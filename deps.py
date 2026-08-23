"""
deps.py — Detects dependencies and env vars. Runs npm/pip install automatically.
"""
import re
import subprocess
import json
from pathlib import Path
from .models import DependencyInfo, EnvVarSuggestion

JS_IMPORT_PATTERN = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]|require\s*\(\s*['"])(@?[\w\-./]+)['"]""",
    re.MULTILINE,
)
PY_IMPORT_PATTERN = re.compile(r'^(?:import|from)\s+([\w.]+)', re.MULTILINE)
KT_IMPORT_PATTERN = re.compile(r'^import\s+([\w.]+)', re.MULTILINE)

ENV_VAR_PATTERNS = [
    re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)'),
    re.compile(r'import\.meta\.env\.([A-Z_][A-Z0-9_]*)'),
    re.compile(r'os\.environ(?:\.get)?\([\'"]([A-Z_][A-Z0-9_]*)'),
    re.compile(r'getenv\([\'"]([A-Z_][A-Z0-9_]*)'),
]

NODE_BUILTINS = {
    'fs', 'path', 'os', 'http', 'https', 'crypto', 'stream',
    'util', 'events', 'buffer', 'url', 'child_process', 'cluster',
}

PYTHON_BUILTINS = {
    'os', 'sys', 'json', 're', 'math', 'datetime', 'time', 'random',
    'collections', 'itertools', 'functools', 'pathlib', 'typing',
    'abc', 'copy', 'io', 'string', 'hashlib', 'base64', 'urllib',
    'http', 'logging', 'unittest', 'dataclasses', 'enum', 'traceback',
    'contextlib', 'inspect', 'shutil', 'tempfile', 'glob', 'difflib',
    'subprocess', 'threading', 'multiprocessing', 'socket', 'sqlite3',
}


def analyze_dependencies(file_path: Path, content: str, project_root: Path):
    ext = file_path.suffix.lower()
    deps, env_vars = [], []

    for pattern in ENV_VAR_PATTERNS:
        for match in pattern.finditer(content):
            var_name = match.group(1)
            if not any(e.name == var_name for e in env_vars):
                env_vars.append(EnvVarSuggestion(
                    name=var_name, source_file=file_path.name,
                    example_value=_guess_env_value(var_name),
                ))

    if ext in ('.js', '.ts', '.jsx', '.tsx'):
        installed = _get_installed_npm(project_root)
        for match in JS_IMPORT_PATTERN.finditer(content):
            pkg = _normalize_npm_package(match.group(1))
            if not pkg or pkg in NODE_BUILTINS:
                continue
            if not any(d.name == pkg for d in deps):
                deps.append(DependencyInfo(
                    name=pkg, package_manager='npm',
                    is_installed=pkg in installed,
                    is_dev=_is_dev_dependency(pkg),
                ))

    elif ext == '.py':
        installed = _get_installed_pip()
        for match in PY_IMPORT_PATTERN.finditer(content):
            pkg = match.group(1).split('.')[0]
            if not pkg or pkg in PYTHON_BUILTINS:
                continue
            if not any(d.name == pkg for d in deps):
                deps.append(DependencyInfo(
                    name=pkg, package_manager='pip',
                    is_installed=pkg.lower() in installed,
                ))

    elif ext in ('.kt', '.kts'):
        known_libs = {
            'androidx.room':          'androidx.room:room-runtime',
            'androidx.lifecycle':     'androidx.lifecycle:lifecycle-viewmodel-compose',
            'androidx.compose':       'androidx.compose.ui:ui',
            'androidx.navigation':    'androidx.navigation:navigation-compose',
            'kotlinx.coroutines':     'org.jetbrains.kotlinx:kotlinx-coroutines-android',
            'dagger.hilt':            'com.google.dagger:hilt-android',
        }
        for match in KT_IMPORT_PATTERN.finditer(content):
            imp = match.group(1)
            for prefix, gradle_dep in known_libs.items():
                if imp.startswith(prefix) and not any(d.name == gradle_dep for d in deps):
                    deps.append(DependencyInfo(
                        name=gradle_dep, package_manager='gradle',
                        is_installed=_check_gradle_dep(project_root, gradle_dep),
                    ))
                    break

    return deps, env_vars


def install_dependencies(deps: list, project_root: Path) -> list:
    logs = []
    missing = [d for d in deps if not d.is_installed]
    if not missing:
        return ["✓ All dependencies already installed."]

    npm_pkgs    = [d.name for d in missing if d.package_manager == 'npm' and not d.is_dev]
    npm_dev     = [d.name for d in missing if d.package_manager == 'npm' and d.is_dev]
    pip_pkgs    = [d.name for d in missing if d.package_manager == 'pip']
    gradle_pkgs = [d.name for d in missing if d.package_manager == 'gradle']

    if gradle_pkgs:
        logs.append("⚠ Gradle dependencies — add manually to build.gradle.kts:")
        for g in gradle_pkgs:
            logs.append(f"    implementation(\"{g}:<version>\")")

    pm = _detect_pm(project_root)
    for cmd in [
        [pm, 'install'] + npm_pkgs if npm_pkgs else [],
        [pm, 'install', '--save-dev'] + npm_dev if npm_dev else [],
    ]:
        if not cmd or len(cmd) <= 2:
            continue
        try:
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logs.append(f"✓ {pm} install: {' '.join(cmd[2:])}")
            else:
                logs.append(f"✗ {pm} error: {result.stderr.strip()[:200]}")
        except Exception as e:
            logs.append(f"✗ Failed: {e}")

    if pip_pkgs:
        try:
            result = subprocess.run(['pip3', 'install'] + pip_pkgs,
                                    cwd=project_root, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logs.append(f"✓ pip install: {' '.join(pip_pkgs)}")
            else:
                logs.append(f"✗ pip error: {result.stderr.strip()[:200]}")
        except Exception as e:
            logs.append(f"✗ pip failed: {e}")

    return logs


def _check_gradle_dep(project_root: Path, dep: str) -> bool:
    lib_name = dep.split(':')[0] if ':' in dep else dep
    for gf in list(project_root.glob('**/build.gradle.kts')) + list(project_root.glob('**/build.gradle')):
        try:
            if lib_name in gf.read_text(encoding='utf-8', errors='replace'):
                return True
        except Exception:
            continue
    return False


def _detect_pm(root: Path) -> str:
    if (root / 'bun.lock').exists() or (root / 'bunfig.toml').exists():
        return 'bun'
    if (root / 'pnpm-lock.yaml').exists():
        return 'pnpm'
    if (root / 'yarn.lock').exists():
        return 'yarn'
    return 'npm'


def _get_installed_npm(project_root: Path) -> set:
    pkg_json = project_root / 'package.json'
    if not pkg_json.exists():
        return set()
    try:
        data = json.loads(pkg_json.read_text())
        return set(data.get('dependencies', {}).keys()) | set(data.get('devDependencies', {}).keys())
    except Exception:
        return set()


def _get_installed_pip() -> set:
    try:
        result = subprocess.run(['pip3', 'list', '--format=freeze'],
                                capture_output=True, text=True, timeout=10)
        return {l.split('==')[0].lower() for l in result.stdout.splitlines() if '==' in l}
    except Exception:
        return set()


def _normalize_npm_package(raw: str) -> str:
    if not raw or raw.startswith('.') or raw.startswith('/'):
        return ''
    parts = raw.split('/')
    return '/'.join(parts[:2]) if raw.startswith('@') and len(parts) >= 2 else parts[0]


def _is_dev_dependency(pkg: str) -> bool:
    dev_keywords = {'eslint', 'prettier', 'jest', 'vitest', 'typescript', 'vite',
                    '@types/', 'babel', 'webpack', 'tailwindcss', 'postcss', 'nodemon'}
    return any(kw in pkg.lower() for kw in dev_keywords)


def _guess_env_value(var_name: str) -> str:
    name = var_name.lower()
    if 'key' in name or 'secret' in name or 'token' in name:
        return 'your_secret_here'
    if 'url' in name or 'uri' in name:
        return 'https://example.com'
    if 'port' in name:
        return '3000'
    if 'host' in name:
        return 'localhost'
    return 'your_value_here'
