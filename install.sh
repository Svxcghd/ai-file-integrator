#!/bin/bash
# install.sh — AI File Integrator v3 setup for Fedora KDE
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    AI File Integrator v3 — Setup         ║"
echo "║    100% local — no API key needed        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "✗ Python3 not found. Install: sudo dnf install python3"
    exit 1
fi
echo "✓ Python3: $(python3 --version)"

if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "⚠ Tkinter not found. Installing..."
    sudo dnf install -y python3-tkinter
fi
echo "✓ Tkinter OK"

if command -v kdialog &> /dev/null; then
    echo "✓ kdialog found (native KDE file browser)"
else
    echo "⚠ kdialog not found — will use Tkinter file dialog"
fi

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$HOME/.local/bin"
LAUNCHER="$HOME/.local/bin/ai-file-integrator"
cat > "$LAUNCHER" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
python3 app.py
EOF
chmod +x "$LAUNCHER"
echo "✓ Launcher: $LAUNCHER"

mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/ai-file-integrator.desktop" << EOF
[Desktop Entry]
Name=AI File Integrator
Comment=Distribute AI-generated files into your project intelligently
Exec=$LAUNCHER
Icon=system-file-manager
Terminal=false
Type=Application
Categories=Development;Utility;
Keywords=AI;files;code;project;integrator;
EOF
echo "✓ KDE app entry created"

echo ""
echo "══════════════════════════════════════════"
echo "  Done! Run with: ai-file-integrator"
echo "  Or: python3 $INSTALL_DIR/app.py"
echo "══════════════════════════════════════════"
echo ""
