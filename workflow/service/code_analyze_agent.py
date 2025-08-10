import json
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger

logger = get_logger(__name__)

# Prompt for OpenAI analysis
PACKAGE_JSON_ANALYSIS_PROMPT = """
Please analyze the provided package.json file and determine if this is a frontend project.

For a project to be considered a frontend project, it should have:
- Frontend frameworks (React, Vue, Angular, etc.)
- Build tools for frontend (Webpack, Vite, Parcel, etc.)
- Frontend-specific dependencies

Response requirements:
1. is_frontend_project: true if this is a frontend project, false otherwise
2. start_command: If it's a frontend project, provide the start command (usually from scripts section like "npm start", "npm run dev", etc.). If not a frontend project, return empty string "".
3. build_command: If it's a frontend project, provide the build command (usually from scripts section like "npm run build", "yarn build", etc.). If not a frontend project, return empty string "".
4. ui_frameworks_info: If it's a frontend project, provide information about UI frameworks, libraries, TailwindCSS and their versions. If not a frontend project, return empty string "".

Always return all four fields, using empty strings for start_command, build_command and ui_frameworks_info when the project is not a frontend project.
"""


class PackageJsonNotFoundError(Exception):
    """Exception raised when package.json file is not found in the specified directory."""
    
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        super().__init__(f"package.json not found in directory: {directory_path}")


class FrontendProjectAnalysis(BaseModel):
    """
    Pydantic model for frontend project analysis results.
    
    This model defines the structure of the JSON response from OpenAI
    when analyzing a package.json file to determine if it's a frontend project.
    """
    
    is_frontend_project: bool = Field(
        ..., 
        description="Whether this project is a frontend project"
    )
    start_command: str = Field(
        ...,
        description="The command to start the project (from package.json scripts), empty string if not applicable"
    )
    build_command: str = Field(
        ...,
        description="The command to build the project (from package.json scripts), empty string if not applicable"
    )
    ui_frameworks_info: str = Field(
        ...,
        description="Information about UI frameworks, libraries, TailwindCSS and their versions, empty string if not applicable"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def code_analyze_agent(directory_path: str) -> FrontendProjectAnalysis:
    """
    Analyze a local directory to determine if it contains a frontend project.
    
    This function reads the package.json file from the specified directory,
    sends it to OpenAI's GPT-5 model for analysis, and returns structured
    information about whether it's a frontend project and its characteristics.
    
    Args:
        directory_path: Path to the directory containing the project
        
    Returns:
        FrontendProjectAnalysis: Structured analysis results including:
            - is_frontend_project: Boolean indicating if it's a frontend project
            - start_command: Command to start the project (if frontend)
            - build_command: Command to build the project (if frontend)
            - ui_frameworks_info: Information about UI frameworks and versions (if frontend)
            
    Raises:
        PackageJsonNotFoundError: If package.json file is not found in the directory
        Exception: For other errors during file reading or API calls
    """
    logger.info(f"Starting code analysis for directory: {directory_path}")
    
    # Convert to Path object for easier manipulation
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        raise PackageJsonNotFoundError(directory_path)
    
    # Look for package.json file
    package_json_path = dir_path / "package.json"
    
    if not package_json_path.exists():
        logger.error(f"package.json not found in {directory_path}")
        raise PackageJsonNotFoundError(directory_path)
    
    try:
        # Read package.json content
        logger.info(f"Reading package.json from: {package_json_path}")
        with open(package_json_path, 'r', encoding='utf-8') as file:
            package_json_content = file.read()
        
        logger.info("Successfully read package.json content")
        
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "is_frontend_project": {
                    "type": "boolean",
                    "description": "Whether this project is a frontend project"
                },
                "start_command": {
                    "type": "string",
                    "description": "The command to start the project, empty string if not applicable"
                },
                "build_command": {
                    "type": "string",
                    "description": "The command to build the project, empty string if not applicable"
                },
                "ui_frameworks_info": {
                    "type": "string",
                    "description": "Information about UI frameworks, libraries, TailwindCSS and their versions, empty string if not applicable"
                }
            },
            "required": ["is_frontend_project", "start_command", "build_command", "ui_frameworks_info"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"{PACKAGE_JSON_ANALYSIS_PROMPT}\n\npackage.json content:\n{package_json_content}"
        
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
                    "name": "frontend_analysis",
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
                # Fallback: convert response to string for debugging
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
        
        # Create and return the Pydantic model instance
        result = FrontendProjectAnalysis(**analysis_data)
        
        logger.info(f"Analysis completed. Is frontend project: {result.is_frontend_project}")
        return result
        
    except FileNotFoundError:
        logger.error(f"File not found: {package_json_path}")
        raise PackageJsonNotFoundError(directory_path)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse package.json: {e}")
        raise Exception(f"Invalid package.json format: {e}")
    except Exception as e:
        logger.error(f"Error during code analysis: {e}")
        raise Exception(f"Code analysis failed: {e}")
