import json
import os
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger
from workflow.service.css_analyze_agent import CssAnalysisResult
from workflow.service.code_analyze_agent import FrontendProjectAnalysis

logger = get_logger(__name__)

# Prompts for OpenAI processing
# Long prompts must be declared at module top per workspace rules
COLOR_THEME_INSTRUCTION_PROMPT = """
You are a senior frontend theme architect. Analyze a single frontend file (TSX/JSX/HTML) and centralize hardcoded colors using CSS custom properties.

Objectives for THIS FILE ONLY:
1) Identify ALL hardcoded colors (hex/rgb/rgba/hsl/hsla/named/Tailwind-like tokens/etc.)
2) Replace them with var(--css-variable) in the file and produce the COMPLETE modified file content
3) DO NOT return the full main CSS. Instead, return a precise natural-language instruction list describing the necessary edits to the main CSS:
   - New CSS variables to add (name and value), and their purpose
   - Whether an existing variable already covers a color (reuse it)
   - Where to place variables (e.g., in :root or in existing theme groups)
   - Any grouping/order rules
   - Any removals/renames if applicable

Important:
- Preserve existing functionality and styling
- Maintain import/export and code structure
- Keep consistent formatting
- If the project already defines CSS variables, reuse them whenever appropriate

Return JSON with:
- modified_file_content: string (complete file content)
- main_css_change_instructions: string (natural-language instructions only, no CSS file content)
"""

FINAL_MAIN_CSS_MERGE_PROMPT = """
You are a CSS theme system editor. You will be given the current main CSS content and a set of natural-language instructions from multiple files describing how to update the main CSS.

Your task:
1) Apply ALL instructions precisely
2) Maintain existing variable definitions unless superseded
3) Add new variables with semantic names, group them logically
4) Ensure final CSS remains valid and consistent
5) Return ONLY the COMPLETE, updated main CSS content as a string
"""


class CodeActFileNotFoundError(Exception):
    """Exception raised when no frontend files are found in the specified directory."""
    
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        super().__init__(f"No frontend files (tsx/jsx/html) found in directory: {directory_path}")


class ThemeExtractionInstructionResult(BaseModel):
    """
    Structured output for per-file processing.

    Contains the fully modified file content and a natural-language instruction
    list describing changes that should be applied to the main CSS file.
    """

    file_path: str = Field(
        ..., description="Relative path of the processed file within the project"
    )
    modified_file_content: str = Field(
        ..., description="Complete modified file content with CSS variables applied"
    )
    main_css_change_instructions: str = Field(
        ..., description="Natural-language instructions describing how to update the main CSS"
    )

    model_config = {"validate_assignment": True, "extra": "forbid"}


class FinalMainCssResult(BaseModel):
    """
    Structured output for the final merged main CSS generation.
    """

    updated_main_css_content: str = Field(
        ..., description="The complete updated main CSS content after applying all instructions"
    )

    model_config = {"validate_assignment": True, "extra": "forbid"}


class CodeActResult(BaseModel):
    """
    Result of the CodeAct agent execution.
    """

    processed_file_count: int = Field(..., description="Number of frontend files processed")
    main_css_path: str = Field(..., description="Path to the updated main CSS file")
    success: bool = Field(..., description="Whether the operation completed successfully")
    message: str = Field(..., description="Summary message for the operation")


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
) -> ThemeExtractionInstructionResult:
    """
    Process a single frontend file to extract colors and generate theme variables.
    
    Args:
        file_path: Relative path to the file being processed
        file_content: Content of the file to process
        main_css_content: Current content of the main CSS file
        ui_frameworks_info: Information about UI frameworks used in the project
        directory_path: Root directory path for context
        
    Returns:
        ThemeExtractionInstructionResult: Modified file content and natural-language main CSS change instructions
        
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
                "file_path": {
                    "type": "string",
                    "description": "Relative path of the processed file within the project"
                },
                "modified_file_content": {
                    "type": "string",
                    "description": "The complete modified file content with colors replaced by CSS variables"
                },
                "main_css_change_instructions": {
                    "type": "string",
                    "description": "Natural-language instructions describing how to update the main CSS"
                }
            },
            "required": ["file_path", "modified_file_content", "main_css_change_instructions"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"""{COLOR_THEME_INSTRUCTION_PROMPT}

Project Information:
- Directory: {directory_path}
- UI Frameworks: {ui_frameworks_info}

File to Process: {file_path}
File Content:
{file_content}

Current Main CSS Content:
{main_css_content}

Please analyze this file and extract all hardcoded colors to CSS variables. Return the complete modified file content and a precise natural-language instruction list for main CSS changes. Do NOT include the full main CSS content here."""
        
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
                    "name": "theme_extraction_instructions",
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
        # Ensure file_path is present in the response; if not, inject from input
        if "file_path" not in extraction_data or not extraction_data.get("file_path"):
            extraction_data["file_path"] = file_path
        result = ThemeExtractionInstructionResult(**extraction_data)
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


def _generate_final_main_css(
    current_main_css_content: str,
    aggregated_instructions: str,
    ui_frameworks_info: str,
    directory_path: str,
) -> FinalMainCssResult:
    """
    Generate the final main CSS by applying aggregated natural-language instructions.

    Args:
        current_main_css_content: The current content of the main CSS file
        aggregated_instructions: Combined natural-language instructions from all files
        ui_frameworks_info: Information about UI frameworks used in the project
        directory_path: Root directory path for context

    Returns:
        FinalMainCssResult: The complete updated main CSS content

    Raises:
        Exception: For errors during API calls or content processing
    """
    logger.info("Generating final main CSS based on aggregated instructions")

    try:
        workflow_config = get_workflow_config()
        client = OpenAI(api_key=workflow_config.openai_api_key)

        json_schema = {
            "type": "object",
            "properties": {
                "updated_main_css_content": {
                    "type": "string",
                    "description": "The complete updated main CSS content after applying all instructions"
                }
            },
            "required": ["updated_main_css_content"],
            "additionalProperties": False
        }

        input_content = f"""{FINAL_MAIN_CSS_MERGE_PROMPT}

Project Information:
- Directory: {directory_path}
- UI Frameworks: {ui_frameworks_info}

Current Main CSS Content:
{current_main_css_content}

Aggregated Instructions From All Files:
{aggregated_instructions}

Please apply all instructions and return only the complete updated main CSS content."""

        logger.info("Sending request to OpenAI GPT-5 model for final main CSS generation")

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
                    "name": "final_main_css_generation",
                    "strict": True,
                    "schema": json_schema
                },
                "verbosity": "medium"
            },
            reasoning={"effort": "minimal"},
            tools=[],
            store=True,
        )

        logger.info("Received response from OpenAI for final main CSS generation")

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
                logger.error(f"Failed to parse response structure: {response}")
                raise Exception(f"Unable to extract content from response: {type(response)}")

        if not content:
            raise Exception("Empty response content from OpenAI")

        logger.info(f"Extracted response content for final CSS: {content[:200]}...")

        try:
            final_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise Exception(f"Invalid JSON response from OpenAI: {e}")

        result = FinalMainCssResult(**final_data)
        logger.info("Successfully generated final main CSS content")
        return result

    except Exception as e:
        logger.error(f"Error generating final main CSS: {e}")
        raise Exception(f"Failed to generate final main CSS: {e}")


def code_act_agent(
    directory_path: str, 
    css_analysis_result: CssAnalysisResult, 
    frontend_analysis: FrontendProjectAnalysis
) -> CodeActResult:
    """
    Process frontend files to extract colors and create a centralized theme system.
    
    This function scans the specified directory for frontend files (tsx, jsx, html),
    then processes files concurrently (up to 10 in parallel) via OpenAI's GPT-5 model.
    Each per-file task returns the fully modified file content and a natural-language
    instruction list for main CSS changes. After all per-file tasks complete, a final
    aggregation call generates the complete updated main CSS, which is then written once.
    
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

        # Get the main CSS file path and read it once (we will generate the final CSS after aggregation)
        main_css_path = dir_path / css_analysis_result.main_css_path
        try:
            with open(main_css_path, 'r', encoding='utf-8') as css_file:
                current_main_css_content = css_file.read()
            logger.info(f"Read main CSS content: {len(current_main_css_content)} characters")
        except Exception as e:
            logger.error(f"Failed to read main CSS file {main_css_path}: {e}")
            raise Exception(f"Cannot read main CSS file: {e}")

        logger.info(f"Starting concurrent processing of {len(frontend_files)} frontend files")
        logger.info(f"Main CSS file: {css_analysis_result.main_css_path}")

        extraction_results: List[ThemeExtractionInstructionResult] = []
        errors: List[str] = []

        # Execute per-file processing with up to 10 concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_file = {}
            for relative_file_path, file_content in frontend_files:
                future = executor.submit(
                    _process_single_file,
                    file_path=relative_file_path,
                    file_content=file_content,
                    main_css_content=current_main_css_content,
                    ui_frameworks_info=frontend_analysis.ui_frameworks_info,
                    directory_path=directory_path,
                )
                future_to_file[future] = relative_file_path

            for future in as_completed(future_to_file):
                rel_path = future_to_file[future]
                try:
                    result = future.result()
                    extraction_results.append(result)
                    logger.info(f"Concurrent processing completed for file: {rel_path}")
                except Exception as e:
                    error_msg = f"Concurrent processing failed for file {rel_path}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        if errors:
            # Early fail on any per-file error per project rule that stage errors must throw
            raise Exception("; ".join(errors))

        logger.info("Writing modified files to disk")
        for result in extraction_results:
            full_file_path = dir_path / result.file_path
            _write_file_content(str(full_file_path), result.modified_file_content)

        logger.info("Aggregating main CSS change instructions")
        instructions_parts: List[str] = []
        for result in extraction_results:
            # Include file path context to help the merge step
            instructions_parts.append(f"File: {result.file_path}\n{result.main_css_change_instructions}\n")
        aggregated_instructions = "\n\n".join(instructions_parts)

        final_css_result = _generate_final_main_css(
            current_main_css_content=current_main_css_content,
            aggregated_instructions=aggregated_instructions,
            ui_frameworks_info=frontend_analysis.ui_frameworks_info,
            directory_path=directory_path,
        )

        _write_file_content(str(main_css_path), final_css_result.updated_main_css_content)

        logger.info("CodeActAgent completed successfully with concurrent processing")
        logger.info(
            f"Processed {len(extraction_results)} files and updated main CSS: {css_analysis_result.main_css_path}"
        )

        return CodeActResult(
            processed_file_count=len(extraction_results),
            main_css_path=str(main_css_path),
            success=True,
            message="CodeActAgent completed with concurrent processing and final CSS merge",
        )
        
    except CodeActFileNotFoundError:
        logger.error(f"No frontend files found in {directory_path}")
        raise
    except Exception as e:
        logger.error(f"Error during CodeActAgent execution: {e}")
        raise Exception(f"CodeActAgent failed: {e}")
