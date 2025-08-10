"""
Main workflow service for handling GitHub repository operations.

Provides a centralized workflow class for orchestrating GitHub repository
cloning and related operations.
"""

from typing import Optional

from common.utils.logger import get_logger
from common.utils.git_utils import clone_github_repo, GitCloneError
from workflow.service.code_analyze_agent import code_analyze_agent, PackageJsonNotFoundError, FrontendProjectAnalysis
from workflow.service.code_init_agent import code_init_agent, DirectoryNotFoundError, PermissionError as CodeInitPermissionError

logger = get_logger(__name__)


class MainWorkflow:
    """
    Main workflow class for GitHub repository operations.

    This class provides high-level workflow methods for handling GitHub
    repository operations such as cloning, processing, and management.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        """
        Initialize MainWorkflow.

        Args:
            workspace_root: Optional custom workspace root directory.
                           If None, uses the default project workspace.
        """
        self.workspace_root = workspace_root
        logger.info("MainWorkflow initialized")

    def main(self, github_repo_url: str) -> None:
        """
        Main workflow orchestrator for complete GitHub repository processing.

        This is the primary workflow function that orchestrates the complete
        processing pipeline for a GitHub repository:
        1. Clones the repository to workspace
        2. Analyzes project structure and type (including ESLint configuration)
        3. Initializes project development environment
        
        This function serves as the central entry point for the automated
        repository processing workflow and handles all stages of project setup.

        Args:
            github_repo_url: GitHub repository HTTPS URL to clone and process

        Raises:
            GitCloneError: If the repository cloning fails
            ValueError: If the GitHub URL format is invalid
            DirectoryNotFoundError: If cloned directory is not accessible
            CodeInitPermissionError: If project initialization fails
        """
        logger.info("=" * 60)
        logger.info("MAIN WORKFLOW STARTED")
        logger.info("=" * 60)
        logger.info(f"Processing repository: {github_repo_url}")

        try:
            # Stage 1: Input validation
            logger.info("Stage 1: Validating input parameters")
            if not github_repo_url or not isinstance(github_repo_url, str):
                raise ValueError(
                    "GitHub repository URL must be a non-empty string")
            logger.info("Input validation completed successfully")

            # Stage 2: Repository cloning
            logger.info("Stage 2: Cloning GitHub repository")
            logger.info(f"Cloning from: {github_repo_url}")

            cloned_path = clone_github_repo(
                github_url=github_repo_url,
                workspace_root=self.workspace_root
            )

            logger.info(f"Repository cloned successfully to: {cloned_path}")
            logger.info("Stage 2 completed: Repository cloning")
            
            # Stage 3: Project analysis
            logger.info("Stage 3: Analyzing project structure and type")
            try:
                analysis_result = code_analyze_agent(cloned_path)
                
                if analysis_result.is_frontend_project:
                    logger.info("Project type: Frontend project detected")
                    if analysis_result.start_command:
                        logger.info(f"Start command identified: {analysis_result.start_command}")
                    if analysis_result.build_command:
                        logger.info(f"Build command identified: {analysis_result.build_command}")
                    if analysis_result.eslint_fix_command:
                        logger.info(f"ESLint fix command identified: {analysis_result.eslint_fix_command}")
                    if analysis_result.ui_frameworks_info:
                        logger.info(f"UI frameworks detected: {analysis_result.ui_frameworks_info}")
                else:
                    logger.info("Project type: Not a frontend project")
                
                logger.info("Stage 3 completed: Project analysis")
                
                # Stage 4: Project environment initialization
                logger.info("Stage 4: Initializing project development environment")
                try:
                    init_result = code_init_agent(cloned_path)
                    
                    if init_result.success:
                        logger.info("Project initialization completed successfully")
                        logger.info(f"Design directory created: {init_result.design_directory_path}")
                        logger.info(f"Themes directory created: {init_result.themes_directory_path}")
                        logger.info("Stage 4 completed: Project initialization")
                    else:
                        logger.error(f"Project initialization failed: {init_result.message}")
                        
                except (DirectoryNotFoundError, CodeInitPermissionError) as e:
                    logger.error(f"Project initialization failed: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error during project initialization: {e}")
                    raise
                
            except PackageJsonNotFoundError:
                logger.warning("No package.json found - proceeding with basic project initialization")
                
                # Still initialize the project structure even without package.json
                logger.info("Stage 4: Initializing basic project structure")
                try:
                    init_result = code_init_agent(cloned_path)
                    
                    if init_result.success:
                        logger.info("Basic project initialization completed successfully")
                        logger.info(f"Design directory created: {init_result.design_directory_path}")
                        logger.info(f"Themes directory created: {init_result.themes_directory_path}")
                        logger.info("Stage 4 completed: Basic project initialization")
                    
                except (DirectoryNotFoundError, CodeInitPermissionError) as e:
                    logger.error(f"Basic project initialization failed: {e}")
                    raise
            
            except Exception as e:
                logger.error(f"Project analysis failed: {e}")
                raise
            
            # Workflow completion
            logger.info("=" * 60)
            logger.info("MAIN WORKFLOW COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)

        except GitCloneError as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED: Git clone error")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise

        except ValueError as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED: Invalid input")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise

        except (DirectoryNotFoundError, CodeInitPermissionError) as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED: Project initialization error")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise

        except Exception as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED: Unexpected error")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise Exception(f"Main workflow failed: {e}")


if __name__ == "__main__":
    """
    Entry point for direct script execution.

    When this module is run directly, it executes the complete main workflow
    for demonstration and testing purposes.
    """
    logger.info("Main workflow module execution started")

    workflow = MainWorkflow()
    try:
        # Execute the complete workflow pipeline
        workflow.main("https://github.com/DreamRender/openai_hackthon_nextjs_test_1.git")
        logger.info("Workflow execution completed successfully")
            
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")

    logger.info("Main workflow module execution finished")
