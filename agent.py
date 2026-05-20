"""
agent.py — Sends file content + project structure to Gemini API
and gets back a placement decision (where the file should go).
"""
import json
import mimetypes
from pathlib import Path
from google import genai
from google.genai import types


SYSTEM_PROMPT = """
You are an expert software project file organizer.

You will receive:
1. The complete directory structure of a software project
2. The project type (Django, React, Next.js, etc.)
3. The content or description of a file that needs to be placed

Your job is to decide exactly where this file belongs inside the project.

Rules:
- Analyze the FILE CONTENT deeply, not just the filename
- Respect the existing project conventions and structure
- If a logical folder exists, use it
- If no folder exists but one should be created, say so
- Never place files outside the project root
- For binary files (images, fonts, audio), analyze the file type and place accordingly
- For code files, analyze what the code does and place accordingly

Respond ONLY with a valid JSON object, no extra text, no markdown:
{
  "destination": "relative/path/to/filename.ext",
  "create_folder": true or false,
  "confidence": "high" or "medium" or "low",
  "reason": "Brief explanation of why this location"
}
"""


def read_file_content(file_path: Path) -> tuple[str, bool]:
    """
    Read file content. Returns (content_str, is_binary).
    For binary files returns a description instead of raw bytes.
    """
    mime, _ = mimetypes.guess_type(str(file_path))

    binary_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico',
        '.mp3', '.wav', '.ogg', '.flac',
        '.mp4', '.avi', '.mov', '.mkv',
        '.ttf', '.otf', '.woff', '.woff2',
        '.zip', '.tar', '.gz', '.rar',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.exe', '.so', '.dll', '.bin',
        '.db', '.sqlite', '.sqlite3',
    }

    suffix = file_path.suffix.lower()

    if suffix in binary_extensions:
        size_kb = file_path.stat().st_size / 1024
        return (
            f"[BINARY FILE]\nType: {mime or suffix}\nSize: {size_kb:.1f} KB\nFilename: {file_path.name}",
            True
        )

    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
        if len(content) > 8000:
            content = content[:8000] + "\n... [truncated]"
        return content, False
    except Exception:
        size_kb = file_path.stat().st_size / 1024
        return f"[BINARY FILE]\nType: {mime or suffix}\nSize: {size_kb:.1f} KB\nFilename: {file_path.name}", True


def ask_gemini(
    api_key: str,
    file_path: Path,
    project_tree: str,
    project_type: str,
    aiconfig: str = "",
) -> dict:
    """
    Send file + project context to Gemini and get placement decision.
    Returns a dict with destination, create_folder, confidence, reason.
    """
    client = genai.Client(api_key=api_key)

    content, is_binary = read_file_content(file_path)

    aiconfig_section = f"""
PROJECT CONTEXT (.aiconfig):
{aiconfig}
""" if aiconfig else ""

    user_message = f"""
PROJECT TYPE: {project_type}
{aiconfig_section}
PROJECT STRUCTURE:
{project_tree}

FILE TO PLACE:
Filename: {file_path.name}
{"Type: Binary file" if is_binary else "Content:"}

{content}

Where should this file go in the project?
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
            ),
        )

        raw = response.text.strip()

        # Strip markdown code fences if Gemini adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        required = {"destination", "create_folder", "confidence", "reason"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields in response: {result}")

        return result

    except json.JSONDecodeError as e:
        return {
            "destination": f"_uncategorized/{file_path.name}",
            "create_folder": True,
            "confidence": "low",
            "reason": f"Could not parse AI response: {e}",
            "error": True,
        }
    except Exception as e:
        return {
            "destination": f"_uncategorized/{file_path.name}",
            "create_folder": True,
            "confidence": "low",
            "reason": f"AI error: {e}",
            "error": True,
        }
