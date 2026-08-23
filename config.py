"""
config.py — Saves app preferences and project tab history.
"""
import json
from pathlib import Path

CONFIG_DIR  = Path.home() / '.config' / 'ai_file_integrator'
CONFIG_FILE = CONFIG_DIR / 'config.json'


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_projects() -> list:
    return load().get('projects', [])


def add_project(path: str):
    cfg = load()
    projects = cfg.get('projects', [])
    if path not in projects:
        projects.insert(0, path)
    cfg['projects'] = projects[:10]
    save(cfg)


def remove_project(path: str):
    cfg = load()
    cfg['projects'] = [p for p in cfg.get('projects', []) if p != path]
    save(cfg)
