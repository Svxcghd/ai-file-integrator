"""
mover.py — Safely moves files to their destination inside the project.
All operations are restricted to the project root.
"""
import shutil
from pathlib import Path


class MoveError(Exception):
    pass


def safe_move(
    source: Path,
    project_root: Path,
    relative_destination: str,
    create_folder: bool = False,
    copy_instead: bool = True,  # Default: copy, don't delete original
) -> Path:
    """
    Move (or copy) a file to its destination inside the project.

    Args:
        source:               The downloaded file to move
        project_root:         The project root directory
        relative_destination: Relative path inside project (from AI decision)
        create_folder:        Whether to create missing directories
        copy_instead:         If True, copies file (keeps original). If False, moves it.

    Returns:
        The final Path where the file was placed.

    Raises:
        MoveError: If any safety check fails.
    """
    # Clean the destination path
    dest_relative = relative_destination.lstrip("/").lstrip("\\")
    dest_absolute = (project_root / dest_relative).resolve()
    project_resolved = project_root.resolve()

    # Safety: must stay inside project
    try:
        dest_absolute.relative_to(project_resolved)
    except ValueError:
        raise MoveError(
            f"Destination '{relative_destination}' is outside the project root. Blocked."
        )

    # Safety: no path traversal
    if '..' in Path(dest_relative).parts:
        raise MoveError(f"Path traversal detected in '{relative_destination}'. Blocked.")

    # Create parent directories if needed
    parent = dest_absolute.parent
    if not parent.exists():
        if create_folder:
            parent.mkdir(parents=True, exist_ok=True)
        else:
            raise MoveError(
                f"Directory '{parent}' does not exist and create_folder=False."
            )

    # If destination already exists, add a suffix to avoid overwriting
    final_dest = dest_absolute
    if final_dest.exists():
        stem = dest_absolute.stem
        suffix = dest_absolute.suffix
        counter = 1
        while final_dest.exists():
            final_dest = dest_absolute.parent / f"{stem}_{counter}{suffix}"
            counter += 1

    # Copy or move
    if copy_instead:
        shutil.copy2(str(source), str(final_dest))
    else:
        shutil.move(str(source), str(final_dest))

    return final_dest


def get_relative(file_path: Path, project_root: Path) -> str:
    """Return a path relative to the project root as a string."""
    try:
        return str(file_path.relative_to(project_root))
    except ValueError:
        return str(file_path)
