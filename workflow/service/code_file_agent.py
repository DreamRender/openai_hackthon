"""
Code file operations agent for handling file copy operations.

Provides functionality for copying files from source to destination paths
with proper error handling and logging.
"""

import shutil
from pathlib import Path
from typing import Optional

from common.utils.logger import get_logger

logger = get_logger(__name__)


class FileNotFoundError(Exception):
    """Exception raised when source file is not found."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"Source file not found: {file_path}")


class FileCopyError(Exception):
    """Exception raised when file copy operation fails."""
    
    def __init__(self, source_path: str, destination_path: str, error_message: str):
        self.source_path = source_path
        self.destination_path = destination_path
        self.error_message = error_message
        super().__init__(f"Failed to copy file from {source_path} to {destination_path}: {error_message}")


def code_file_agent(file_path: str, new_file_path: str) -> str:
    """
    Copy a file from source path to destination path.
    
    This function copies a file from the specified source path to a new destination path,
    creating any necessary parent directories. It returns the absolute path of the
    copied file for verification purposes.
    
    Args:
        file_path: Source file path to copy from
        new_file_path: Destination file path (including filename) to copy to
        
    Returns:
        str: Absolute path of the copied file
        
    Raises:
        FileNotFoundError: If the source file does not exist
        FileCopyError: If the file copy operation fails
        Exception: For other unexpected errors during the copy operation
    """
    logger.info(f"Starting file copy operation from {file_path} to {new_file_path}")
    
    # Convert to Path objects for easier manipulation
    source_path = Path(file_path)
    destination_path = Path(new_file_path)
    
    # Check if source file exists
    if not source_path.exists():
        logger.error(f"Source file does not exist: {file_path}")
        raise FileNotFoundError(file_path)
    
    # Check if source is actually a file (not a directory)
    if not source_path.is_file():
        logger.error(f"Source path is not a file: {file_path}")
        raise FileNotFoundError(file_path)
    
    try:
        # Create parent directories if they don't exist
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created parent directories for: {destination_path.parent}")
        
        # Copy the file
        shutil.copy2(source_path, destination_path)
        logger.info(f"Successfully copied file from {source_path} to {destination_path}")
        
        # Get absolute path of the copied file
        absolute_destination_path = destination_path.resolve()
        
        # Verify the copy was successful
        if not absolute_destination_path.exists():
            logger.error("File copy verification failed - destination file does not exist")
            raise FileCopyError(
                str(source_path), 
                str(destination_path), 
                "Copy operation completed but destination file was not found"
            )
        
        logger.info(f"File copy operation completed successfully: {absolute_destination_path}")
        return str(absolute_destination_path)
        
    except FileNotFoundError:
        # Re-raise our custom exceptions
        raise
    except PermissionError as e:
        logger.error(f"Permission denied during file copy: {e}")
        raise FileCopyError(str(source_path), str(destination_path), f"Permission denied: {e}")
    except OSError as e:
        logger.error(f"OS error during file copy: {e}")
        raise FileCopyError(str(source_path), str(destination_path), f"OS error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during file copy: {e}")
        raise FileCopyError(str(source_path), str(destination_path), f"Unexpected error: {e}")
