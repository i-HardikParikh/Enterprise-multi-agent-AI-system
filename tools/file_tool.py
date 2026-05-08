"""
tools/file_tool.py — File Read / Write Tools
"""
import structlog
from pathlib import Path
from langchain_core.tools import tool

logger = structlog.get_logger()
UPLOAD_DIR  = Path("./data/uploads")
OUTPUT_DIR  = Path("./data/outputs")


@tool
def read_file(file_path: str) -> str:
    """
    Read content of an uploaded file (.txt, .md, .json, .csv).

    Args:
        file_path: Filename relative to uploads dir (e.g. 'report.txt')

    Returns:
        File contents as text
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    full = UPLOAD_DIR / file_path
    if not full.exists():
        available = [f.name for f in UPLOAD_DIR.iterdir()] if UPLOAD_DIR.exists() else []
        return f"File '{file_path}' not found. Available: {available}"
    try:
        return full.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_available_files() -> str:
    """
    List all files in the uploads directory.

    Returns:
        Filenames with sizes
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    files = list(UPLOAD_DIR.iterdir())
    if not files:
        return "No files uploaded yet."
    return "\n".join(f"{f.name}  ({f.stat().st_size:,} bytes)" for f in files if f.is_file())


@tool
def save_output(filename: str, content: str) -> str:
    """
    Save generated content to the outputs directory.

    Args:
        filename: Output filename (e.g. 'report.md')
        content:  Text content to save

    Returns:
        Confirmation message with path
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    logger.info("save_output.done", path=str(path), size=len(content))
    return f"Saved: {path}  ({len(content):,} chars)"


def get_file_tool():
    return [read_file, list_available_files, save_output]
