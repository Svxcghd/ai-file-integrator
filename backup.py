"""
backup.py — Backup system + Git checkpoint for patch safety.
"""
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from .models import BackupEntry

BACKUP_DIR = '.afi_backups'


def backup_file(file_path: Path, project_root: Path) -> BackupEntry:
    timestamp = datetime.now()
    if _has_git(project_root):
        return _git_backup(file_path, project_root, timestamp)
    return _folder_backup(file_path, project_root, timestamp)


def commit_before_patch(project_root: Path, target_file: Path):
    """Create a Git commit checkpoint before patching. Returns commit hash or None."""
    if not _has_git(project_root):
        return None
    try:
        rel_path = target_file.relative_to(project_root)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(['git', 'add', '-A'], cwd=project_root, capture_output=True, check=False)
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', f'AFI pre-patch checkpoint — {ts} — {rel_path}'],
            cwd=project_root, capture_output=True, check=False
        )
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=project_root, capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def revert_to_commit(project_root: Path, commit_hash: str):
    """Revert project to a specific Git commit. Returns (success, message)."""
    if not _has_git(project_root):
        return False, "Git not available in this project."
    try:
        result = subprocess.run(
            ['git', 'checkout', commit_hash, '--', '.'],
            cwd=project_root, capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return True, f"✓ Reverted to commit {commit_hash[:8]}"
        return False, f"Git revert failed: {result.stderr.strip()[:200]}"
    except Exception as e:
        return False, f"Revert error: {e}"


def get_last_commits(project_root: Path, count: int = 5) -> list:
    if not _has_git(project_root):
        return []
    try:
        result = subprocess.run(
            ['git', 'log', f'-{count}', '--pretty=format:%H|%s|%ar'],
            cwd=project_root, capture_output=True, text=True, check=False
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split('|', 2)
            if len(parts) == 3:
                commits.append({'hash': parts[0].strip(), 'message': parts[1].strip(), 'date': parts[2].strip()})
        return commits
    except Exception:
        return []


def list_backups(project_root: Path) -> list:
    backup_dir = project_root / BACKUP_DIR
    if not backup_dir.exists():
        return []
    entries = []
    for f in sorted(backup_dir.iterdir(), reverse=True):
        if f.is_file():
            entries.append(BackupEntry(
                original_path=project_root / f.name,
                backup_path=f,
                timestamp=datetime.fromtimestamp(f.stat().st_mtime),
                used_git=False,
            ))
    return entries


def restore_backup(backup_entry: BackupEntry) -> bool:
    if backup_entry.used_git:
        return False
    try:
        shutil.copy2(str(backup_entry.backup_path), str(backup_entry.original_path))
        return True
    except Exception:
        return False


def _has_git(project_root: Path) -> bool:
    return (project_root / '.git').exists()


def _git_backup(file_path: Path, project_root: Path, timestamp: datetime) -> BackupEntry:
    try:
        rel_path = file_path.relative_to(project_root)
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(['git', 'add', str(rel_path)], cwd=project_root, capture_output=True, check=False)
        subprocess.run(
            ['git', 'commit', '-m', f'AFI backup — {ts_str} — {rel_path}'],
            cwd=project_root, capture_output=True, check=False
        )
        return BackupEntry(original_path=file_path, backup_path=file_path, timestamp=timestamp, used_git=True)
    except Exception:
        return _folder_backup(file_path, project_root, timestamp)


def _folder_backup(file_path: Path, project_root: Path, timestamp: datetime) -> BackupEntry:
    backup_dir = project_root / BACKUP_DIR
    backup_dir.mkdir(exist_ok=True)
    ts_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"{file_path.stem}_{ts_str}{file_path.suffix}"
    shutil.copy2(str(file_path), str(backup_path))
    return BackupEntry(original_path=file_path, backup_path=backup_path, timestamp=timestamp, used_git=False)
