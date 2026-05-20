# AI File Integrator v1

this tool optimize workflows with files generates from AI like Chatgpt from the web and put it where belongs in your local proyect ---> Drag files downloaded from AI → the app analyzes their content with Gemini → decides where they go in your project → you configurate and approve the copy of the files

## Install (Fedora)

```bash
bash install.sh
```

That's it. The script installs everything and creates a launcher in your KDE app menu.

## Manual install (if preferred)

```bash
pip3 install --user google-generativeai tkinterdnd2
python3 app.py
```

## How to use

1. Open the app
2. Click **Choose Project Folder** → select your project
3. Paste your **Gemini API key** and click Save
4. **Drag files** from your Downloads into the drop zone (or click Browse)
5. Click **⚡ Analyze Files** — Gemini reads each file's content and decides where it goes
6. Review the decisions in the **AI Decisions** tab (you can edit the path if needed)
7. Click **✓ Confirm All** — files get **copied** into your project (originals stay in Downloads)

## Getting your free Gemini API key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** (top left)
3. Click **Create API Key**
4. Copy the key and paste it in the app

The free tier gives you 1,500 requests/day — more than enough.

## Project structure

```
ai_file_integrator_v2/
├── app.py        ← Main UI (run this)
├── agent.py      ← Talks to Gemini API
├── scanner.py    ← Scans your project structure
├── mover.py      ← Safely copies files to destination
├── config.py     ← Saves your API key and preferences
└── install.sh    ← One-click setup for Fedora
```

## Safety

- Files are **copied**, not moved — your Downloads folder stays intact
- All destinations are validated to stay inside the project root
- Path traversal (`../`) and absolute paths are blocked
- If AI is unsure, it places the file in `_uncategorized/` and marks confidence as low
