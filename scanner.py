"""
scanner.py — Scans a project directory and builds a structured map
for the AI to understand the project layout.
"""
from pathlib import Path

IGNORED = {
    '__pycache__', '.git', 'node_modules', '.venv', 'venv',
    'dist', 'build', '.next', '.idea', '.vscode', 'target',
    'vendor', '.pytest_cache', '.mypy_cache', 'coverage', 'out'
}


def scan(root: Path, max_depth: int = 6) -> str:
    """
    Returns a readable tree string of the project structure.
    This is what gets sent to Gemini as context.
    """
    lines = [f"{root.name}/"]
    _recurse(root, lines, prefix="", depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _recurse(path: Path, lines: list, prefix: str, depth: int, max_depth: int):
    if depth >= max_depth:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return

    entries = [e for e in entries if e.name not in IGNORED and not e.name.startswith('.')]

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
        if entry.is_dir():
            ext = "    " if is_last else "│   "
            _recurse(entry, lines, prefix + ext, depth + 1, max_depth)


def detect_project_type(root: Path) -> str:
    """Detect the project type for extra context to the AI."""
    files = {f.name for f in root.rglob('*') if f.is_file()}
    dirs = {d.name for d in root.rglob('*') if d.is_dir()}

    if 'package.json' in files:
        if 'next.config.js' in files or 'next.config.ts' in files:
            return 'Next.js'
        if 'vite.config.ts' in files or 'vite.config.js' in files:
            return 'Vite (React/Vue)'
        return 'Node.js'
    if 'manage.py' in files:
        return 'Django'
    if 'pyproject.toml' in files or 'setup.py' in files:
        return 'Python'
    if 'Cargo.toml' in files:
        return 'Rust'
    if 'go.mod' in files:
        return 'Go'
    if 'pom.xml' in files:
        return 'Java (Maven)'
    if 'CMakeLists.txt' in files:
        return 'C/C++'
    return 'Unknown'


def read_aiconfig(root: "Path") -> str:
    """
    Read .aiconfig file from project root if it exists.
    Returns the content as string, or empty string if not found.
    """
    aiconfig = root / ".aiconfig"
    if aiconfig.exists():
        try:
            return aiconfig.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""
