import json
import os
from pathlib import Path
from typing import List, Tuple, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger

logger = get_logger(__name__)

# Prompt for OpenAI CSS analysis
CSS_ANALYSIS_PROMPT = """
Please analyze the provided frontend project structure and CSS files to identify the main CSS file.

The main CSS file is typically:
1. Contains global CSS imports like @tailwindcss/base, @tailwindcss/components, @tailwindcss/utilities
2. Contains global reset styles or base styles
3. Is imported at the root level of the application
4. Has the most comprehensive styling definitions
5. Contains CSS custom properties (CSS variables) definitions
6. May be named like main.css, app.css, global.css, index.css, styles.css, etc.

Based on the project structure and CSS file contents provided, determine which CSS file is the main/global CSS file for this project.

If no clear main CSS file is found, return the CSS file that contains the most global styling definitions.

Response requirements:
- main_css_path: The relative path to the main CSS file from the project root
"""


class CssFileNotFoundError(Exception):
    """Exception raised when no CSS files are found in the specified directory."""
    
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        super().__init__(f"No CSS files found in directory: {directory_path}")


class MainCssAnalysis(BaseModel):
    """
    Pydantic model for main CSS file analysis results.
    
    This model defines the structure of the JSON response from OpenAI
    when analyzing CSS files to determine the main CSS file.
    """
    
    main_css_path: str = Field(
        ..., 
        description="The relative path to the main CSS file from the project root"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class CssAnalysisResult(BaseModel):
    """
    Result model for CSS analysis containing only the main CSS file path.
    
    The CSS content should be read dynamically from disk when needed,
    not stored in memory to ensure we always have the latest version.
    """
    
    main_css_path: str = Field(
        ...,
        description="The relative path to the main CSS file from the project root"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def _scan_css_files(directory_path: str) -> List[Tuple[str, str]]:
    """
    Scan the directory for CSS files and return their paths and contents.
    
    This function recursively scans the directory for .css files while
    excluding common directories like node_modules, .git, etc.
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        List of tuples containing (relative_path, file_content) for each CSS file
        
    Raises:
        CssFileNotFoundError: If no CSS files are found
    """
    logger.info(f"Scanning directory for CSS files: {directory_path}")
    
    dir_path = Path(directory_path)
    css_files = []
    
    # Directories to exclude from scanning
    exclude_dirs = {
        'node_modules', '.git', '.next', 'dist', 'build', 
        '__pycache__', '.vscode', '.idea', 'coverage'
    }
    
    # Recursively find all .css files
    for file_path in dir_path.rglob("*.css"):
        # Check if any parent directory is in exclude list
        if any(part in exclude_dirs for part in file_path.parts):
            continue
            
        relative_path = file_path.relative_to(dir_path)
        
        try:
            # Read CSS file content
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            css_files.append((str(relative_path), content))
            logger.info(f"Found CSS file: {relative_path}")
            
        except Exception as e:
            logger.warning(f"Failed to read CSS file {file_path}: {e}")
            continue
    
    if not css_files:
        raise CssFileNotFoundError(directory_path)
    
    logger.info(f"Found {len(css_files)} CSS files")
    return css_files


def css_analyze_agent(directory_path: str) -> CssAnalysisResult:
    """
    Analyze a frontend project directory to identify the main CSS file.
    
    This function scans the specified directory for CSS files (excluding node_modules),
    sends the project structure and CSS contents to OpenAI's GPT-5 model for analysis,
    and returns the main CSS file path and its content.
    
    Args:
        directory_path: Path to the frontend project directory
        
    Returns:
        CssAnalysisResult: Contains the main CSS file path and its content
            
    Raises:
        CssFileNotFoundError: If no CSS files are found in the directory
        Exception: For other errors during file reading or API calls
    """
    logger.info(f"Starting CSS analysis for directory: {directory_path}")
    
    # Convert to Path object for easier manipulation
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        raise CssFileNotFoundError(directory_path)
    
    try:
        # Scan for CSS files
        css_files = _scan_css_files(directory_path)
        
        # Prepare content for OpenAI analysis
        project_structure = f"Project directory: {directory_path}\n\n"
        
        css_contents = "CSS Files Found:\n\n"
        for relative_path, content in css_files:
            css_contents += f"File: {relative_path}\n"
            css_contents += f"Content:\n{content}\n"
            css_contents += "-" * 80 + "\n\n"
        
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "main_css_path": {
                    "type": "string",
                    "description": "The relative path to the main CSS file from the project root"
                }
            },
            "required": ["main_css_path"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"{CSS_ANALYSIS_PROMPT}\n\n{project_structure}{css_contents}"
        
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
                    "name": "css_analysis",
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
            analysis_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise Exception(f"Invalid JSON response from OpenAI: {e}")
        
        # Create the analysis result
        main_css_analysis = MainCssAnalysis(**analysis_data)
        main_css_path = main_css_analysis.main_css_path
        
        # Verify that the main CSS file exists in our scan results
        main_css_found = False
        for relative_path, content in css_files:
            if relative_path == main_css_path:
                main_css_found = True
                break
        
        if not main_css_found:
            # If still not found, raise exception - we cannot process projects without main CSS
            logger.error("Main CSS file not found after analysis and fallback attempts")
            raise Exception(f"No main CSS file could be identified in project: {directory_path}")
        
        # Create and return the result (only path, content will be read dynamically)
        result = CssAnalysisResult(main_css_path=main_css_path)
        
        logger.info(f"CSS analysis completed. Main CSS file: {result.main_css_path}")
        return result
        
    except CssFileNotFoundError:
        logger.error(f"No CSS files found in {directory_path}")
        raise
    except Exception as e:
        logger.error(f"Error during CSS analysis: {e}")
        raise Exception(f"CSS analysis failed: {e}")
