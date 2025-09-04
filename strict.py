from pathlib import Path


def strict_path(value: Path | None) -> Path:
    if value is None:
        raise ValueError("Expected non-None value")
    return value
