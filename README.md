# AI File Integrator

A local desktop tool for **Fedora/Linux** that intelligently distributes AI-generated files into the correct structure of your projects — automatically, safely, and without any external API or internet connection.

> **No API key. No cloud. No subscriptions. 100% local.**

---

## The problem it solves

When you use Google AI Studio, ChatGPT, or Claude to generate code, the files land in your Downloads folder with no structure. Moving them manually to the right project folders is slow, error-prone, and breaks your flow.

AI File Integrator acts as the bridge between your AI tool and your local project — it reads the file content, understands your project structure, and places each file exactly where it belongs.

---

## How it works

```
Google AI Studio generates files
        ↓
You download them to ~/Downloads
        ↓
Open AI File Integrator → select your project
        ↓
Browse and queue the downloaded files
        ↓
Local analyzer reads content and decides where each file goes
        ↓
Review decisions (edit paths if needed)
        ↓
Confirm → files copied, backups created automatically
        ↓
Dependencies detected → npm/pip install runs automatically
```

---

## Features

### Multi-project tabs
Manage several projects simultaneously. Each tab is fully independent with its own context, file tree, and modules. The app remembers your last 3 projects and reopens them automatically.

### .aiconfig — the project brain
A plain text file you place in your project root. It tells the analyzer exactly how your project is structured and what rules to follow. Edit it directly inside the app — no external editor needed.

```
Proyecto: StudyFlow
Tipo: Web — React + Vite + TypeScript
Plataforma: WEB ÚNICAMENTE

Reglas:
Componentes → src/components/
Hooks → src/hooks/
Rutas → src/routes/
Estilos → src/styles/
Config → raíz
```

### Local intelligent analyzer
No AI API needed. Works completely offline. The analyzer:
1. Reads your `.aiconfig` rules first (highest priority)
2. Falls back to content analysis if no rule matches — reads imports, exports, decorators, class names, and patterns
3. Checks what folders actually exist in your project and adapts to your real structure

### Patch Editor with Git safety net
Instead of replacing a whole file, paste only the changed fragment. The tool finds where it fits and applies only those lines.

**Safety flow:**
1. Git checkpoint commit created before touching anything
2. Patch applied — only changed lines written
3. Project validated automatically (TypeScript, Django, Python, Kotlin)
4. If validation fails → error panel shows exactly what broke with file + line number
5. One-click **↩ Revert** restores the project to the pre-patch state instantly

### Dependency detection
After integrating files, the app scans them and:
- Detects new npm/pip/Gradle imports not yet installed
- Runs `npm install` / `pip install` automatically for missing packages
- Suggests `.env` variables found in the code (never writes them automatically)

### Automatic backup
Before overwriting any file:
- **If the project has Git** → automatic commit: `AFI pre-patch checkpoint — timestamp — filename`
- **If no Git** → copy saved to `.afi_backups/` with timestamp suffix

---

## Supported project types

| Type | Detection | Validation |
|------|-----------|------------|
| React / Vite | `vite.config.ts` | `tsc --noEmit` |
| Next.js | `next.config.ts` | `tsc --noEmit` |
| React Native / Expo | `app.json` + expo | `tsc --noEmit` |
| Android / Kotlin | `build.gradle.kts` | `gradlew compileDebugKotlin` |
| Django | `manage.py` | `manage.py check` |
| Python | `pyproject.toml` | `py_compile` |
| Node.js | `package.json` | `tsc --noEmit` |

---

## Supported file types

```
Web:       .tsx  .jsx  .ts  .js  .css  .scss  .html  .json
Mobile:    .tsx  .ts  .js  .json
Android:   .kt  .kts  .cpp  .c  .h  .xml
Config:    .env  .gitignore  .toml  .yaml  .yml
Python:    .py  .sql  .sqlite
Assets:    .png  .jpg  .svg  .ttf  .otf  .mp3  .wav
Models:    .bin  .gguf  (Whisper models → res/raw/)
```

---

## Installation (Fedora / KDE)

```bash
git clone https://github.com/yourusername/ai-file-integrator.git
cd ai-file-integrator
bash install.sh
```

The install script:
- Checks Python 3.10+
- Installs Tkinter if missing (`sudo dnf install python3-tkinter`)
- Detects kdialog (native KDE file browser)
- Creates a launcher at `~/.local/bin/ai-file-integrator`
- Adds an entry to your KDE app menu

**No Python packages to install** — the tool uses only the standard library.

### Run manually

```bash
python3 app.py
```

---

## Project structure

```
ai-file-integrator/
├── app.py                  ← Main UI — launch this
├── install.sh              ← One-click Fedora/KDE setup
└── backend/
    ├── models.py           ← Data classes (ProjectState, FileDecision, PatchOutcome...)
    ├── scanner.py          ← Scans project structure + loads .aiconfig
    ├── analyzer.py         ← Local file placement engine (no API)
    ├── writer.py           ← Safe file copy with backup
    ├── patcher.py          ← Partial patch applier with Git checkpoint + revert
    ├── validator.py        ← Post-patch project validation (tsc, manage.py, etc.)
    ├── backup.py           ← Git checkpoint + .afi_backups/ fallback
    ├── deps.py             ← Dependency detection + npm/pip install
    ├── config.py           ← Saves project history
    └── __init__.py
```

---

## The .aiconfig file

The `.aiconfig` lives in your project root and is the single source of truth for the analyzer. You edit it directly in the app's left panel.

**Rules format:**
```
Reglas:
keyword → destination/folder/
.extension → destination/folder/
```

**Real examples:**

For a **React/Vite** project:
```
Proyecto: StudyFlow
Tipo: Web — React + Vite + TypeScript + TanStack Router
Plataforma: WEB ÚNICAMENTE

Reglas:
Componentes → src/components/
Hooks → src/hooks/
Rutas → src/routes/
Estilos → src/styles/
.json → raíz
```

For an **Android/Kotlin** project:
```
Proyecto: Inscribed
Tipo: Mobile (Android/Kotlin) — Jetpack Compose + MVVM
Plataforma: ANDROID ÚNICAMENTE

Reglas:
# Rules use simple keywords only
# Free-text hints are ignored by the parser
# Content-based rules (ViewModel, @Entity, etc.) are automatic
```

> **Tip:** For Android projects the content-based analyzer handles most decisions automatically (`@Entity` → `data/local/entity/`, `@Composable` + Screen → `ui/screens/`, `ViewModel` → `viewmodel/`, etc.). The `.aiconfig` is most useful for web/RN projects where conventions vary.

---

## Patch Editor — how to use

1. Open the **✏️ Patch** tab
2. Click **Browse** → select the file you want to edit in your project
3. Paste the new code fragment (a function, a block, a class — not loose lines)
4. Click **👁 Preview Diff** → see exactly what lines change before committing
5. Click **✓ Apply Patch**
   - A Git checkpoint is created (or `.afi_backups/` copy if no Git)
   - The patch is applied
   - The project is validated automatically
6. If errors are detected:
   - **↩ Revert Patch** — one click, instant rollback to the checkpoint
   - **✎ Keep & Fix Manually** — keep the change and fix the error yourself

**For best results:** ask your AI tool to always give you the complete function or block, not just a few loose lines. A good prompt to add to Google AI Studio:

```
Always give me the complete function or block when editing existing files.
Never use "..." or "// rest of code here". Never omit unchanged parts.
```

---

## Roadmap

- [ ] Git integration for the tool itself (`git pull` to update)
- [ ] Windows support
- [ ] RPM package for Fedora
- [ ] Real drag & drop (pending Python 3.14 compatible library)
- [ ] Backup history viewer with one-click restore from inside the app
- [ ] Support for `yarn`, `pnpm`, `poetry` package managers
- [ ] Forsetih project support (stack TBD)

---

## Requirements

- Python 3.10+
- Fedora Linux (KDE Plasma recommended)
- Git (optional — enables checkpoint commits and instant revert)
- No external Python packages required

---

## License

MIT — use it, modify it, share it.
