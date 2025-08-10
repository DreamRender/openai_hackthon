"""
Main workflow service for handling GitHub repository operations.

Provides a centralized workflow class for orchestrating GitHub repository
cloning and related operations.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from common.utils.logger import get_logger
from common.utils.git_utils import clone_github_repo, GitCloneError
from workflow.service.code_analyze_agent import code_analyze_agent, PackageJsonNotFoundError, FrontendProjectAnalysis
from workflow.service.code_init_agent import code_init_agent, DirectoryNotFoundError, PermissionError as CodeInitPermissionError, CodeInitResult
from workflow.service.css_analyze_agent import css_analyze_agent, CssFileNotFoundError, CssAnalysisResult, css_theme_summary_generator, CssThemeFileNotFoundError, ThemeJsonWriteError
from workflow.service.code_act_agent import code_act_agent, CodeActFileNotFoundError
from workflow.service.code_run_agent import (
    code_run_npm_install,
    NpmInstallError,
    code_run_build_with_fix,
    BuildMaxIterationsError,
    code_run_start_dev_server,
    DevServerStartError,
    PortKillError,
    DevServerInfo,
)
from workflow.service.code_file_agent import code_file_agent, FileCopyError
from workflow.service.css_generator_agent import css_generator_agent, CssFileReadError, ThemesDirectoryError, ThemeGenerationError

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
            raise ValueError(
                "GitHub repository URL must be a non-empty string")
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
            logger.info(
                f"Start command identified: {analysis_result.start_command}")
        if analysis_result.build_command:
            logger.info(
                f"Build command identified: {analysis_result.build_command}")
        if analysis_result.eslint_fix_command:
            logger.info(
                f"ESLint fix command identified: {analysis_result.eslint_fix_command}")
        if analysis_result.ui_frameworks_info:
            logger.info(
                f"UI frameworks detected: {analysis_result.ui_frameworks_info}")

        logger.info("Stage 3 completed: Project analysis")
        return analysis_result

    def _initialize_project(self, cloned_path: str) -> CodeInitResult:
        """
        Stage 4: Initialize project development environment.

        Args:
            cloned_path: Path to the cloned repository

        Returns:
            CodeInitResult: Project initialization results containing directory paths

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
            logger.error(
                f"Unexpected error during project initialization: {e}")
            raise

        if not init_result.success:
            logger.error(
                f"Project initialization failed: {init_result.message}")
            raise Exception(
                f"Project initialization failed: {init_result.message}")

        logger.info("Project initialization completed successfully")
        logger.info(
            f"Design directory created: {init_result.design_directory_path}")
        logger.info(
            f"Themes directory created: {init_result.themes_directory_path}")
        logger.info("Stage 4 completed: Project initialization")
        return init_result

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
        logger.info(
            "Stage 6: Processing color theme extraction and centralization")

        try:
            code_act_agent(
                directory_path=cloned_path,
                css_analysis_result=css_result,
                frontend_analysis=analysis_result
            )
        except CodeActFileNotFoundError:
            logger.error("No frontend files found for color theme processing")
            raise Exception(
                "Frontend projects must contain tsx/jsx/html files for theme processing")
        except Exception as e:
            logger.error(f"Color theme processing failed: {e}")
            raise

        logger.info("Color theme processing completed successfully")
        logger.info(
            "All frontend files have been processed for color centralization")
        logger.info(
            "CSS variables have been created and applied throughout the project")
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
            logger.error(
                f"Unexpected error during dependency installation: {e}")
            raise

        logger.info("Dependency installation completed successfully")
        logger.info("All project dependencies have been installed")
        logger.info("Stage 7 completed: Dependency installation")

    def _build_with_fix(self, cloned_path: str, analysis_result: FrontendProjectAnalysis) -> None:
        """
        Stage 8: Build project and automatically fix errors if build fails.

        Args:
            cloned_path: Path to the cloned repository
            analysis_result: Frontend project analysis results containing build commands

        Raises:
            BuildMaxIterationsError: If build fix iterations exceed maximum limit
            Exception: If build or fix process fails
        """
        logger.info("Stage 8: Building project with automatic fix on failures")
        logger.info(f"Building in directory: {cloned_path}")

        try:
            code_run_build_with_fix(analysis_result, cloned_path)
            logger.info("Build and automatic fix stage completed successfully")
            logger.info("Stage 8 completed: Build with fix")
        except BuildMaxIterationsError as e:
            logger.error(f"Build fix exceeded maximum iterations: {e}")
            raise
        except Exception as e:
            logger.error(f"Build with fix failed: {e}")
            raise

    def _backup_original_css(
        self,
        cloned_path: str,
        css_result: CssAnalysisResult,
        init_result: CodeInitResult
    ) -> str:
        """
        Stage 9: Backup original main CSS file to themes directory.

        Args:
            cloned_path: Path to the cloned repository
            css_result: CSS analysis results containing main CSS file path
            init_result: Project initialization results containing themes directory path

        Returns:
            str: Absolute path to the backed up CSS file

        Raises:
            FileCopyError: If CSS file copy operation fails
            Exception: If CSS backup fails
        """
        logger.info("Stage 9: Backing up original main CSS file")

        # Construct source CSS file path
        source_css_path = Path(cloned_path) / css_result.main_css_path

        # Get CSS file extension for the backup
        css_file_extension = source_css_path.suffix

        # Construct destination path in themes directory
        destination_css_path = Path(
            init_result.themes_directory_path) / f"original{css_file_extension}"

        logger.info(f"Copying main CSS file from: {source_css_path}")
        logger.info(f"Copying main CSS file to: {destination_css_path}")

        try:
            backup_path = code_file_agent(
                file_path=str(source_css_path),
                new_file_path=str(destination_css_path)
            )
            logger.info(
                f"Successfully backed up original CSS file to: {backup_path}")
        except FileCopyError as e:
            logger.error(f"CSS file backup failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during CSS backup: {e}")
            raise

        logger.info("CSS backup completed successfully")
        logger.info(
            f"Original CSS file preserved as: original{css_file_extension}")
        logger.info("Stage 9 completed: CSS backup")
        return backup_path

    def _generate_original_theme_summary(
        self,
        backed_up_css_path: str,
        init_result: CodeInitResult
    ) -> None:
        """
        Stage 10: Generate theme summary JSON for the original CSS file.

        Args:
            backed_up_css_path: Absolute path to the backed up CSS file
            init_result: Project initialization results containing themes directory path

        Raises:
            CssThemeFileNotFoundError: If the backed up CSS file is not found
            ThemeJsonWriteError: If JSON file writing fails
            Exception: If theme summary generation fails
        """
        logger.info("Stage 10: Generating original theme summary JSON")

        # Construct JSON output path
        json_output_path = Path(
            init_result.themes_directory_path) / "original.json"

        logger.info(f"Analyzing CSS file: {backed_up_css_path}")
        logger.info(f"Generating JSON summary to: {json_output_path}")

        try:
            css_theme_summary_generator(
                css_file_path=backed_up_css_path,
                json_file_path=str(json_output_path)
            )
            logger.info("Successfully generated original theme summary JSON")
        except (CssThemeFileNotFoundError, ThemeJsonWriteError) as e:
            logger.error(f"Theme summary generation failed: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during theme summary generation: {e}")
            raise

        logger.info("Original theme summary generation completed successfully")
        logger.info(f"Theme summary saved to: {json_output_path}")
        logger.info("Stage 10 completed: Original theme summary generation")

    def _generate_additional_themes(
        self,
        backed_up_css_path: str,
        init_result: CodeInitResult
    ) -> None:
        """
        Stage 11: Generate additional color theme variations using the backed up CSS.

        Args:
            backed_up_css_path: Absolute path to the backed up CSS file
            init_result: Project initialization results containing themes directory path

        Raises:
            CssFileReadError: If the backed up CSS file cannot be read
            ThemesDirectoryError: If themes directory operations fail
            ThemeGenerationError: If theme generation fails
            Exception: If additional theme generation fails
        """
        logger.info("Stage 11: Generating additional color theme variations")

        logger.info(f"Using backed up CSS file: {backed_up_css_path}")
        logger.info(
            f"Generating themes in directory: {init_result.themes_directory_path}")

        try:
            css_generator_agent(
                themes_directory_path=init_result.themes_directory_path,
                original_css_file_path=backed_up_css_path
            )
            logger.info("Successfully generated additional theme variations")
        except (CssFileReadError, ThemesDirectoryError, ThemeGenerationError) as e:
            logger.error(f"Additional theme generation failed: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during additional theme generation: {e}")
            raise

        logger.info("Additional theme generation completed successfully")
        logger.info("5 new color theme variations have been created")
        logger.info("Stage 11 completed: Additional theme generation")

    def _start_development_server(
        self,
        cloned_path: str,
        analysis_result: FrontendProjectAnalysis,
        hostname: str = "0.0.0.0",
        port: int = 3000
    ) -> DevServerInfo:
        """
        Stage 12: Start the frontend development server in background.

        Args:
            cloned_path: Path to the cloned repository
            analysis_result: Frontend project analysis results containing start command
            hostname: Hostname to bind the server to (default: "0.0.0.0")
            port: Port number to use for the server (default: 3000)

        Returns:
            DevServerInfo: Information about the running server (hostname and port)

        Raises:
            PortKillError: If unable to kill existing processes on the port
            DevServerStartError: If the development server fails to start
            Exception: If development server startup fails or no start command available
        """
        logger.info("Stage 12: Starting frontend development server")

        # Check if start command is available
        if not analysis_result.start_command:
            logger.error("No start command found in frontend analysis")
            raise Exception("No start command available for this project")

        logger.info(f"Using start command: {analysis_result.start_command}")
        logger.info(f"Server will be started at {hostname}:{port}")

        try:
            server_info = code_run_start_dev_server(
                start_command=analysis_result.start_command,
                directory_path=cloned_path,
                hostname=hostname,
                port=port
            )

            logger.info("Development server started successfully")
            logger.info(f"Server is running at http://{server_info.hostname}:{server_info.port}")
            logger.info("Server is running in background thread (daemon mode)")
            logger.info("Stage 12 completed: Development server startup")

            return server_info

        except (PortKillError, DevServerStartError) as e:
            logger.error(f"Development server startup failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during development server startup: {e}")
            raise

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
        8. Builds project and automatically fixes build errors if needed
        9. Backs up original main CSS file to themes directory
        10. Generates theme summary JSON for the original CSS file
        11. Generates 5 additional color theme variations
        12. Starts the frontend development server in background

        This function serves as the central entry point for the automated
        repository processing workflow and handles all stages of project setup,
        theme system implementation, dependency installation, CSS backup,
        theme summary generation, additional theme creation, and development server startup.

        Args:
            github_repo_url: GitHub repository HTTPS URL to clone and process

        Raises:
            ValueError: If the GitHub URL format is invalid
            GitCloneError: If the repository cloning fails
            NpmInstallError: If npm install operation fails
            BuildMaxIterationsError: If build fix iterations exceed maximum limit
            FileCopyError: If CSS file backup fails
            CssThemeFileNotFoundError: If backed up CSS file is not found
            ThemeJsonWriteError: If theme summary JSON writing fails
            CssFileReadError: If original CSS file cannot be read for theme generation
            ThemesDirectoryError: If themes directory operations fail
            ThemeGenerationError: If additional theme generation fails
            PortKillError: If unable to kill existing processes on the port
            DevServerStartError: If the development server fails to start
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
            init_result = self._initialize_project(cloned_path)
            css_result = self._analyze_css(cloned_path)
            self._process_color_theme(cloned_path, css_result, analysis_result)
            self._install_dependencies(cloned_path)
            self._build_with_fix(cloned_path, analysis_result)
            backed_up_css_path = self._backup_original_css(
                cloned_path, css_result, init_result)
            self._generate_original_theme_summary(
                backed_up_css_path, init_result)
            self._generate_additional_themes(backed_up_css_path, init_result)
            server_info = self._start_development_server(cloned_path, analysis_result)

            # Workflow completion
            logger.info("=" * 60)
            logger.info("MAIN WORKFLOW COMPLETED SUCCESSFULLY")
            logger.info("All stages completed: Repository processed with color theme system, dependencies installed, original CSS backed up, theme summary generated, additional themes created, and development server started")
            logger.info(f"Development server is running at http://{server_info.hostname}:{server_info.port}")
            logger.info("=" * 60)

        except (ValueError, GitCloneError, NpmInstallError, BuildMaxIterationsError, FileCopyError, CssThemeFileNotFoundError, ThemeJsonWriteError, CssFileReadError, ThemesDirectoryError, ThemeGenerationError, PortKillError, DevServerStartError) as e:
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


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for main workflow.

    Returns:
        Parsed arguments namespace containing github_repo_url and workspace_root

    Raises:
        SystemExit: If argument parsing fails or help is requested
    """
    parser = argparse.ArgumentParser(
        description="Main workflow for processing GitHub repositories with color theme generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m workflow.service.main https://github.com/user/repo.git
  python -m workflow.service.main --repo https://github.com/user/repo.git --workspace /custom/workspace
  python -m workflow.service.main -r https://github.com/user/repo.git -w ./my_workspace
        """
    )

    parser.add_argument(
        "github_repo_url",
        nargs="?",
        type=str,
        help="GitHub repository HTTPS URL to clone and process"
    )

    parser.add_argument(
        "--repo", "-r",
        type=str,
        dest="github_repo_url",
        help="GitHub repository HTTPS URL to clone and process (alternative to positional argument)"
    )

    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=None,
        help="Custom workspace root directory (optional, uses default if not specified)"
    )

    return parser.parse_args()


def _validate_arguments(args: argparse.Namespace) -> None:
    """
    Validate command line arguments.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If validation fails
    """
    # Check if GitHub repository URL is provided
    if not args.github_repo_url:
        logger.error("GitHub repository URL is required")
        logger.error("Use: python -m workflow.service.main <github_repo_url>")
        logger.error(
            "Or: python -m workflow.service.main --repo <github_repo_url>")
        sys.exit(1)

    # Validate GitHub URL format
    if not isinstance(args.github_repo_url, str) or not args.github_repo_url.strip():
        logger.error("GitHub repository URL must be a non-empty string")
        sys.exit(1)

    # Basic GitHub URL validation
    github_url = args.github_repo_url.strip()
    if not (github_url.startswith("https://github.com/") and github_url.endswith(".git")):
        logger.warning(
            "GitHub URL should be in HTTPS format and end with .git")
        logger.warning(f"Example: https://github.com/user/repo.git")
        logger.warning(f"Provided: {github_url}")

    # Validate workspace path if provided
    if args.workspace:
        workspace_path = Path(args.workspace)
        if workspace_path.exists() and not workspace_path.is_dir():
            logger.error(
                f"Workspace path exists but is not a directory: {args.workspace}")
            sys.exit(1)

    logger.info("Arguments validated successfully")
    logger.info(f"GitHub repository: {args.github_repo_url}")
    if args.workspace:
        logger.info(f"Custom workspace: {args.workspace}")
    else:
        logger.info("Using default workspace directory")


if __name__ == "__main__":
    """
    Entry point for direct script execution.

    When this module is run directly, it parses command line arguments
    and executes the complete main workflow for GitHub repository processing.

    Command line arguments:
        github_repo_url: GitHub repository HTTPS URL (positional or --repo/-r)
        --workspace, -w: Custom workspace root directory (optional)
    """
    logger.info("Main workflow module execution started")

    try:
        # Parse and validate command line arguments
        args = _parse_arguments()
        _validate_arguments(args)

        # Initialize workflow with optional custom workspace
        workflow = MainWorkflow(workspace_root=args.workspace)

        # Execute the complete workflow pipeline
        workflow.main(args.github_repo_url)
        logger.info("Workflow execution completed successfully")

    except SystemExit:
        # Re-raise SystemExit (from argparse or validation)
        raise
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        sys.exit(1)

    logger.info("Main workflow module execution finished")
