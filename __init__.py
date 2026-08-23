"""AI File Integrator v3 — Backend"""
from .models    import *
from .scanner   import scan, save_aiconfig
from .analyzer  import analyze
from .writer    import write_file
from .backup    import backup_file, list_backups, commit_before_patch, revert_to_commit, get_last_commits
from .patcher   import apply_patch, preview_patch, revert_patch, PatchOutcome
from .validator import validate_project, ValidationResult, ValidationError
from .deps      import analyze_dependencies, install_dependencies
from .config    import get_projects, add_project, remove_project
