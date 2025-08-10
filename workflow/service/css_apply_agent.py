"""
CSS apply agent for applying specific theme files to main CSS files.

Provides functionality for copying theme CSS files to replace main CSS file content,
enabling theme switching in frontend projects.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from common.utils.logger import get_logger

logger = get_logger(__name__)


class ThemeFileNotFoundError(Exception):
    """Exception raised when the target theme file is not found."""

    def __init__(self, theme_file_path: str):
        self.theme_file_path = theme_file_path
        super().__init__(f"Theme file not found: {theme_file_path}")


class MainCssFileNotFoundError(Exception):
    """Exception raised when the main CSS file is not found."""

    def __init__(self, main_css_file_path: str):
        self.main_css_file_path = main_css_file_path
        super().__init__(f"Main CSS file not found: {main_css_file_path}")


class CssApplyError(Exception):
    """Exception raised when CSS theme application fails."""

    def __init__(self, error_message: str):
        self.error_message = error_message
        super().__init__(f"CSS theme application failed: {error_message}")


class CssApplyResult(BaseModel):
    """
    Result of the CSS theme application operation.
    """

    success: bool = Field(...,
                          description="Whether the theme application was successful")
    theme_file_path: str = Field(...,
                                 description="Path of the applied theme file")
    main_css_file_path: str = Field(...,
                                    description="Path of the target main CSS file")
    message: str = Field(..., description="Success or error message")

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


def css_apply_agent(
    themes_directory_path: str,
    theme_filename: str,
    main_css_file_path: str
) -> bool:
    """
    Apply a specific theme file to the main CSS file by copying its content.

    This function locates the specified theme CSS file in the themes directory
    and copies its content to replace the main CSS file content completely.
    The theme filename can be provided with or without the .css extension.

    Args:
        themes_directory_path: Path to the themes directory containing theme CSS files
        theme_filename: Name of the target theme file (with or without .css extension)
        main_css_file_path: Path to the main CSS file that will be replaced

    Returns:
        bool: True if the theme was successfully applied, False otherwise

    Raises:
        ThemeFileNotFoundError: If the target theme file cannot be found
        MainCssFileNotFoundError: If the main CSS file cannot be found
        CssApplyError: If the CSS content copying operation fails
        Exception: For other unexpected errors during the process
    """
    logger.info(f"Starting CSS theme application")
    logger.info(f"Themes directory: {themes_directory_path}")
    logger.info(f"Target theme: {theme_filename}")
    logger.info(f"Main CSS file: {main_css_file_path}")

    # Convert paths to Path objects for easier manipulation
    themes_dir = Path(themes_directory_path)
    main_css_file = Path(main_css_file_path)

    # Ensure theme filename has .css extension
    if not theme_filename.endswith('.css'):
        theme_filename = f"{theme_filename}.css"

    theme_file = themes_dir / theme_filename

    try:
        # Validate themes directory exists
        if not themes_dir.exists():
            logger.error(
                f"Themes directory does not exist: {themes_directory_path}")
            raise CssApplyError(
                f"Themes directory not found: {themes_directory_path}")

        if not themes_dir.is_dir():
            logger.error(
                f"Themes path is not a directory: {themes_directory_path}")
            raise CssApplyError(
                f"Themes path is not a directory: {themes_directory_path}")

        # Validate theme file exists
        if not theme_file.exists():
            logger.error(f"Theme file does not exist: {theme_file}")
            raise ThemeFileNotFoundError(str(theme_file))

        if not theme_file.is_file():
            logger.error(f"Theme path is not a file: {theme_file}")
            raise ThemeFileNotFoundError(str(theme_file))

        # Validate main CSS file exists
        if not main_css_file.exists():
            logger.error(f"Main CSS file does not exist: {main_css_file_path}")
            raise MainCssFileNotFoundError(main_css_file_path)

        if not main_css_file.is_file():
            logger.error(f"Main CSS path is not a file: {main_css_file_path}")
            raise MainCssFileNotFoundError(main_css_file_path)

        # Read theme file content
        logger.info(f"Reading theme file content from: {theme_file}")
        with open(theme_file, 'r', encoding='utf-8') as file:
            theme_content = file.read()

        logger.info(
            f"Successfully read theme file: {len(theme_content)} characters")

        # Write theme content to main CSS file
        logger.info(f"Writing theme content to main CSS file: {main_css_file}")
        with open(main_css_file, 'w', encoding='utf-8') as file:
            file.write(theme_content)

        logger.info("Successfully applied theme to main CSS file")
        logger.info(
            f"Theme '{theme_filename}' has been applied to '{main_css_file_path}'")

        return True

    except (ThemeFileNotFoundError, MainCssFileNotFoundError):
        # Re-raise our custom exceptions
        raise
    except OSError as e:
        error_msg = f"File operation failed: {e}"
        logger.error(error_msg)
        raise CssApplyError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error during CSS theme application: {e}"
        logger.error(error_msg)
        raise Exception(f"CSS theme application failed: {e}")


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for CSS theme application.

    Returns:
        Parsed arguments namespace containing themes_directory, theme_filename, and main_css_file

    Raises:
        SystemExit: If argument parsing fails or help is requested
    """
    parser = argparse.ArgumentParser(
        description="Apply a specific theme file to the main CSS file by copying its content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m workflow.service.css_apply_agent --themes-dir /path/to/themes --theme original --main-css /path/to/main.css
  python -m workflow.service.css_apply_agent -t ./themes -n dark_theme -m ./src/styles/globals.css
  python -m workflow.service.css_apply_agent --theme blue_ocean.css --main-css ./styles/main.css
        """
    )

    parser.add_argument(
        "--themes-dir", "-t",
        type=str,
        help=f"Path to the themes directory containing theme CSS files"
    )

    parser.add_argument(
        "--theme", "-n",
        type=str,
        help=f"Name of the target theme file (with or without .css extension)"
    )

    parser.add_argument(
        "--main-css", "-m",
        type=str,
        help=f"Path to the main CSS file that will be replaced"
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
    # Validate themes directory path
    if not args.themes_dir:
        logger.error("Themes directory path cannot be empty")
        sys.exit(1)

    # Validate theme filename
    if not args.theme:
        logger.error("Theme filename cannot be empty")
        sys.exit(1)

    # Validate main CSS file path
    if not args.main_css:
        logger.error("Main CSS file path cannot be empty")
        sys.exit(1)

    # Check if themes directory exists
    themes_dir = Path(args.themes_dir)
    if not themes_dir.exists():
        logger.error(f"Themes directory does not exist: {args.themes_dir}")
        sys.exit(1)

    if not themes_dir.is_dir():
        logger.error(f"Themes path is not a directory: {args.themes_dir}")
        sys.exit(1)

    # Check if main CSS file exists
    main_css_file = Path(args.main_css)
    if not main_css_file.exists():
        logger.error(f"Main CSS file does not exist: {args.main_css}")
        sys.exit(1)

    if not main_css_file.is_file():
        logger.error(f"Main CSS path is not a file: {args.main_css}")
        sys.exit(1)

    logger.info("Arguments validated successfully")
    logger.info(f"Themes directory: {args.themes_dir}")
    logger.info(f"Target theme: {args.theme}")
    logger.info(f"Main CSS file: {args.main_css}")


def main() -> None:
    """
    Standalone entry point to apply a specific theme to the main CSS file.

    This function parses command line arguments to get the themes directory,
    target theme filename, and main CSS file path, then invokes css_apply_agent
    to copy the theme content to the main CSS file.

    Command line arguments:
        --themes-dir, -t: Path to the themes directory (optional, has default)
        --theme, -n: Name of the target theme file (optional, has default)
        --main-css, -m: Path to the main CSS file (optional, has default)

    Raises:
        ThemeFileNotFoundError: If the target theme file cannot be found
        MainCssFileNotFoundError: If the main CSS file cannot be found
        CssApplyError: If the CSS content copying operation fails
        SystemExit: If argument parsing or validation fails
        Exception: For other unexpected errors during the process
    """
    logger.info("Standalone CSS theme application started")

    try:
        # Parse and validate command line arguments
        args = _parse_arguments()
        _validate_arguments(args)

        # Apply CSS theme with parsed arguments
        success = css_apply_agent(
            themes_directory_path=args.themes_dir,
            theme_filename=args.theme,
            main_css_file_path=args.main_css
        )

        if success:
            logger.info(
                "Standalone CSS theme application finished successfully")
        else:
            logger.error("CSS theme application failed")
            sys.exit(1)

    except (ThemeFileNotFoundError, MainCssFileNotFoundError, CssApplyError) as e:
        logger.error(f"CSS theme application failed: {e}")
        sys.exit(1)
    except SystemExit:
        # Re-raise SystemExit (from argparse or validation)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
