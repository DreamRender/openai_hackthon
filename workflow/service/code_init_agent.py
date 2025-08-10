import os
import stat
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from common.utils.logger import get_logger

logger = get_logger(__name__)


class DirectoryNotFoundError(Exception):
    """Exception raised when the specified directory is not found."""
    
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        super().__init__(f"Directory not found: {directory_path}")


class PermissionError(Exception):
    """Exception raised when permission setting fails."""
    
    def __init__(self, path: str, error_message: str):
        self.path = path
        self.error_message = error_message
        super().__init__(f"Failed to set permissions for {path}: {error_message}")


class CodeInitResult(BaseModel):
    """
    Pydantic model for code initialization results.
    
    This model defines the structure of the result returned by the 
    code_init_agent function when initializing project directories.
    """
    
    success: bool = Field(
        ...,
        description="Whether the initialization was successful"
    )
    design_directory_path: str = Field(
        ...,
        description="The absolute path to the created .design directory"
    )
    themes_directory_path: str = Field(
        ...,
        description="The absolute path to the created .design/themes directory"
    )
    message: str = Field(
        ...,
        description="Success or error message describing the operation result"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def code_init_agent(directory_path: str) -> CodeInitResult:
    """
    Initialize a project directory by creating .design structure with proper permissions.
    
    This function creates the necessary directory structure for design files:
    1. Creates a .design directory in the specified path
    2. Creates a .design/themes subdirectory
    3. Sets permissions to 777 (read, write, execute for all users) for both directories
    
    Args:
        directory_path: Path to the target directory where .design structure should be created
        
    Returns:
        CodeInitResult: Structured result containing:
            - success: Boolean indicating if initialization was successful
            - design_directory_path: Absolute path to the created .design directory
            - themes_directory_path: Absolute path to the created .design/themes directory
            - message: Success or error message
            
    Raises:
        DirectoryNotFoundError: If the specified directory does not exist
        PermissionError: If permission setting fails for any created directory
        Exception: For other unexpected errors during directory creation
    """
    logger.info(f"Starting code initialization for directory: {directory_path}")
    
    # Convert to Path object for easier manipulation
    base_path = Path(directory_path).resolve()
    
    # Check if the base directory exists
    if not base_path.exists():
        error_msg = f"Base directory does not exist: {directory_path}"
        logger.error(error_msg)
        raise DirectoryNotFoundError(directory_path)
    
    if not base_path.is_dir():
        error_msg = f"Path is not a directory: {directory_path}"
        logger.error(error_msg)
        raise DirectoryNotFoundError(directory_path)
    
    try:
        # Define paths for the directories to create
        design_dir = base_path / ".design"
        themes_dir = design_dir / "themes"
        
        logger.info(f"Creating .design directory at: {design_dir}")
        
        # Create .design directory
        design_dir.mkdir(exist_ok=True)
        logger.info("Successfully created .design directory")
        
        # Set permissions to 777 for .design directory
        logger.info("Setting permissions (777) for .design directory")
        os.chmod(design_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        logger.info("Successfully set permissions for .design directory")
        
        # Create .design/themes subdirectory
        logger.info(f"Creating themes subdirectory at: {themes_dir}")
        themes_dir.mkdir(exist_ok=True)
        logger.info("Successfully created .design/themes directory")
        
        # Set permissions to 777 for themes directory
        logger.info("Setting permissions (777) for .design/themes directory")
        os.chmod(themes_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        logger.info("Successfully set permissions for .design/themes directory")
        
        # Create successful result
        result = CodeInitResult(
            success=True,
            design_directory_path=str(design_dir),
            themes_directory_path=str(themes_dir),
            message="Successfully initialized .design directory structure with proper permissions"
        )
        
        logger.info("Code initialization completed successfully")
        return result
        
    except OSError as e:
        error_msg = f"Failed to create directories or set permissions: {e}"
        logger.error(error_msg)
        raise PermissionError(str(base_path), str(e))
    except Exception as e:
        error_msg = f"Unexpected error during code initialization: {e}"
        logger.error(error_msg)
        raise Exception(f"Code initialization failed: {e}")
