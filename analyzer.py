"""
analyzer.py — Local intelligent file placement analyzer.
No external API. Uses .aiconfig rules + content analysis + project structure.
Supports: React/Vite, React Native, Django, Python, Node.js, Android/Kotlin.
"""
import re
from pathlib import Path
from .models import FileDecision, ProjectState, ProjectType, ConfidenceLevel


def analyze(file_path: Path, state: ProjectState) -> FileDecision:
    if state.config.has_config:
        decision = _check_aiconfig_rules(file_path, state)
        if decision:
            return decision
    return _analyze_locally(file_path, state)


def _check_aiconfig_rules(file_path: Path, state: ProjectState):
    content = state.config.raw_content
    ext  = file_path.suffix.lower()
    name = file_path.name.lower()
    stem = file_path.stem.lower()

    in_rules_block = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith('reglas') or lowered.startswith('rules'):
            in_rules_block = True
            continue
        if line.startswith('═') or (line.endswith(':') and line.isupper()):
            in_rules_block = False
            continue
        if not in_rules_block:
            continue
        if line.startswith('#') or '"' in line or "'" in line:
            continue
        if '→' not in line and '->' not in line:
            continue

        sep = '→' if '→' in line else '->'
        parts = line.split(sep, 1)
        if len(parts) != 2:
            continue

        keyword     = parts[0].strip().lower()
        dest_folder = parts[1].strip().rstrip('/')

        if len(keyword.split()) > 3:
            continue

        matched = False
        if keyword.startswith('.'):
            matched = (ext == keyword)
        elif keyword == stem or keyword == name:
            matched = True
        elif _keyword_matches_file(keyword, file_path):
            matched = True

        if matched:
            dest   = f"{dest_folder}/{file_path.name}"
            exists = (state.root / dest_folder).exists()
            return FileDecision(
                source=file_path, destination=dest,
                confidence=ConfidenceLevel.HIGH,
                reason=f"Matched .aiconfig rule: '{line}'",
                create_folder=not exists,
                is_new_file=not (state.root / dest).exists(),
            )
    return None


def _keyword_matches_file(keyword: str, file_path: Path) -> bool:
    stem = file_path.stem.lower()
    ext  = file_path.suffix.lower()
    keyword_map = {
        'componente': ['.tsx', '.jsx'], 'component':  ['.tsx', '.jsx'],
        'hook':       ['.ts', '.js'],   'hooks':      ['.ts', '.js'],
        'estilo':     ['.css', '.scss'],'style':      ['.css', '.scss'],
        'styles':     ['.css', '.scss'],'config':     ['.json', '.toml', '.yaml'],
        'ruta':       ['.tsx', '.ts'],  'route':      ['.tsx', '.ts'],
        'routes':     ['.tsx', '.ts'],  'tipo':       ['.ts'],
        'type':       ['.ts'],          'types':      ['.ts'],
        'modelo':     ['.py', '.ts'],   'model':      ['.py', '.ts'],
        'vista':      ['.py', '.html'], 'view':       ['.py', '.html'],
        'plantilla':  ['.html'],        'template':   ['.html'],
    }
    allowed = keyword_map.get(keyword, [])
    if allowed and ext not in allowed:
        return False
    if keyword in ('hook', 'hooks') and not stem.startswith('use'):
        return False
    return bool(allowed)


def _analyze_locally(file_path: Path, state: ProjectState) -> FileDecision:
    ext  = file_path.suffix.lower()
    name = file_path.name
    content = _read_content(file_path)

    ROOT_FILES = {
        'package.json', 'tsconfig.json', 'vite.config.ts', 'vite.config.js',
        'bunfig.toml', 'babel.config.js', '.eslintrc', 'eslint.config.js',
        '.prettierrc', 'tailwind.config.js', 'tailwind.config.ts',
        'next.config.js', 'next.config.ts', 'app.json', 'eas.json',
        'wrangler.jsonc', 'requirements.txt', 'pyproject.toml', 'setup.py',
        'Makefile', 'Dockerfile', 'docker-compose.yml', '.gitignore',
        '.env', '.env.local', '.env.example', 'README.md', 'LICENSE',
        'build.gradle.kts', 'settings.gradle.kts', 'gradle.properties',
    }
    if name in ROOT_FILES:
        return FileDecision(
            source=file_path, destination=name,
            confidence=ConfidenceLevel.HIGH,
            reason=f"'{name}' is a root-level config file",
            create_folder=False,
            is_new_file=not (state.root / name).exists(),
        )

    if ext == '.env' or name.startswith('.env'):
        return FileDecision(source=file_path, destination=name,
            confidence=ConfidenceLevel.HIGH, reason="Environment file → root",
            create_folder=False, is_new_file=not (state.root / name).exists())

    if ext in ('.sql', '.sqlite', '.sqlite3', '.db'):
        folder = _find_folder(state.root, ['database', 'db', 'migrations', 'prisma']) or \
                 ('migrations' if state.project_type == ProjectType.DJANGO else 'database')
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"Database file → {folder}/")

    if ext == '.py':
        return _analyze_python(file_path, state, content)

    if ext in ('.kt', '.kts'):
        return _analyze_kotlin(file_path, state, content)

    if ext in ('.cpp', '.cc', '.c', '.h', '.hpp'):
        folder = _find_folder(state.root, ['app/src/main/cpp', 'cpp', 'jni']) or 'app/src/main/cpp'
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"Native C/C++ → {folder}/")

    if name == 'CMakeLists.txt':
        folder = _find_folder(state.root, ['app/src/main/cpp', 'cpp']) or 'app/src/main/cpp'
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, "CMake build file → native folder")

    if name == 'AndroidManifest.xml':
        folder = _find_folder(state.root, ['app/src/main']) or 'app/src/main'
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, "Android manifest → app/src/main/")

    if ext in ('.bin', '.gguf') and state.project_type == ProjectType.ANDROID_KOTLIN:
        folder = _find_folder(state.root, ['app/src/main/res/raw']) or 'app/src/main/res/raw'
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, "Whisper model → res/raw/")

    if ext in ('.ts', '.tsx', '.js', '.jsx'):
        return _analyze_js_ts(file_path, state, content, ext)

    if ext in ('.css', '.scss', '.sass', '.less'):
        folder = _find_folder(state.root, ['src/styles', 'styles', 'src/css']) or 'src/styles'
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"Style file → {folder}/")

    if ext == '.html':
        if state.project_type == ProjectType.DJANGO:
            folder = _find_folder(state.root, ['templates']) or 'templates'
        else:
            folder = _find_folder(state.root, ['public', 'src']) or 'public'
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"HTML → {folder}/")

    IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg'}
    FONT_EXTS  = {'.ttf', '.otf', '.woff', '.woff2'}
    AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac'}

    if ext in IMAGE_EXTS:
        is_mobile = state.project_type == ProjectType.REACT_NATIVE
        folder = _find_folder(state.root, ['assets/images', 'public/images', 'assets', 'public']) or \
                 ('assets/images' if is_mobile else 'public/images')
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"Image → {folder}/")

    if ext in FONT_EXTS:
        folder = _find_folder(state.root, ['assets/fonts', 'public/fonts']) or 'assets/fonts'
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"Font → {folder}/")

    if ext in AUDIO_EXTS:
        folder = _find_folder(state.root, ['assets/sounds', 'public/sounds']) or 'public/sounds'
        return _decision(file_path, state.root, folder, ConfidenceLevel.MEDIUM, f"Audio → {folder}/")

    return FileDecision(
        source=file_path, destination=f"_uncategorized/{name}",
        confidence=ConfidenceLevel.LOW,
        reason="Could not determine placement — please review",
        create_folder=True, is_new_file=True,
    )


def _analyze_python(file_path: Path, state: ProjectState, content: str) -> FileDecision:
    name = file_path.name
    patterns = [
        (['def test_', 'import pytest', 'import unittest'], 'tests/'),
        (['models.Model', 'db.Model'], None),
        (['urlpatterns', 'path(', 're_path('], None),
        (['serializers.Serializer'], None),
        (['admin.site.register'], None),
        (['def get(self', 'def post(self'], None),
        (['celery', 'shared_task', '@task'], 'tasks/'),
    ]
    name_hints_map = {
        'tests/': ('tests', 'test'),
        None: None,
    }
    django_names = {
        'models.Model':          'models',
        'urlpatterns':           'urls',
        'serializers.Serializer':'serializers',
        'admin.site.register':   'admin',
        'def get(self':          'views',
    }
    for keywords, forced_folder in patterns:
        if any(kw in content for kw in keywords):
            if forced_folder:
                folder = _find_folder(state.root, [forced_folder.rstrip('/')]) or forced_folder.rstrip('/')
                return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"Python {folder} file")
            for kw, hint in django_names.items():
                if kw in content and hint:
                    app_folder = _find_django_app(state.root)
                    dest = f"{app_folder}/{hint}.py" if app_folder else f"{hint}.py"
                    return FileDecision(
                        source=file_path, destination=dest,
                        confidence=ConfidenceLevel.HIGH,
                        reason=f"Django {hint} file detected",
                        create_folder=False,
                        is_new_file=not (state.root / dest).exists(),
                    )

    folder = _find_folder(state.root, ['utils', 'lib', 'helpers', 'src']) or 'utils'
    return _decision(file_path, state.root, folder, ConfidenceLevel.LOW, "Generic Python → utils/")


def _analyze_kotlin(file_path: Path, state: ProjectState, content: str) -> FileDecision:
    name = file_path.name
    base = _find_folder(state.root, [
        'app/src/main/java/com/alberto/inscribed',
        'app/src/main/java', 'app/src/main/kotlin'
    ]) or 'app/src/main/java/com/alberto/inscribed'

    checks = [
        (lambda: name in ('Color.kt', 'Theme.kt', 'Type.kt', 'Shape.kt'), f"{base}/ui/theme", "Compose theme → ui/theme/"),
        (lambda: '@Entity' in content, f"{base}/data/local/entity", "Room @Entity → data/local/entity/"),
        (lambda: '@Dao' in content, f"{base}/data/local/dao", "Room @Dao → data/local/dao/"),
        (lambda: '@Database' in content, f"{base}/data/local/database", "Room @Database → data/local/database/"),
        (lambda: 'Repository' in name or bool(re.search(r'class\s+\w*Repository', content)),
            f"{base}/data/repository", "Repository → data/repository/"),
        (lambda: bool(re.search(r':\s*(AndroidViewModel|ViewModel)\s*\(', content)) or 'ViewModel' in name,
            f"{base}/viewmodel", "ViewModel → viewmodel/"),
        (lambda: bool(re.search(r':\s*Service\s*[\(\{]', content)),
            f"{base}/service", "Android Service → service/"),
        (lambda: 'whisper' in name.lower() or 'whisper' in content.lower() or 'external fun' in content,
            f"{base}/whisper", "Whisper/JNI → whisper/"),
        (lambda: any(kw in content for kw in ['AudioRecord', 'MediaRecorder', 'AudioFormat']),
            f"{base}/audio", "Audio capture → audio/"),
        (lambda: '@Composable' in content and ('Screen' in name or 'Screen(' in content),
            f"{base}/ui/screens", "Compose screen → ui/screens/"),
        (lambda: '@Composable' in content,
            f"{base}/ui/components", "Compose component → ui/components/"),
        (lambda: '@Module' in content or '@HiltAndroidApp' in content,
            f"{base}/di", "DI module → di/"),
    ]

    for condition, folder, reason in checks:
        if condition():
            return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, reason)

    return _decision(file_path, state.root, f"{base}/utils", ConfidenceLevel.LOW, "Generic Kotlin → utils/")


def _analyze_js_ts(file_path: Path, state: ProjectState, content: str, ext: str) -> FileDecision:
    name   = file_path.name
    stem   = file_path.stem.lower()
    mobile = state.project_type == ProjectType.REACT_NATIVE

    if stem.startswith('use'):
        folder = _find_folder(state.root, ['src/hooks', 'hooks']) or ('hooks' if mobile else 'src/hooks')
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"Hook → {folder}/")

    if any(kw in content for kw in ['create(', 'createSlice', 'createStore', 'createContext', 'useReducer']):
        folder = _find_folder(state.root, ['src/store', 'store', 'src/context', 'context']) or \
                 ('store' if mobile else 'src/store')
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"State management → {folder}/")

    if any(kw in content for kw in ['createRoute', 'createRootRoute', 'Route', 'useNavigate', 'useParams']):
        folder = _find_folder(state.root, ['src/routes', 'routes', 'app']) or \
                 ('app' if mobile else 'src/routes')
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"Route → {folder}/")

    if ext == '.ts' and any(kw in content for kw in ['interface ', 'type ', 'enum ']):
        if not any(kw in content for kw in ['export default function', 'export const', 'import React']):
            folder = _find_folder(state.root, ['src/types', 'types']) or ('types' if mobile else 'src/types')
            return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"Types → {folder}/")

    if ext in ('.tsx', '.jsx') or ('return (' in content and '<' in content):
        if mobile:
            feature = _detect_feature(name, content)
            folder = _find_folder(state.root, [f'features/{feature}/components']) if feature else None
            folder = folder or _find_folder(state.root, ['components/ui', 'components']) or 'components'
        else:
            folder = _find_folder(state.root, ['src/components', 'components']) or 'src/components'
        return _decision(file_path, state.root, folder, ConfidenceLevel.HIGH, f"React component → {folder}/")

    folder = _find_folder(state.root, ['src/lib', 'src/utils', 'lib', 'utils']) or \
             ('utils' if mobile else 'src/lib')
    return _decision(file_path, state.root, folder, ConfidenceLevel.LOW, f"Generic TS/JS → {folder}/")


def _decision(file_path: Path, root: Path, folder: str, confidence: ConfidenceLevel, reason: str) -> FileDecision:
    dest = f"{folder}/{file_path.name}"
    return FileDecision(
        source=file_path, destination=dest,
        confidence=confidence, reason=reason,
        create_folder=not (root / folder).exists(),
        is_new_file=not (root / dest).exists(),
    )


def _find_folder(root: Path, candidates: list) -> str | None:
    for candidate in candidates:
        if '*' in candidate:
            matches = list(root.glob(candidate))
            if matches:
                return str(matches[0].relative_to(root))
        elif (root / candidate).exists():
            return candidate
    return None


def _find_django_app(root: Path) -> str | None:
    for d in root.iterdir():
        if d.is_dir() and (d / 'models.py').exists():
            return d.name
    return None


def _detect_feature(filename: str, content: str) -> str | None:
    feature_keywords = {
        'cheatsheet': ['cheatsheet', 'sheet', 'snippet', 'code'],
        'search':     ['search', 'query', 'filter', 'fuse'],
        'auth':       ['auth', 'login', 'signup', 'user', 'password'],
        'categories': ['categor', 'tag', 'label'],
        'timer':      ['timer', 'pomodoro', 'session', 'break'],
        'profile':    ['profile', 'settings', 'preferences'],
    }
    text = (filename + content).lower()
    for feature, keywords in feature_keywords.items():
        if any(kw in text for kw in keywords):
            return feature
    return None


def _read_content(file_path: Path, max_chars: int = 6000) -> str:
    BINARY_EXTS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico',
        '.mp3', '.wav', '.ogg', '.ttf', '.otf', '.woff', '.woff2',
        '.zip', '.tar', '.gz', '.pdf', '.exe', '.so', '.dll',
        '.sqlite', '.sqlite3', '.db', '.bin', '.gguf',
    }
    if file_path.suffix.lower() in BINARY_EXTS:
        return ''
    try:
        return file_path.read_text(encoding='utf-8', errors='replace')[:max_chars]
    except Exception:
        return ''
