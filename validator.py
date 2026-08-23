"""
validator.py — Runs project validation after a patch and parses errors.
"""
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from .models import ProjectType


@dataclass
class ValidationError:
    file: str
    line: int | None
    message: str
    raw: str = ""


@dataclass
class ValidationResult:
    success: bool
    project_type: ProjectType
    errors: list = field(default_factory=list)
    raw_output: str = ""
    command_used: str = ""

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def summary(self) -> str:
        if self.success:
            return "✓ Project validated successfully."
        return f"✗ {self.error_count} error(s) detected after patch."


def validate_project(root: Path, project_type: ProjectType) -> ValidationResult:
    validators = {
        ProjectType.WEB_REACT:      _validate_web,
        ProjectType.REACT_NATIVE:   _validate_react_native,
        ProjectType.DJANGO:         _validate_django,
        ProjectType.NODEJS:         _validate_node,
        ProjectType.PYTHON:         _validate_python,
        ProjectType.ANDROID_KOTLIN: _validate_android,
        ProjectType.UNKNOWN:        _validate_unknown,
    }
    return validators.get(project_type, _validate_unknown)(root)


def _run(cmd: list, cwd: Path, timeout: int = 60):
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Validation timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def _detect_pm(root: Path) -> str:
    if (root / 'bun.lock').exists() or (root / 'bunfig.toml').exists():
        return 'bun'
    if (root / 'pnpm-lock.yaml').exists():
        return 'pnpm'
    if (root / 'yarn.lock').exists():
        return 'yarn'
    return 'npm'


def _validate_web(root: Path) -> ValidationResult:
    cmd = ['npx', 'tsc', '--noEmit']
    success, output = _run(cmd, root, timeout=60)
    return ValidationResult(
        success=success, project_type=ProjectType.WEB_REACT,
        raw_output=output, command_used=' '.join(cmd),
        errors=_parse_typescript_errors(output) if not success else [],
    )


def _validate_react_native(root: Path) -> ValidationResult:
    cmd = ['npx', 'tsc', '--noEmit']
    success, output = _run(cmd, root, timeout=60)
    return ValidationResult(
        success=success, project_type=ProjectType.REACT_NATIVE,
        raw_output=output, command_used=' '.join(cmd),
        errors=_parse_typescript_errors(output) if not success else [],
    )


def _validate_django(root: Path) -> ValidationResult:
    cmd = ['python3', 'manage.py', 'check']
    success, output = _run(cmd, root, timeout=30)
    return ValidationResult(
        success=success, project_type=ProjectType.DJANGO,
        raw_output=output, command_used=' '.join(cmd),
        errors=_parse_django_errors(output) if not success else [],
    )


def _validate_python(root: Path) -> ValidationResult:
    import py_compile
    errors = []
    py_files = [f for f in root.rglob('*.py')
                if '.venv' not in str(f) and '__pycache__' not in str(f)]
    for f in py_files:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(ValidationError(file=str(f.relative_to(root)), line=None, message=str(e), raw=str(e)))
    return ValidationResult(
        success=len(errors) == 0, project_type=ProjectType.PYTHON,
        errors=errors, command_used="py_compile (syntax check)",
        raw_output="\n".join(e.raw for e in errors),
    )


def _validate_node(root: Path) -> ValidationResult:
    if (root / 'tsconfig.json').exists():
        return _validate_web(root)
    return ValidationResult(success=True, project_type=ProjectType.NODEJS, command_used="skipped")


def _validate_android(root: Path) -> ValidationResult:
    gradlew = root / 'gradlew'
    if not gradlew.exists():
        return ValidationResult(
            success=True, project_type=ProjectType.ANDROID_KOTLIN,
            command_used="skipped — gradlew not found",
        )
    cmd = ['./gradlew', 'compileDebugKotlin', '--quiet']
    success, output = _run(cmd, root, timeout=120)
    return ValidationResult(
        success=success, project_type=ProjectType.ANDROID_KOTLIN,
        raw_output=output, command_used=' '.join(cmd),
        errors=_parse_kotlin_errors(output) if not success else [],
    )


def _validate_unknown(root: Path) -> ValidationResult:
    return ValidationResult(success=True, project_type=ProjectType.UNKNOWN, command_used="skipped")


def _parse_typescript_errors(output: str) -> list:
    import re
    errors = []
    pattern = re.compile(r'^(.+?)\((\d+),\d+\):\s+error\s+\w+:\s+(.+)$', re.MULTILINE)
    for m in pattern.finditer(output):
        errors.append(ValidationError(file=m.group(1).strip(), line=int(m.group(2)), message=m.group(3).strip(), raw=m.group(0)))
    if not errors and output.strip():
        errors.append(ValidationError(file="unknown", line=None, message=output.strip()[:300], raw=output[:300]))
    return errors


def _parse_django_errors(output: str) -> list:
    errors = []
    for line in output.splitlines():
        if 'ERROR' in line or 'Error' in line:
            errors.append(ValidationError(file="django", line=None, message=line.strip(), raw=line))
    if not errors and output.strip():
        errors.append(ValidationError(file="django", line=None, message=output.strip()[:300], raw=output[:300]))
    return errors


def _parse_kotlin_errors(output: str) -> list:
    import re
    errors = []
    pattern = re.compile(r'^e:\s+(.+?):\s+\((\d+),\s*\d+\):\s+(.+)$', re.MULTILINE)
    for m in pattern.finditer(output):
        errors.append(ValidationError(file=m.group(1).strip(), line=int(m.group(2)), message=m.group(3).strip(), raw=m.group(0)))
    if not errors and output.strip():
        errors.append(ValidationError(file="unknown", line=None, message=output.strip()[:300], raw=output[:300]))
    return errors
