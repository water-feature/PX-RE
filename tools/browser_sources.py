"""Shared inventory of browser-recipe generator inputs; Markdown is not executable input."""
from pathlib import Path


def source_paths(root: Path) -> list[Path]:
    direct = root / 'firmware_builder/direct'
    return sorted(path for path in direct.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts
                  and path.suffix.lower() != '.md')
