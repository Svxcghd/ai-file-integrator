"""
writer.py — Safely writes files to the project with backup support.
"""
import shutil
from pathlib import Path
from .models import FileDecision, WriteResult, WriteStatus
from .backup import backup_file

DANGEROUS_EXTENSIONS = {'.exe', '.bat', '.cmd', '.dll', '.so', '.pif', '.scr'}


def write_file(decision: FileDecision, project_root: Path) -> WriteResult:
    dest_relative = decision.destination.lstrip('/')
    dest_absolute = (project_root / dest_relative).resolve()
    project_resolved = project_root.resolve()

    try:
        dest_absolute.relative_to(project_resolved)
    except ValueError:
        return WriteResult(
            source=decision.source, destination=dest_absolute,
            status=WriteStatus.ERROR,
            message=f"Destination outside project root — blocked: {decision.destination}",
        )

    if dest_absolute.suffix.lower() in DANGEROUS_EXTENSIONS:
        return WriteResult(
            source=decision.source, destination=dest_absolute,
            status=WriteStatus.ERROR,
            message=f"Dangerous extension blocked: {dest_absolute.suffix}",
        )

    created_dirs = []
    backup = None

    if not dest_absolute.parent.exists():
        if decision.create_folder:
            dest_absolute.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(dest_absolute.parent.relative_to(project_root)))
        else:
            return WriteResult(
                source=decision.source, destination=dest_absolute,
                status=WriteStatus.ERROR,
                message=f"Directory does not exist: {dest_absolute.parent}",
            )

    if dest_absolute.exists():
        backup = backup_file(dest_absolute, project_root)

    try:
        shutil.copy2(str(decision.source), str(dest_absolute))
        action = "Updated" if backup else "Created"
        return WriteResult(
            source=decision.source, destination=dest_absolute,
            status=WriteStatus.SUCCESS,
            message=f"✓ {action}: {dest_relative}",
            backup=backup, created_dirs=created_dirs,
        )
    except Exception as e:
        return WriteResult(
            source=decision.source, destination=dest_absolute,
            status=WriteStatus.ERROR, message=f"Write error: {e}",
        )
