"""
Git utility functions for repository operations.

Provides functions for cloning GitHub repositories with automatic naming
and directory management.
"""

import hashlib
import os
import subprocess
import re
from pathlib import Path
from typing import Optional

from common.utils.logger import get_logger

logger = get_logger(__name__)


class GitCloneError(Exception):
    """Exception raised when git clone operations fail."""
    
    def __init__(self, message: str, return_code: Optional[int] = None):
        """
        Initialize GitCloneError.
        
        Args:
            message: Error message describing the failure
            return_code: Git command return code if available
        """
        super().__init__(message)
        self.return_code = return_code


def extract_repo_name_from_url(github_url: str) -> str:
    """
    Extract repository name from GitHub HTTPS URL.
    
    Args:
        github_url: GitHub repository HTTPS URL
        
    Returns:
        Repository name without .git extension
        
    Raises:
        ValueError: If URL format is invalid
    """
    if not github_url or not isinstance(github_url, str):
        raise ValueError("GitHub URL must be a non-empty string")
    
    # Match GitHub HTTPS URL pattern
    pattern = r'https://github\.com/[^/]+/([^/]+?)(?:\.git)?/?$'
    match = re.match(pattern, github_url.strip())
    
    if not match:
        raise ValueError(f"Invalid GitHub HTTPS URL format: {github_url}")
    
    return match.group(1)


def generate_hash_suffix(url: str, length: int = 6) -> str:
    """
    Generate a hash suffix for the repository directory name.
    
    Args:
        url: Repository URL to hash
        length: Length of hash suffix (default: 6)
        
    Returns:
        Hexadecimal hash string of specified length
    """
    if length <= 0:
        raise ValueError("Hash length must be positive")
    
    hash_object = hashlib.md5(url.encode('utf-8'))
    return hash_object.hexdigest()[:length]


def clone_github_repo(github_url: str, workspace_root: Optional[str] = None) -> str:
    """
    Clone a GitHub repository to the workspace directory.
    
    This function clones a GitHub repository using HTTPS URL and places it
    in the workspace directory with a unique name consisting of the repository
    name plus a 6-character hash suffix.
    
    Args:
        github_url: GitHub repository HTTPS URL (e.g., "https://github.com/user/repo.git")
        workspace_root: Root directory path. If None, uses project root's workspace folder
        
    Returns:
        Absolute path to the cloned repository directory
        
    Raises:
        GitCloneError: If git clone operation fails
        ValueError: If GitHub URL format is invalid
        OSError: If workspace directory operations fail
    """
    logger.info(f"Starting GitHub repository clone: {github_url}")
    
    try:
        # Extract repository name from URL
        repo_name = extract_repo_name_from_url(github_url)
        logger.debug(f"Extracted repository name: {repo_name}")
        
        # Generate hash suffix
        hash_suffix = generate_hash_suffix(github_url)
        logger.debug(f"Generated hash suffix: {hash_suffix}")
        
        # Create directory name with hash
        dir_name = f"{repo_name}-{hash_suffix}"
        
        # Determine workspace directory
        if workspace_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            workspace_dir = project_root / "workspace"
        else:
            workspace_dir = Path(workspace_root) / "workspace"
        
        # Ensure workspace directory exists
        workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Workspace directory: {workspace_dir}")
        
        # Target directory for clone
        target_dir = workspace_dir / dir_name
        
        # Check if directory already exists
        if target_dir.exists():
            logger.warning(f"Target directory already exists: {target_dir}")
            logger.warning("Removing existing directory before cloning")
            import shutil
            shutil.rmtree(target_dir)
        
        # Execute git clone command
        logger.info(f"Cloning repository to: {target_dir}")
        
        try:
            result = subprocess.run(
                ["git", "clone", github_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"Git clone failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                logger.error(error_msg)
                raise GitCloneError(error_msg, result.returncode)
                
            logger.info(f"Successfully cloned repository to: {target_dir}")
            
            # Verify the clone was successful
            if not target_dir.exists() or not any(target_dir.iterdir()):
                raise GitCloneError("Clone completed but target directory is empty")
                
            return str(target_dir.absolute())
            
        except subprocess.TimeoutExpired:
            error_msg = "Git clone operation timed out after 5 minutes"
            logger.error(error_msg)
            raise GitCloneError(error_msg)
            
        except FileNotFoundError:
            error_msg = "Git command not found. Please ensure Git is installed and in PATH"
            logger.error(error_msg)
            raise GitCloneError(error_msg)
            
    except ValueError as e:
        logger.error(f"Invalid GitHub URL: {e}")
        raise
        
    except OSError as e:
        error_msg = f"File system operation failed: {e}"
        logger.error(error_msg)
        raise GitCloneError(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error during git clone: {e}"
        logger.error(error_msg)
        raise GitCloneError(error_msg)
