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
from workflow.service.css_analyze_agent import css_analyze_agent, CssFileNotFoundError, CssAnalysisResult
from workflow.service.code_act_agent import code_act_agent, CodeActFileNotFoundError
from workflow.service.code_run_agent import code_run_npm_install, NpmInstallError

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

    def _validate_input(self, github_repo_url: str) -> None:
        """
        Stage 1: Validate input parameters.
        
        Args:
            github_repo_url: GitHub repository HTTPS URL to validate
            
        Raises:
            ValueError: If the GitHub URL format is invalid
        """
        logger.info("Stage 1: Validating input parameters")
        if not github_repo_url or not isinstance(github_repo_url, str):
            logger.error("GitHub repository URL must be a non-empty string")
            raise ValueError("GitHub repository URL must be a non-empty string")
        logger.info("Input validation completed successfully")

    def _clone_repository(self, github_repo_url: str) -> str:
        """
        Stage 2: Clone GitHub repository.
        
        Args:
            github_repo_url: GitHub repository HTTPS URL to clone
            
        Returns:
            str: Path to the cloned repository
            
        Raises:
            GitCloneError: If the repository cloning fails
        """
        logger.info("Stage 2: Cloning GitHub repository")
        logger.info(f"Cloning from: {github_repo_url}")

        try:
            cloned_path = clone_github_repo(
                github_url=github_repo_url,
                workspace_root=self.workspace_root
            )
            logger.info(f"Repository cloned successfully to: {cloned_path}")
            logger.info("Stage 2 completed: Repository cloning")
            return cloned_path
        except GitCloneError as e:
            logger.error(f"Git clone failed: {e}")
            raise

    def _analyze_project(self, cloned_path: str) -> FrontendProjectAnalysis:
        """
        Stage 3: Analyze project structure and type.
        
        Args:
            cloned_path: Path to the cloned repository
            
        Returns:
            FrontendProjectAnalysis: Analysis results
            
        Raises:
            PackageJsonNotFoundError: If no package.json file is found
            Exception: If project analysis fails or project is not frontend
        """
        logger.info("Stage 3: Analyzing project structure and type")
        
        try:
            analysis_result = code_analyze_agent(cloned_path)
        except PackageJsonNotFoundError:
            logger.error("No package.json found - cannot analyze project type")
            raise Exception("Frontend projects must have a package.json file")
        except Exception as e:
            logger.error(f"Project analysis failed: {e}")
            raise

        # Check if it's a frontend project
        if not analysis_result.is_frontend_project:
            logger.error("Non-frontend projects are not supported")
            raise Exception("This workflow only supports frontend projects")

        # Log frontend project details
        logger.info("Project type: Frontend project detected")
        if analysis_result.start_command:
            logger.info(f"Start command identified: {analysis_result.start_command}")
        if analysis_result.build_command:
            logger.info(f"Build command identified: {analysis_result.build_command}")
        if analysis_result.eslint_fix_command:
            logger.info(f"ESLint fix command identified: {analysis_result.eslint_fix_command}")
        if analysis_result.ui_frameworks_info:
            logger.info(f"UI frameworks detected: {analysis_result.ui_frameworks_info}")

        logger.info("Stage 3 completed: Project analysis")
        return analysis_result

    def _initialize_project(self, cloned_path: str) -> None:
        """
        Stage 4: Initialize project development environment.
        
        Args:
            cloned_path: Path to the cloned repository
            
        Raises:
            DirectoryNotFoundError: If cloned directory is not accessible
            CodeInitPermissionError: If project initialization fails
        """
        logger.info("Stage 4: Initializing project development environment")
        
        try:
            init_result = code_init_agent(cloned_path)
        except (DirectoryNotFoundError, CodeInitPermissionError) as e:
            logger.error(f"Project initialization failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during project initialization: {e}")
            raise

        if not init_result.success:
            logger.error(f"Project initialization failed: {init_result.message}")
            raise Exception(f"Project initialization failed: {init_result.message}")

        logger.info("Project initialization completed successfully")
        logger.info(f"Design directory created: {init_result.design_directory_path}")
        logger.info(f"Themes directory created: {init_result.themes_directory_path}")
        logger.info("Stage 4 completed: Project initialization")

    def _analyze_css(self, cloned_path: str) -> CssAnalysisResult:
        """
        Stage 5: Analyze CSS structure and identify main CSS file.
        
        Args:
            cloned_path: Path to the cloned repository
            
        Returns:
            CssAnalysisResult: CSS analysis results
            
        Raises:
            CssFileNotFoundError: If no CSS files are found
            Exception: If CSS analysis fails or no main CSS file can be identified
        """
        logger.info("Stage 5: Analyzing CSS structure")
        
        try:
            css_result = css_analyze_agent(cloned_path)
        except CssFileNotFoundError:
            logger.error("No CSS files found in the project")
            raise Exception("Frontend projects must contain CSS files")
        except Exception as e:
            logger.error(f"CSS analysis failed: {e}")
            raise

        logger.info("CSS analysis completed successfully")
        logger.info(f"Main CSS file identified: {css_result.main_css_path}")
        logger.info("Stage 5 completed: CSS analysis")
        return css_result

    def _process_color_theme(
        self, 
        cloned_path: str, 
        css_result: CssAnalysisResult, 
        analysis_result: FrontendProjectAnalysis
    ) -> None:
        """
        Stage 6: Process frontend files for color theme extraction and centralization.
        
        Args:
            cloned_path: Path to the cloned repository
            css_result: CSS analysis results containing main CSS file information
            analysis_result: Frontend project analysis results
            
        Raises:
            CodeActFileNotFoundError: If no frontend files are found
            Exception: If color theme processing fails
        """
        logger.info("Stage 6: Processing color theme extraction and centralization")
        
        try:
            code_act_agent(
                directory_path=cloned_path,
                css_analysis_result=css_result,
                frontend_analysis=analysis_result
            )
        except CodeActFileNotFoundError:
            logger.error("No frontend files found for color theme processing")
            raise Exception("Frontend projects must contain tsx/jsx/html files for theme processing")
        except Exception as e:
            logger.error(f"Color theme processing failed: {e}")
            raise

        logger.info("Color theme processing completed successfully")
        logger.info("All frontend files have been processed for color centralization")
        logger.info("CSS variables have been created and applied throughout the project")
        logger.info("Stage 6 completed: Color theme processing")

    def _install_dependencies(self, cloned_path: str) -> None:
        """
        Stage 7: Install project dependencies using npm install.
        
        Args:
            cloned_path: Path to the cloned repository
            
        Raises:
            NpmInstallError: If npm install operation fails
            Exception: If dependency installation fails
        """
        logger.info("Stage 7: Installing project dependencies")
        
        try:
            code_run_npm_install(cloned_path)
        except NpmInstallError as e:
            logger.error(f"npm install failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during dependency installation: {e}")
            raise

        logger.info("Dependency installation completed successfully")
        logger.info("All project dependencies have been installed")
        logger.info("Stage 7 completed: Dependency installation")

    def main(self, github_repo_url: str) -> None:
        """
        Main workflow orchestrator for complete GitHub repository processing.

        This is the primary workflow function that orchestrates the complete
        processing pipeline for a GitHub repository:
        1. Validates input parameters
        2. Clones the repository to workspace
        3. Analyzes project structure and type (must be frontend)
        4. Initializes project development environment
        5. Analyzes CSS structure and identifies main CSS file
        6. Processes frontend files for color theme extraction and centralization
        7. Installs project dependencies using npm install

        This function serves as the central entry point for the automated
        repository processing workflow and handles all stages of project setup,
        theme system implementation, and dependency installation.

        Args:
            github_repo_url: GitHub repository HTTPS URL to clone and process

        Raises:
            ValueError: If the GitHub URL format is invalid
            GitCloneError: If the repository cloning fails
            NpmInstallError: If npm install operation fails
            Exception: If any stage fails (project must be frontend with CSS and frontend files)
        """
        logger.info("=" * 60)
        logger.info("MAIN WORKFLOW STARTED")
        logger.info("=" * 60)
        logger.info(f"Processing repository: {github_repo_url}")

        try:
            # Execute each stage with early return on failure
            self._validate_input(github_repo_url)
            cloned_path = self._clone_repository(github_repo_url)
            analysis_result = self._analyze_project(cloned_path)
            self._initialize_project(cloned_path)
            css_result = self._analyze_css(cloned_path)
            self._process_color_theme(cloned_path, css_result, analysis_result)
            self._install_dependencies(cloned_path)

            # Workflow completion
            logger.info("=" * 60)
            logger.info("MAIN WORKFLOW COMPLETED SUCCESSFULLY")
            logger.info("All stages completed: Repository processed with color theme system and dependencies installed")
            logger.info("=" * 60)

        except (ValueError, GitCloneError, NpmInstallError) as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise

        except Exception as e:
            logger.error("=" * 60)
            logger.error("MAIN WORKFLOW FAILED: Unexpected error")
            logger.error(f"Error details: {e}")
            logger.error("=" * 60)
            raise


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
        workflow.main(
            "https://github.com/DreamRender/openai_hackthon_nextjs_test_1.git")
        logger.info("Workflow execution completed successfully")

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")

    logger.info("Main workflow module execution finished")
