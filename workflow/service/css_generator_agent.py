"""
CSS generator agent for creating multiple color theme variations.

Provides functionality for generating new CSS color themes based on existing
CSS files and theme information using OpenAI LLM integration.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI
from pydantic import BaseModel, Field

from common.config.config import get_workflow_config
from common.utils.logger import get_logger


logger = get_logger(__name__)

# Default paths for standalone execution
DEFAULT_THEMES_DIRECTORY_PATH = \
    "/workspace/ui-agent/workspace/openai_hackthon_nextjs_test_1-3d173a/.design/themes"
DEFAULT_ORIGINAL_CSS_FILE_PATH = \
    "/workspace/ui-agent/workspace/openai_hackthon_nextjs_test_1-3d173a/.design/themes/original.css"

# Prompt for OpenAI CSS theme generation
CSS_THEME_GENERATION_PROMPT = """
You are a CSS theme design expert. Your task is to generate 5 new color theme variations based on an original CSS file and existing theme information.

Your objectives:
1. Analyze the provided original CSS file to understand its structure and color usage patterns
2. Review the existing theme JSON files to understand current color palettes and avoid similar combinations
3. Generate 5 completely new and distinct color theme variations with unique color schemes
4. For each new theme, create both a modified CSS file and a corresponding JSON description

CRITICAL: Color Uniqueness Requirements:
- Carefully analyze the representative colors from ALL existing themes
- Ensure each new theme uses a COMPLETELY DIFFERENT color palette from existing themes
- Avoid similar color combinations, hues, or saturation levels that already exist
- Create truly unique and distinguishable color schemes
- Each of the 5 new themes must also be distinct from each other
- Consider color theory: complementary, triadic, analogous, and monochromatic schemes
- Use different color temperatures (warm vs cool) and brightness levels

Key requirements for CSS generation:
- ONLY modify color values (hex, rgb, rgba, hsl, hsla, named colors, CSS variables)
- Maintain ALL other CSS properties exactly as they are (margins, paddings, fonts, layouts, etc.)
- Preserve the exact same CSS structure, selectors, and non-color properties
- Ensure the modified CSS maintains the same visual layout and functionality
- Use harmonious and professional color schemes for each variation
- Make each theme visually distinct from the original and from each other

Key requirements for filename generation:
- Generate unique filenames that don't conflict with existing JSON files
- Use descriptive names that reflect the unique color scheme (e.g., "coral_sunset", "emerald_forest", "royal_purple")
- Use lowercase with underscores for consistency
- The same filename will be used for both CSS and JSON files (different extensions)

Key requirements for JSON descriptions:
- Generate a descriptive title that captures the essence of the unique color theme
- Extract 3-6 representative colors from the generated CSS in HEX format
- Titles should be user-friendly and suitable for theme selection interface
- Each theme should have a unique and meaningful title that reflects its distinctive color palette

Generate 5 diverse and UNIQUE theme variations such as:
- Unique color families not represented in existing themes
- Distinctive saturation and brightness combinations
- Novel color temperature combinations
- Creative color harmonies (split-complementary, tetradic, etc.)
- Thematic color schemes (nature-inspired, cosmic, vintage, neon, etc.)

Response format: Return a JSON array with 5 theme objects, each containing filename, CSS content, and theme description.
"""


class CssFileReadError(Exception):
    """Exception raised when CSS file reading fails."""
    
    def __init__(self, css_file_path: str, error_message: str):
        self.css_file_path = css_file_path
        self.error_message = error_message
        super().__init__(f"Failed to read CSS file {css_file_path}: {error_message}")


class ThemesDirectoryError(Exception):
    """Exception raised when themes directory operations fail."""
    
    def __init__(self, themes_directory: str, error_message: str):
        self.themes_directory = themes_directory
        self.error_message = error_message
        super().__init__(f"Themes directory error in {themes_directory}: {error_message}")


class ThemeGenerationError(Exception):
    """Exception raised when theme generation fails."""
    
    def __init__(self, error_message: str):
        self.error_message = error_message
        super().__init__(f"Theme generation failed: {error_message}")


class ExistingThemeInfo(BaseModel):
    """
    Pydantic model for existing theme information.
    
    This model represents information about existing themes
    found in the themes directory.
    """
    
    filename: str = Field(
        ...,
        description="The filename of the existing theme JSON file (without extension)"
    )
    content: Dict[str, Any] = Field(
        ...,
        description="The JSON content of the existing theme file"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class GeneratedTheme(BaseModel):
    """
    Pydantic model for generated theme results from OpenAI.
    
    This model defines the structure of each theme generated by OpenAI
    for new color theme variations.
    """
    
    filename: str = Field(
        ...,
        description="Unique filename for the theme (without extension, used for both CSS and JSON)"
    )
    css_content: str = Field(
        ...,
        description="Complete CSS content with modified colors but preserved structure"
    )
    theme_description: Dict[str, Any] = Field(
        ...,
        description="JSON description containing title and representative_colors"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class ThemeGenerationResult(BaseModel):
    """
    Pydantic model for the complete theme generation response from OpenAI.
    
    This model defines the structure of the JSON response containing
    all 5 generated theme variations.
    """
    
    generated_themes: List[GeneratedTheme] = Field(
        ...,
        description="List of 5 generated theme variations"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }



def _scan_existing_themes(themes_directory_path: str) -> List[ExistingThemeInfo]:
    """
    Scan the themes directory for existing JSON theme files.
    
    Args:
        themes_directory_path: Path to the themes directory
        
    Returns:
        List of ExistingThemeInfo containing filename and content of each theme
        
    Raises:
        ThemesDirectoryError: If directory scanning fails
    """
    logger.info(f"Scanning themes directory for existing JSON files: {themes_directory_path}")
    
    themes_dir = Path(themes_directory_path)
    existing_themes = []
    
    if not themes_dir.exists():
        logger.warning(f"Themes directory does not exist: {themes_directory_path}")
        return existing_themes
    
    try:
        # Find all JSON files in themes directory
        for json_file in themes_dir.glob("*.json"):
            try:
                # Read JSON content
                with open(json_file, 'r', encoding='utf-8') as file:
                    json_content = json.load(file)
                
                # Get filename without extension
                filename = json_file.stem
                
                existing_themes.append(ExistingThemeInfo(
                    filename=filename,
                    content=json_content
                ))
                logger.info(f"Found existing theme: {filename}")
                
            except Exception as e:
                logger.warning(f"Failed to read JSON file {json_file}: {e}")
                continue
        
        logger.info(f"Found {len(existing_themes)} existing theme files")
        return existing_themes
        
    except Exception as e:
        logger.error(f"Error scanning themes directory: {e}")
        raise ThemesDirectoryError(themes_directory_path, str(e))


def _generate_new_themes(
    original_css_content: str,
    existing_themes: List[ExistingThemeInfo]
) -> List[GeneratedTheme]:
    """
    Generate new theme variations using OpenAI.
    
    Args:
        original_css_content: Content of the original CSS file
        existing_themes: List of existing themes to avoid conflicts
        
    Returns:
        List of GeneratedTheme objects with new theme variations
        
    Raises:
        ThemeGenerationError: If theme generation fails
    """
    logger.info("Generating new theme variations using OpenAI")
    
    try:
        # Get OpenAI configuration
        workflow_config = get_workflow_config()
        
        # Initialize OpenAI client
        client = OpenAI(api_key=workflow_config.openai_api_key)
        
        # Define the JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {
                "generated_themes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Unique filename for the theme (without extension)"
                            },
                            "css_content": {
                                "type": "string",
                                "description": "Complete CSS content with modified colors"
                            },
                            "theme_description": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "Descriptive title for the theme"
                                    },
                                    "representative_colors": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "List of representative colors in HEX format"
                                    }
                                },
                                "required": ["title", "representative_colors"],
                                "additionalProperties": False
                            }
                        },
                        "required": ["filename", "css_content", "theme_description"],
                        "additionalProperties": False
                    },
                    "minItems": 5,
                    "maxItems": 5
                }
            },
            "required": ["generated_themes"],
            "additionalProperties": False
        }
        
        # Prepare detailed existing themes information for color analysis
        existing_filenames = [theme.filename for theme in existing_themes]
        existing_themes_info = ""
        
        if existing_themes:
            existing_themes_info = "Existing Theme Files (avoid these filenames and color combinations):\n\n"
            for theme in existing_themes:
                title = theme.content.get('title', 'Unknown')
                colors = theme.content.get('representative_colors', [])
                existing_themes_info += f"Theme: {theme.filename}\n"
                existing_themes_info += f"  Title: {title}\n"
                existing_themes_info += f"  Representative Colors: {', '.join(colors) if colors else 'None specified'}\n\n"
            
            existing_themes_info += "CRITICAL: Analyze the above color palettes and ensure your new themes use COMPLETELY DIFFERENT color schemes. Avoid similar hues, saturation levels, brightness, and color families. Create truly unique and distinguishable color combinations.\n"
        else:
            existing_themes_info = "No existing theme files found. You have complete creative freedom for color selection.\n"
        
        # Prepare the input content
        input_content = f"""{CSS_THEME_GENERATION_PROMPT}

{existing_themes_info}

Original CSS Content:
{original_css_content}

Please generate 5 new and distinct color theme variations based on this CSS file. Each theme should have a unique filename that doesn't conflict with existing themes, modified CSS content with only color changes, and a descriptive JSON theme description."""
        
        logger.info("Sending theme generation request to OpenAI GPT-5 model")
        
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
                    "name": "theme_generation",
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
                raise ThemeGenerationError(f"Unable to extract content from response: {type(response)}")
        
        if not content:
            raise ThemeGenerationError("Empty response content from OpenAI")
        
        logger.info(f"Extracted response content: {content[:200]}...")
        
        # Parse the JSON response
        try:
            generation_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise ThemeGenerationError(f"Invalid JSON response from OpenAI: {e}")
        
        # Create and validate the generation result
        result = ThemeGenerationResult(**generation_data)
        
        logger.info(f"Successfully generated {len(result.generated_themes)} theme variations")
        for theme in result.generated_themes:
            logger.info(f"Generated theme: {theme.filename} - {theme.theme_description.get('title', 'Unknown')}")
        
        return result.generated_themes
        
    except Exception as e:
        logger.error(f"Error during theme generation: {e}")
        raise ThemeGenerationError(str(e))


def _write_theme_files(
    themes_directory_path: str,
    generated_themes: List[GeneratedTheme]
) -> None:
    """
    Write generated theme files to the themes directory.
    
    Args:
        themes_directory_path: Path to the themes directory
        generated_themes: List of generated themes to write
        
    Raises:
        ThemesDirectoryError: If file writing fails
    """
    logger.info(f"Writing {len(generated_themes)} theme files to: {themes_directory_path}")
    
    themes_dir = Path(themes_directory_path)
    
    try:
        # Ensure themes directory exists
        themes_dir.mkdir(parents=True, exist_ok=True)
        
        for theme in generated_themes:
            # Write CSS file
            css_file_path = themes_dir / f"{theme.filename}.css"
            with open(css_file_path, 'w', encoding='utf-8') as file:
                file.write(theme.css_content)
            logger.info(f"Wrote CSS file: {css_file_path}")
            
            # Write JSON file
            json_file_path = themes_dir / f"{theme.filename}.json"
            with open(json_file_path, 'w', encoding='utf-8') as file:
                json.dump(theme.theme_description, file, indent=2, ensure_ascii=False)
            logger.info(f"Wrote JSON file: {json_file_path}")
        
        logger.info("Successfully wrote all theme files")
        
    except Exception as e:
        logger.error(f"Error writing theme files: {e}")
        raise ThemesDirectoryError(themes_directory_path, f"File writing failed: {e}")


def css_generator_agent(
    themes_directory_path: str,
    original_css_file_path: str
) -> None:
    """
    Generate multiple color theme variations based on an original CSS file.
    
    This function scans the themes directory for existing themes, reads the original
    CSS file, and uses OpenAI's GPT-5 model to generate 5 new color theme variations.
    Each variation includes both a modified CSS file and a corresponding JSON description
    file for theme selection interface display. The function ensures each new theme has
    unique colors that don't overlap with existing themes.
    
    Args:
        themes_directory_path: Path to the themes directory where JSON and CSS files are stored
        original_css_file_path: Path to the original CSS file to base variations on
        
    Raises:
        CssFileReadError: If the original CSS file cannot be read
        ThemesDirectoryError: If themes directory operations fail
        ThemeGenerationError: If theme generation fails
        Exception: For other unexpected errors during the process
    """
    logger.info(f"Starting CSS theme generation for: {original_css_file_path}")
    logger.info(f"Using themes directory: {themes_directory_path}")
    
    # Convert to Path object for easier manipulation
    css_file = Path(original_css_file_path)
    
    # Check if original CSS file exists
    if not css_file.exists():
        logger.error(f"Original CSS file does not exist: {original_css_file_path}")
        raise CssFileReadError(original_css_file_path, "File not found")
    
    if not css_file.is_file():
        logger.error(f"Original CSS path is not a file: {original_css_file_path}")
        raise CssFileReadError(original_css_file_path, "Path is not a file")
    
    try:
        # Read original CSS file content
        logger.info("Reading original CSS file content")
        with open(css_file, 'r', encoding='utf-8') as file:
            original_css_content = file.read()
        
        logger.info(f"Successfully read original CSS file: {len(original_css_content)} characters")
        
        # Scan existing themes in the directory
        existing_themes = _scan_existing_themes(themes_directory_path)
        
        # Generate new theme variations using OpenAI
        generated_themes = _generate_new_themes(original_css_content, existing_themes)
        
        # Write the generated theme files
        _write_theme_files(themes_directory_path, generated_themes)
        
        logger.info("CSS theme generation completed successfully")
        logger.info(f"Generated {len(generated_themes)} new theme variations")
        
    except (CssFileReadError, ThemesDirectoryError, ThemeGenerationError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during CSS theme generation: {e}")
        raise Exception(f"CSS theme generation failed: {e}")


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for CSS theme generator.
    
    Returns:
        Parsed arguments namespace containing themes_directory and original_css_file
        
    Raises:
        SystemExit: If argument parsing fails or help is requested
    """
    parser = argparse.ArgumentParser(
        description="Generate multiple color theme variations based on an original CSS file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m workflow.service.css_generator_agent --themes-dir /path/to/themes --original-css /path/to/original.css
  python -m workflow.service.css_generator_agent -t ./themes -o ./styles/main.css
        """
    )
    
    parser.add_argument(
        "--themes-dir", "-t",
        type=str,
        default=DEFAULT_THEMES_DIRECTORY_PATH,
        help=f"Path to the themes directory where JSON and CSS files are stored (default: {DEFAULT_THEMES_DIRECTORY_PATH})"
    )
    
    parser.add_argument(
        "--original-css", "-o",
        type=str,
        default=DEFAULT_ORIGINAL_CSS_FILE_PATH,
        help=f"Path to the original CSS file to base variations on (default: {DEFAULT_ORIGINAL_CSS_FILE_PATH})"
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
    
    # Validate original CSS file path
    if not args.original_css:
        logger.error("Original CSS file path cannot be empty")
        sys.exit(1)
    
    # Check if original CSS file exists
    css_file = Path(args.original_css)
    if not css_file.exists():
        logger.error(f"Original CSS file does not exist: {args.original_css}")
        sys.exit(1)
    
    if not css_file.is_file():
        logger.error(f"Original CSS path is not a file: {args.original_css}")
        sys.exit(1)
    
    logger.info(f"Arguments validated successfully")
    logger.info(f"Themes directory: {args.themes_dir}")
    logger.info(f"Original CSS file: {args.original_css}")


def main() -> None:
    """
    Standalone entry point to generate additional CSS color themes.

    This function parses command line arguments to get the themes directory
    and original CSS file paths, then invokes css_generator_agent to
    generate five new and unique color theme variations.

    Command line arguments:
        --themes-dir, -t: Path to the themes directory (optional, has default)
        --original-css, -o: Path to the original CSS file (optional, has default)

    Raises:
        CssFileReadError: If the original CSS file cannot be read
        ThemesDirectoryError: If themes directory operations fail
        ThemeGenerationError: If theme generation fails
        SystemExit: If argument parsing or validation fails
        Exception: For other unexpected errors during the process
    """
    logger.info("Standalone CSS theme generator started")

    try:
        # Parse and validate command line arguments
        args = _parse_arguments()
        _validate_arguments(args)
        
        # Run CSS theme generation with parsed arguments
        css_generator_agent(
            themes_directory_path=args.themes_dir,
            original_css_file_path=args.original_css
        )
        logger.info("Standalone CSS theme generator finished successfully")
        
    except (CssFileReadError, ThemesDirectoryError, ThemeGenerationError) as e:
        logger.error(f"CSS theme generation failed: {e}")
        sys.exit(1)
    except SystemExit:
        # Re-raise SystemExit (from argparse or validation)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
