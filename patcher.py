"""
patcher.py — Applies partial code changes with Git checkpoint + validation + revert.
"""
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from .models import PatchResult, ProjectState
from .backup import backup_file, commit_before_patch, revert_to_commit
from .validator import validate_project, ValidationResult


@dataclass
class PatchOutcome:
    patch_result: PatchResult
    validation: ValidationResult | None = None
    git_checkpoint: str | None = None
    was_reverted: bool = False
    revert_message: str = ""

    @property
    def success(self) -> bool:
        if not self.patch_result.success:
            return False
        if self.validation and not self.validation.success:
            return False
        return True

    @property
    def needs_attention(self) -> bool:
        return self.patch_result.success and self.validation is not None and not self.validation.success


def apply_patch(
    target_file: Path,
    new_fragment: str,
    project_root: Path,
    state: ProjectState | None = None,
    validate_after: bool = True,
) -> PatchOutcome:
    outcome = PatchOutcome(patch_result=PatchResult(target_file=target_file))

    if not target_file.exists():
        outcome.patch_result.success = False
        outcome.patch_result.message = f"File not found: {target_file.name}"
        return outcome

    # Step 1: Git checkpoint
    checkpoint_hash = commit_before_patch(project_root, target_file)
    outcome.git_checkpoint = checkpoint_hash

    # Step 2: Apply patch
    original_content = target_file.read_text(encoding='utf-8', errors='replace')
    original_lines   = original_content.splitlines(keepends=True)
    fragment_lines   = new_fragment.splitlines(keepends=True)

    match_result = _find_and_replace(original_lines, fragment_lines)

    if match_result is None:
        outcome.patch_result.success = False
        outcome.patch_result.message = (
            "Fragment not found in file — the code doesn't match any section.\n"
            "Tip: Make sure the AI gave you the complete function or block."
        )
        return outcome

    new_content, lines_changed = match_result

    if new_content == original_content:
        outcome.patch_result.success = True
        outcome.patch_result.lines_changed = 0
        outcome.patch_result.message = "No changes detected — file is already up to date."
        return outcome

    backup = backup_file(target_file, project_root)
    outcome.patch_result.backup = backup

    target_file.write_text(new_content, encoding='utf-8')
    outcome.patch_result.success = True
    outcome.patch_result.lines_changed = lines_changed
    outcome.patch_result.message = f"✓ Patched {lines_changed} line(s) in {target_file.name}"

    # Step 3: Validate
    if validate_after and state is not None:
        outcome.validation = validate_project(project_root, state.project_type)

    return outcome


def revert_patch(outcome: PatchOutcome, project_root: Path):
    if not outcome.git_checkpoint:
        if outcome.patch_result.backup and not outcome.patch_result.backup.used_git:
            from .backup import restore_backup
            success = restore_backup(outcome.patch_result.backup)
            msg = "✓ Reverted from .afi_backups/" if success else "✗ Could not restore backup."
            outcome.was_reverted = success
            outcome.revert_message = msg
            return success, msg
        return False, "No checkpoint available to revert to."

    success, msg = revert_to_commit(project_root, outcome.git_checkpoint)
    outcome.was_reverted = success
    outcome.revert_message = msg
    return success, msg


def preview_patch(target_file: Path, new_fragment: str) -> str:
    if not target_file.exists():
        return f"File not found: {target_file.name}"

    original_lines = target_file.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
    fragment_lines = new_fragment.splitlines(keepends=True)

    result = _find_and_replace(original_lines, fragment_lines)
    if result is None:
        return (
            "⚠ Fragment not found in original file.\n\n"
            "Make sure you're pasting a complete function or block\n"
            "that exists in the current file."
        )

    new_content, _ = result
    diff = difflib.unified_diff(
        original_lines,
        new_content.splitlines(keepends=True),
        fromfile=f"original/{target_file.name}",
        tofile=f"patched/{target_file.name}",
        lineterm='',
    )
    return ''.join(diff) or "No differences found."


def _find_and_replace(original_lines: list, fragment_lines: list):
    if not fragment_lines:
        return None
    frag_len = len(fragment_lines)
    orig_len = len(original_lines)
    if frag_len > orig_len:
        return None

    best_ratio = 0.0
    best_start = -1

    for i in range(orig_len - frag_len + 1):
        ratio = _similarity(original_lines[i:i + frag_len], fragment_lines)
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = i

    if best_ratio < 0.6 or best_start == -1:
        return None

    original_chunk = original_lines[best_start:best_start + frag_len]
    lines_changed  = sum(1 for a, b in zip(original_chunk, fragment_lines) if a != b)
    new_lines = original_lines[:best_start] + fragment_lines + original_lines[best_start + frag_len:]
    return ''.join(new_lines), lines_changed


def _similarity(a: list, b: list) -> float:
    matcher = difflib.SequenceMatcher(None, [l.strip() for l in a], [l.strip() for l in b])
    return matcher.ratio()
