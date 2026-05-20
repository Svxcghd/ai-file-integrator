"""
config.py — Saves and loads user configuration (API key, preferences).
Stored in ~/.config/ai_file_integrator/config.json
"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "ai_file_integrator"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load() -> dict:
    """Load config from disk. Returns empty dict if not found."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save(data: dict):
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_api_key() -> str:
    """Return saved API key or empty string."""
    return load().get("gemini_api_key", "")


def set_api_key(key: str):
    """Save API key."""
    cfg = load()
    cfg["gemini_api_key"] = key
    save(cfg)


def get_last_project() -> str:
    """Return last used project path."""
    return load().get("last_project", "")


def set_last_project(path: str):
    """Save last used project path."""
    cfg = load()
    cfg["last_project"] = path
    save(cfg)
