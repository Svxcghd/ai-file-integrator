# AI File Integrator
A desktop utility for Fedora/Linux that intelligently distributes AI-generated files into your local project structure using Gemini AI analysis.
Instead of manually moving files one by one, drop them into the app — Gemini reads the file content, understands your project structure, and decides exactly where each file belongs.
## How it works
```
Download or save the programming files  →  Drop into the app  →  Gemini analyzes content  →  Review decisions  →  Confirm
```

## Features
- **Content-based analysis** — Gemini reads the actual file content, not just the filename
- **Project-aware** — scans your project structure before making decisions
- **`.aiconfig` support** — add a config file to each project to give Gemini extra context
- **Preview before writing** — review every decision before anything gets moved
- **Safe by design** — files are copied, originals stay untouched
- **KDE native** — uses kdialog for file browsing on KDE Plasma
- **Auto-creates folders** — if a folder doesn't exist, it gets created automatically

## Requirements

- Python 3.10+
- Fedora Linux (KDE Plasma recommended)
- Gemini API key (free tier — 1,500 requests/day)

## Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/ai-file-integrator.git
cd ai-file-integrator
# Install dependencies
python3 -m pip install --user google-genai
# Run
python3 app.py
```

## Getting your free Gemini API key
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → **Create API Key**
3. Copy the key and paste it in the app under the API Key field
4. Click **Save API Key**

> The free tier gives you 1,500 requests/day at no cost.
> A Google Cloud billing account may be required to activate the API.

## Project Structure
```
ai-file-integrator/
├── app.py           ← Main UI (run this)
├── agent.py         ← Gemini API integration
├── scanner.py       ← Project structure scanner
├── mover.py         ← Safe file copy engine
├── config.py        ← API key and preferences storage
└── install.sh       ← One-click setup for Fedora
```
## .aiconfig — Project Context

Place a `.aiconfig` file in your project root to give Gemini extra context about your project. This prevents Gemini from confusing similar files across different projects for more compatibility tell the gemini to make this file about your proyect and put it in your proyect files.
```
Proyect: MyApp
Type: React Native mobile app
Platform: Mobile only — NOT web

Structure:
- features/cheatsheets/components/ → feature components
- components/ui/                   → global reusable components
- hooks/                           → global hooks

Notes:
- No public/ folder (that's web)
- No CSS files (uses NativeWind)
```
## Roadmap

- [ ] Windows support
- [ ] RPM package for Fedora
- [ ] Real drag & drop (pending Python 3.14 compatible library)
- [ ] Git integration
- [ ] Multi-project profiles
- [ ] Batch processing
## License

MIT
