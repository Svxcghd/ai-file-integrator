"""
scanner.py — Scans project directory and builds structured info.
"""
from pathlib import Path
from .models import ProjectState, ProjectType, ProjectConfig

IGNORED = {
    '__pycache__', '.git', 'node_modules', '.venv', 'venv',
    'dist', 'build', '.next', '.idea', '.vscode', 'target',
    'vendor', '.pytest_cache', '.mypy_cache', 'coverage',
    'out', '.expo', '.afi_backups',
}


def scan(root: Path) -> ProjectState:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid project root: {root}")

    state = ProjectState(root=root, name=root.name)

    try:
        all_entries = list(root.rglob('*'))
    except PermissionError:
        all_entries = []

    state.total_files = sum(1 for e in all_entries if e.is_file() and not _is_ignored(e, root))
    state.total_dirs  = sum(1 for e in all_entries if e.is_dir() and not _is_ignored(e, root))

    filenames = {f.name for f in all_entries if f.is_file()}
    state.has_git              = (root / '.git').exists()
    state.has_package_json     = 'package.json' in filenames
    state.has_requirements_txt = 'requirements.txt' in filenames
    state.project_type         = _detect_type(root, filenames)
    state.detected_languages   = _detect_languages(all_entries)
    state.tree                 = _build_tree(root)
    state.config               = _load_aiconfig(root)

    return state


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
        return any(p in IGNORED or p.startswith('.') for p in parts)
    except ValueError:
        return False


def _detect_type(root: Path, filenames: set) -> ProjectType:
    if 'manage.py' in filenames:
        return ProjectType.DJANGO
    if 'build.gradle.kts' in filenames or 'build.gradle' in filenames:
        return ProjectType.ANDROID_KOTLIN
    if (root / 'app' / 'src' / 'main').exists() and (root / 'gradlew').exists():
        return ProjectType.ANDROID_KOTLIN
    if 'app.json' in filenames and 'expo' in _read_json_field(root / 'package.json', 'dependencies', ''):
        return ProjectType.REACT_NATIVE
    if 'app.json' in filenames and (root / 'app').exists():
        return ProjectType.REACT_NATIVE
    if 'vite.config.ts' in filenames or 'vite.config.js' in filenames:
        return ProjectType.WEB_REACT
    if 'next.config.js' in filenames or 'next.config.ts' in filenames:
        return ProjectType.WEB_REACT
    if 'package.json' in filenames:
        return ProjectType.NODEJS
    if 'pyproject.toml' in filenames or 'setup.py' in filenames:
        return ProjectType.PYTHON
    return ProjectType.UNKNOWN


def _read_json_field(path: Path, field: str, default: str) -> str:
    try:
        import json
        data = json.loads(path.read_text())
        return str(data.get(field, default))
    except Exception:
        return default


def _detect_languages(entries: list) -> list:
    ext_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
        '.tsx': 'TypeScript/React', '.jsx': 'JavaScript/React',
        '.cpp': 'C++', '.c': 'C', '.rs': 'Rust', '.go': 'Go',
        '.kt': 'Kotlin', '.kts': 'Kotlin Script', '.h': 'C/C++ Header',
    }
    found: set = set()
    for e in entries:
        if e.is_file():
            lang = ext_map.get(e.suffix.lower())
            if lang:
                found.add(lang)
    return sorted(found)


def _build_tree(root: Path, max_depth: int = 6) -> str:
    lines = [f"{root.name}/"]
    _recurse_tree(root, lines, "", 0, max_depth)
    return "\n".join(lines)


def _recurse_tree(path: Path, lines: list, prefix: str, depth: int, max_depth: int):
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
            _recurse_tree(entry, lines, prefix + ext, depth + 1, max_depth)


def _load_aiconfig(root: Path) -> ProjectConfig:
    aiconfig_path = root / '.aiconfig'
    if not aiconfig_path.exists():
        return ProjectConfig()
    try:
        content = aiconfig_path.read_text(encoding='utf-8')
        config = ProjectConfig(raw_content=content)
        for line in content.splitlines():
            if line.startswith('Proyecto:'):
                config.project_name = line.split(':', 1)[1].strip()
            elif line.startswith('Tipo:'):
                config.project_type = line.split(':', 1)[1].strip()
        return config
    except Exception:
        return ProjectConfig()


def save_aiconfig(root: Path, content: str):
    (root / '.aiconfig').write_text(content, encoding='utf-8')
