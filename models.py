"""
models.py — Data classes for AI File Integrator v3
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


class ProjectType(Enum):
    WEB_REACT      = "Web (React/Vite)"
    REACT_NATIVE   = "Mobile (React Native/Expo)"
    ANDROID_KOTLIN = "Mobile (Android/Kotlin)"
    DJANGO         = "Django (Python)"
    NODEJS         = "Node.js"
    PYTHON         = "Python"
    UNKNOWN        = "Unknown"


class WriteStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR   = "error"
    BACKUP  = "backup"


class ConfidenceLevel(Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


@dataclass
class ProjectConfig:
    raw_content: str = ""
    project_name: str = ""
    project_type: str = ""
    rules: dict = field(default_factory=dict)

    @property
    def has_config(self) -> bool:
        return bool(self.raw_content.strip())


@dataclass
class FileDecision:
    source: Path
    destination: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    reason: str = ""
    create_folder: bool = False
    is_new_file: bool = True


@dataclass
class BackupEntry:
    original_path: Path
    backup_path: Path
    timestamp: datetime = field(default_factory=datetime.now)
    used_git: bool = False

    @property
    def timestamp_str(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d_%H-%M-%S")


@dataclass
class WriteResult:
    source: Path
    destination: Path
    status: WriteStatus
    message: str = ""
    backup: Optional[BackupEntry] = None
    created_dirs: list = field(default_factory=list)


@dataclass
class DependencyInfo:
    name: str
    package_manager: str
    is_installed: bool = False
    is_dev: bool = False


@dataclass
class EnvVarSuggestion:
    name: str
    source_file: str
    example_value: str = ""


@dataclass
class PatchResult:
    target_file: Path
    lines_changed: int = 0
    success: bool = False
    message: str = ""
    backup: Optional[BackupEntry] = None


@dataclass
class ProjectState:
    root: Path
    name: str
    project_type: ProjectType = ProjectType.UNKNOWN
    config: ProjectConfig = field(default_factory=ProjectConfig)
    tree: str = ""
    total_files: int = 0
    total_dirs: int = 0
    has_git: bool = False
    has_package_json: bool = False
    has_requirements_txt: bool = False
    detected_languages: list = field(default_factory=list)
