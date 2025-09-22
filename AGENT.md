# Photo Manager Agent Guide

## Commands
- **Run**: `uv run photo_manager.py <folder_name>`
- **Install**: `uv sync` (installs from pyproject.toml)
- **Test**: `uv run python -m unittest test_photo_manager -v`
- **Python version**: Requires Python 3.13+ (see pyproject.toml)

## Architecture
- **Single-file script** (`photo_manager.py`) that uploads photos to Cloudflare R2 and Google Drive
- **Dependencies**: Cloudflare R2 (boto3), Google Drive API, EXIF processing
- **Configuration**: Requires `constants.py` (copy from `constants.py.example`)
- **Authentication**: Google OAuth (`credentials.json`, `token.pickle`) and R2 access keys
- **Storage**: R2 bucket path: `photo_collections/<collection_name>/<number>.jpg`
- **Photo naming**: Automatically numbers photos 1.jpg, 2.jpg, etc. in sorted order
- **Resumability**: Checks existing files in both R2 and Google Drive to avoid re-uploads

## Code Style
- **Imports**: Standard library first, then third-party (boto3, Google), then local constants
- **Functions**: Snake_case with docstrings for main functions
- **Error handling**: Try/except blocks with descriptive print statements for failures
- **Constants**: ALL_CAPS in separate constants.py file
- **File paths**: Cross-platform support (Windows vs WSL paths)
- **User prompts**: Uses promptUser() helper for Y/n confirmations
