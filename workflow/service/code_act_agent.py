import json
import os
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger
from workflow.service.css_analyze_agent import CssAnalysisResult
from workflow.service.code_analyze_agent import FrontendProjectAnalysis

logger = get_logger(__name__)

# Prompt for OpenAI color theme extraction and modification
COLOR_THEME_PROMPT = """
You are a frontend theme architect. Your task is to analyze a frontend file (TSX/JSX/HTML) and extract all hardcoded colors to create a centralized theme system using CSS custom properties (variables).

Your objectives:
1. Identify ALL hardcoded colors in the provided file including:
   - Hex colors (#ffffff, #000, etc.)
   - RGB/RGBA colors (rgb(255,255,255), rgba(0,0,0,0.5), etc.)
   - HSL/HSLA colors (hsl(0,0%,100%), etc.)
   - Named colors (red, blue, white, black, etc.)
   - Colors in Tailwind classes (text-red-500, bg-blue-600, etc.)
   - Any other color representations

2. For each unique color found:
   - Generate a meaningful CSS variable name (e.g., --primary-color, --text-dark, --bg-light)
   - Add the variable definition to the main CSS file
   - Replace the hardcoded color in the file with var(--variable-name)

3. Preserve existing CSS variables that are already defined in the main CSS

4. Ensure the modified file maintains the same visual appearance
5. Generate complete file contents (not partial modifications)

Key requirements:
- Return COMPLETE file contents for both the modified file and updated main CSS
- Maintain all existing functionality and styling
- Use semantic variable names that describe the color's purpose
- Group related colors logically in the CSS
- Preserve all imports, exports, and other code structure
- Keep consistent code formatting and style

Response format: Return the complete modified file content and complete updated main CSS content.
"""


class CodeActFileNotFoundError(Exception):
    """Exception raised when no frontend files are found in the specified directory."""
    
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        super().__init__(f"No frontend files (tsx/jsx/html) found in directory: {directory_path}")


class ThemeExtractionResult(BaseModel):
    """
    Pydantic model for theme extraction results from OpenAI.
    
    This model defines the structure of the JSON response from OpenAI
    when processing a file for color theme extraction.
    """
    
    modified_file_content: str = Field(
        ...,
        description="The complete modified file content with colors replaced by CSS variables"
    )
    updated_main_css_content: str = Field(
        ...,
        description="The complete updated main CSS content with new CSS variable definitions"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def _scan_frontend_files(directory_path: str) -> List[Tuple[str, str]]:
    """
    Scan the directory for frontend files (tsx, jsx, html) and return their paths and contents.
    
    This function recursively scans the directory for frontend files while
    excluding common directories like node_modules, .git, etc.
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        List of tuples containing (relative_path, file_content) for each frontend file
        
    Raises:
        CodeActFileNotFoundError: If no frontend files are found
    """
    logger.info(f"Scanning directory for frontend files: {directory_path}")
    
    dir_path = Path(directory_path)
    frontend_files = []
    
    # Directories to exclude from scanning
    exclude_dirs = {
        'node_modules', '.git', '.next', 'dist', 'build', 
        '__pycache__', '.vscode', '.idea', 'coverage', '.nuxt'
    }
    
    # File extensions to search for
    target_extensions = ['*.tsx', '*.jsx', '*.html']
    
    # Recursively find all target files
    for extension in target_extensions:
        for file_path in dir_path.rglob(extension):
            # Check if any parent directory is in exclude list
            if any(part in exclude_dirs for part in file_path.parts):
                continue
                
            relative_path = file_path.relative_to(dir_path)
            
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                frontend_files.append((str(relative_path), content))
                logger.info(f"Found frontend file: {relative_path}")
                
            except Exception as e:
                logger.warning(f"Failed to read frontend file {file_path}: {e}")
                continue
    
    if not frontend_files:
        raise CodeActFileNotFoundError(directory_path)
    
    logger.info(f"Found {len(frontend_files)} frontend files")
    return frontend_files


def _process_single_file(
    file_path: str, 
    file_content: str, 
    main_css_content: str,
    ui_frameworks_info: str,
    directory_path: str
) -> ThemeExtractionResult:
    """
    Process a single frontend file to extract colors and generate theme variables.
    
    Args:
        file_path: Relative path to the file being processed
        file_content: Content of the file to process
        main_css_content: Current content of the main CSS file
        ui_frameworks_info: Information about UI frameworks used in the project
        directory_path: Root directory path for context
        
    Returns:
        ThemeExtractionResult: Contains modified file content and updated main CSS
        
    Raises:
        Exception: For errors during API calls or content processing
    """
    logger.info(f"Processing file for color theme extraction: {file_path}")
    
    try:
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "modified_file_content": {
                    "type": "string",
                    "description": "The complete modified file content with colors replaced by CSS variables"
                },
                "updated_main_css_content": {
                    "type": "string",
                    "description": "The complete updated main CSS content with new CSS variable definitions"
                }
            },
            "required": ["modified_file_content", "updated_main_css_content"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"""{COLOR_THEME_PROMPT}

Project Information:
- Directory: {directory_path}
- UI Frameworks: {ui_frameworks_info}

File to Process: {file_path}
File Content:
{file_content}

Current Main CSS Content:
{main_css_content}

Please analyze this file and extract all hardcoded colors to CSS variables. Return the complete modified file content and updated main CSS content."""
        
        logger.info("Sending request to OpenAI GPT-5 model")
        
        # Call OpenAI API with structured output
        response = client.responses.create(
            model="gpt-5",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": input_content
                        }
                    ]
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "theme_extraction",
                    "strict": True,
                    "schema": json_schema
                },
                "verbosity": "medium"
            },
            reasoning={
                "effort": "minimal"
            },
            tools=[],
            store=True
        )
        
        # Extract the response content (compatible with Responses API structure)
        logger.info("Received response from OpenAI")
        
        # Try to extract content from Responses API structure
        content = getattr(response, "output_text", None)
        if not content:
            try:
                content_parts = []
                for item in getattr(response, "output", []) or []:
                    for block in getattr(item, "content", []) or []:
                        block_type = getattr(block, "type", "")
                        if block_type in ("output_text", "text") and hasattr(block, "text"):
                            content_parts.append(block.text)
                content = "\n".join(content_parts) if content_parts else ""
            except Exception:
                # Fallback: log error for debugging
                logger.error(f"Failed to parse response structure: {response}")
                raise Exception(f"Unable to extract content from response: {type(response)}")
        
        if not content:
            raise Exception("Empty response content from OpenAI")
        
        logger.info(f"Extracted response content: {content[:200]}...")
        
        # Parse the JSON response
        try:
            extraction_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise Exception(f"Invalid JSON response from OpenAI: {e}")
        
        # Create and return the result
        result = ThemeExtractionResult(**extraction_data)
        logger.info(f"Successfully processed file: {file_path}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        raise Exception(f"Failed to process file {file_path}: {e}")


def _write_file_content(file_path: str, content: str) -> None:
    """
    Write content to a file, creating directories if needed.
    
    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        
    Raises:
        Exception: If file writing fails
    """
    try:
        # Ensure directory exists
        file_path_obj = Path(file_path)
        file_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content to file
        with open(file_path_obj, 'w', encoding='utf-8') as file:
            file.write(content)
        
        logger.info(f"Successfully wrote content to file: {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        raise Exception(f"File write operation failed for {file_path}: {e}")


def code_act_agent(
    directory_path: str, 
    css_analysis_result: CssAnalysisResult, 
    frontend_analysis: FrontendProjectAnalysis
) -> None:
    """
    Process frontend files to extract colors and create a centralized theme system.
    
    This function scans the specified directory for frontend files (tsx, jsx, html),
    processes each file individually through OpenAI's GPT-5 model to extract hardcoded
    colors and replace them with CSS custom properties (variables), then writes the
    modified files and updated main CSS back to the filesystem.
    
    The process is sequential - each file is processed one by one, ensuring that
    the main CSS file is progressively updated with new color variables from each
    processed file.
    
    Args:
        directory_path: Path to the directory containing the frontend project
        css_analysis_result: Result from CSS analysis containing main CSS file info
        frontend_analysis: Result from frontend project analysis
        
    Raises:
        CodeActFileNotFoundError: If no frontend files are found in the directory
        Exception: For any errors during file processing, API calls, or file writing
    """
    logger.info(f"Starting CodeActAgent for directory: {directory_path}")
    
    # Check if it's actually a frontend project
    if not frontend_analysis.is_frontend_project:
        logger.error("Project is not identified as a frontend project")
        raise Exception(f"Directory {directory_path} is not a frontend project")
    
    # Convert to Path object for easier manipulation
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        logger.error(f"Directory does not exist: {directory_path}")
        raise Exception(f"Directory not found: {directory_path}")
    
    try:
        # Scan for frontend files
        frontend_files = _scan_frontend_files(directory_path)
        
        # Get the main CSS file path
        main_css_path = dir_path / css_analysis_result.main_css_path
        
        logger.info(f"Starting to process {len(frontend_files)} frontend files")
        logger.info(f"Main CSS file: {css_analysis_result.main_css_path}")
        
        # Process each file sequentially
        for index, (relative_file_path, file_content) in enumerate(frontend_files, 1):
            logger.info(f"Processing file {index}/{len(frontend_files)}: {relative_file_path}")
            
            try:
                # Read the latest main CSS content from disk before processing each file
                # This ensures we have the most up-to-date CSS variables from previous iterations
                try:
                    with open(main_css_path, 'r', encoding='utf-8') as css_file:
                        current_main_css_content = css_file.read()
                    logger.info(f"Read latest main CSS content from disk: {len(current_main_css_content)} characters")
                except Exception as e:
                    logger.error(f"Failed to read main CSS file {main_css_path}: {e}")
                    raise Exception(f"Cannot read main CSS file: {e}")
                
                # Process the file with current main CSS content
                extraction_result = _process_single_file(
                    file_path=relative_file_path,
                    file_content=file_content,
                    main_css_content=current_main_css_content,
                    ui_frameworks_info=frontend_analysis.ui_frameworks_info,
                    directory_path=directory_path
                )
                
                # Write the modified file content
                full_file_path = dir_path / relative_file_path
                _write_file_content(str(full_file_path), extraction_result.modified_file_content)
                
                # Write the updated main CSS content
                _write_file_content(str(main_css_path), extraction_result.updated_main_css_content)
                
                logger.info(f"Successfully processed and wrote file {index}/{len(frontend_files)}: {relative_file_path}")
                
            except Exception as e:
                logger.error(f"Failed to process file {relative_file_path}: {e}")
                raise Exception(f"Processing failed for file {relative_file_path}: {e}")
        
        logger.info("CodeActAgent completed successfully")
        logger.info(f"Processed {len(frontend_files)} files and updated main CSS: {css_analysis_result.main_css_path}")
        
    except CodeActFileNotFoundError:
        logger.error(f"No frontend files found in {directory_path}")
        raise
    except Exception as e:
        logger.error(f"Error during CodeActAgent execution: {e}")
        raise Exception(f"CodeActAgent failed: {e}")
