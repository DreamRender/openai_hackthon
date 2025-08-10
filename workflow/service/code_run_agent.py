"""
Code run operations agent for handling npm operations and build error fixing.

Provides functionality for npm install, build operations, and automatic
error fixing using OpenAI LLM integration.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger
from workflow.service.code_analyze_agent import FrontendProjectAnalysis

logger = get_logger(__name__)

# Prompt for OpenAI build error analysis and fixing
BUILD_ERROR_ANALYSIS_PROMPT = """
You are a senior frontend developer expert. Your task is to analyze build errors and fix the problematic files.

Your objectives:
1. Analyze the provided build error output to identify the root cause
2. Examine the problematic file content to understand the context
3. Generate a complete corrected version of the file that resolves the build errors
4. Ensure the fix maintains all existing functionality and follows best practices

Key requirements:
- Return COMPLETE file contents (not partial modifications)
- Maintain all imports, exports, and other code structure
- Follow TypeScript/JavaScript best practices
- Ensure compatibility with the project's framework and dependencies
- Keep consistent code formatting and style
- Fix syntax errors, type errors, import issues, and other build-related problems

Response format: Return the complete corrected file content that will resolve the build errors.
"""

# Prompt for OpenAI build error file extraction
BUILD_ERROR_EXTRACTION_PROMPT = """
You are a build system expert. Your task is to analyze build error output and extract the file paths that have errors.

Your objective:
Examine the provided build error output and identify all file paths that contain errors requiring fixes.

Key requirements:
- Extract relative file paths from error messages
- Include only files that have actual errors (not just warnings)
- Return file paths relative to the project root
- Focus on source files that need to be modified to resolve build errors

Response format: Return a list of file paths that contain errors and need to be fixed.
"""


class NpmInstallError(Exception):
    """Exception raised when npm install operation fails."""
    
    def __init__(self, directory_path: str, error_message: str):
        self.directory_path = directory_path
        self.error_message = error_message
        super().__init__(f"npm install failed in directory {directory_path}: {error_message}")


class BuildMaxIterationsError(Exception):
    """Exception raised when build fix iterations exceed maximum limit."""
    
    def __init__(self, max_iterations: int):
        self.max_iterations = max_iterations
        super().__init__(f"Build fix exceeded maximum iterations: {max_iterations}")


class BuildErrorFileExtraction(BaseModel):
    """
    Pydantic model for build error file extraction results.
    
    This model defines the structure of the JSON response from OpenAI
    when extracting error file paths from build output.
    """
    
    error_files: List[str] = Field(
        ...,
        description="List of file paths that contain build errors and need to be fixed"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class BuildErrorFix(BaseModel):
    """
    Pydantic model for build error fix results.
    
    This model defines the structure of the JSON response from OpenAI
    when fixing a problematic file.
    """
    
    fixed_file_content: str = Field(
        ...,
        description="The complete corrected file content that resolves the build errors"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def _run_command(command: str, directory_path: str) -> tuple[bool, str, str]:
    """
    Execute a shell command in the specified directory.
    
    Args:
        command: Shell command to execute
        directory_path: Directory to execute the command in
        
    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=directory_path,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout: {command}")
        return False, "", "Command timed out after 5 minutes"
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        return False, "", str(e)


def _extract_error_files(build_output: str) -> List[str]:
    """
    Extract error file paths from build output using OpenAI.
    
    Args:
        build_output: Build error output text
        
    Returns:
        List of file paths that contain errors
        
    Raises:
        Exception: If error extraction fails
    """
    logger.info("Extracting error files from build output using OpenAI")
    
    try:
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "error_files": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of file paths that contain build errors and need to be fixed"
                }
            },
            "required": ["error_files"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"""{BUILD_ERROR_EXTRACTION_PROMPT}

Build Error Output:
{build_output}

Please analyze this build output and extract all file paths that contain errors requiring fixes."""
        
        logger.info("Sending error extraction request to OpenAI GPT-5 model")
        
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
                    "name": "error_file_extraction",
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
        
        # Extract the response content
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
                logger.error(f"Failed to parse response structure: {response}")
                raise Exception(f"Unable to extract content from response: {type(response)}")
        
        if not content:
            raise Exception("Empty response content from OpenAI")
        
        # Parse the JSON response
        try:
            extraction_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise Exception(f"Invalid JSON response from OpenAI: {e}")
        
        # Create and return the result
        result = BuildErrorFileExtraction(**extraction_data)
        logger.info(f"Extracted {len(result.error_files)} error files: {result.error_files}")
        return result.error_files
        
    except Exception as e:
        logger.error(f"Error extracting error files: {e}")
        raise Exception(f"Failed to extract error files: {e}")


def _fix_error_file(file_path: str, build_output: str, directory_path: str) -> None:
    """
    Fix a single error file using OpenAI.
    
    Args:
        file_path: Path to the file with errors
        build_output: Build error output for context
        directory_path: Project directory path
        
    Raises:
        Exception: If file fixing fails
    """
    logger.info(f"Fixing error file: {file_path}")
    
    # Construct full file path
    full_file_path = Path(directory_path) / file_path
    
    if not full_file_path.exists():
        logger.warning(f"Error file does not exist: {full_file_path}")
        return
    
    try:
        # Read the problematic file content
        with open(full_file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "fixed_file_content": {
                    "type": "string",
                    "description": "The complete corrected file content that resolves the build errors"
                }
            },
            "required": ["fixed_file_content"],
            "additionalProperties": False
        }
        
        # Prepare the input content
        input_content = f"""{BUILD_ERROR_ANALYSIS_PROMPT}

File Path: {file_path}
File Content:
{file_content}

Build Error Output:
{build_output}

Please analyze the build errors and provide the complete corrected file content that will resolve all issues."""
        
        logger.info(f"Sending file fix request to OpenAI GPT-5 model for: {file_path}")
        
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
                    "name": "build_error_fix",
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
        
        # Extract the response content
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
                logger.error(f"Failed to parse response structure: {response}")
                raise Exception(f"Unable to extract content from response: {type(response)}")
        
        if not content:
            raise Exception("Empty response content from OpenAI")
        
        # Parse the JSON response
        try:
            fix_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise Exception(f"Invalid JSON response from OpenAI: {e}")
        
        # Create the result and write the fixed content
        result = BuildErrorFix(**fix_data)
        
        # Write the fixed content back to the file
        with open(full_file_path, 'w', encoding='utf-8') as file:
            file.write(result.fixed_file_content)
        
        logger.info(f"Successfully fixed and wrote file: {file_path}")
        
    except Exception as e:
        logger.error(f"Error fixing file {file_path}: {e}")
        raise Exception(f"Failed to fix file {file_path}: {e}")


def code_run_npm_install(directory_path: str) -> None:
    """
    Execute npm install in the specified frontend project directory.
    
    This function changes to the specified directory and runs npm install
    to install all project dependencies.
    
    Args:
        directory_path: Path to the frontend project directory
        
    Raises:
        NpmInstallError: If npm install operation fails
        Exception: For other errors during the operation
    """
    logger.info(f"Starting npm install in directory: {directory_path}")
    
    # Convert to Path object for easier manipulation
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        logger.error(f"Directory does not exist: {directory_path}")
        raise Exception(f"Directory not found: {directory_path}")
    
    # Check if package.json exists
    package_json_path = dir_path / "package.json"
    if not package_json_path.exists():
        logger.error(f"package.json not found in {directory_path}")
        raise Exception(f"package.json not found in directory: {directory_path}")
    
    try:
        logger.info("Executing npm install command")
        success, stdout, stderr = _run_command("npm install", str(dir_path))
        
        if not success:
            logger.error(f"npm install failed: {stderr}")
            raise NpmInstallError(directory_path, stderr)
        
        logger.info("npm install completed successfully")
        logger.info(f"npm install output: {stdout}")
        
    except NpmInstallError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during npm install: {e}")
        raise Exception(f"npm install operation failed: {e}")


def code_run_build_with_fix(
    frontend_analysis: FrontendProjectAnalysis,
    directory_path: str
) -> None:
    """
    Execute build operations with automatic error fixing using OpenAI.
    
    This function performs ESLint fix (if available) followed by build operations.
    If build errors occur, it uses OpenAI to automatically fix the problematic files
    and retry the build process until successful or maximum iterations are reached.
    
    Args:
        frontend_analysis: Frontend project analysis results containing build commands
        directory_path: Path to the frontend project directory
        
    Raises:
        BuildMaxIterationsError: If build fix iterations exceed maximum limit (20)
        Exception: For other errors during the operation
    """
    logger.info(f"Starting build with fix operation for directory: {directory_path}")
    
    # Convert to Path object for easier manipulation
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        logger.error(f"Directory does not exist: {directory_path}")
        raise Exception(f"Directory not found: {directory_path}")
    
    # Check if build command is available
    if not frontend_analysis.build_command:
        logger.error("No build command found in frontend analysis")
        raise Exception("No build command available for this project")
    
    try:
        # Step 1: Run ESLint fix if available
        if frontend_analysis.eslint_fix_command:
            logger.info(f"Running ESLint fix: {frontend_analysis.eslint_fix_command}")
            success, stdout, stderr = _run_command(frontend_analysis.eslint_fix_command, str(dir_path))
            
            if success:
                logger.info("ESLint fix completed successfully")
                logger.info(f"ESLint fix output: {stdout}")
            else:
                logger.warning(f"ESLint fix had issues but continuing: {stderr}")
        else:
            logger.info("No ESLint fix command available, skipping ESLint step")
        
        # Step 2: Iterative build and fix process
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Build attempt {iteration}/{max_iterations}")
            
            # Run build command
            logger.info(f"Running build command: {frontend_analysis.build_command}")
            success, stdout, stderr = _run_command(frontend_analysis.build_command, str(dir_path))
            
            if success:
                logger.info("Build completed successfully")
                logger.info(f"Build output: {stdout}")
                return
            
            # Build failed, extract error information
            build_output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            logger.warning(f"Build failed on iteration {iteration}")
            logger.info(f"Build error output: {build_output}")
            
            # Extract error files using OpenAI
            try:
                error_files = _extract_error_files(build_output)
                
                if not error_files:
                    logger.warning("No error files identified, but build still failed")
                    continue
                
                # Fix each error file
                for error_file in error_files:
                    logger.info(f"Attempting to fix error file: {error_file}")
                    _fix_error_file(error_file, build_output, str(dir_path))
                
                logger.info(f"Fixed {len(error_files)} error files in iteration {iteration}")
                
            except Exception as e:
                logger.error(f"Error during fix process in iteration {iteration}: {e}")
                continue
        
        # If we reach here, we've exceeded max iterations
        logger.error(f"Build fix exceeded maximum iterations: {max_iterations}")
        raise BuildMaxIterationsError(max_iterations)
        
    except BuildMaxIterationsError:
        raise
    except Exception as e:
        logger.error(f"Error during build with fix operation: {e}")
        raise Exception(f"Build with fix operation failed: {e}")
