#!/bin/bash
# install.sh — AI File Integrator setup for Fedora
# Run with: bash install.sh

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     AI File Integrator — Setup       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "✗ Python3 not found. Install it with: sudo dnf install python3"
    exit 1
fi
echo "✓ Python3 found: $(python3 --version)"

# Check tkinter
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "⚠ Tkinter not found. Installing..."
    sudo dnf install -y python3-tkinter
fi
echo "✓ Tkinter available"

# Install pip packages
echo ""
echo "Installing Python dependencies..."
pip3 install --user google-generativeai tkinterdnd2

echo ""
echo "✓ Dependencies installed"

# Create launcher script
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HOME/.local/bin/ai-file-integrator"

mkdir -p "$HOME/.local/bin"

cat > "$LAUNCHER" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
python3 app.py
EOF

chmod +x "$LAUNCHER"
echo "✓ Launcher created at $LAUNCHER"

# Create .desktop file for KDE app menu
DESKTOP_FILE="$HOME/.local/share/applications/ai-file-integrator.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=AI File Integrator
Comment=Intelligently distribute AI-generated files into your project
Exec=$LAUNCHER
Icon=system-file-manager
Terminal=false
Type=Application
Categories=Development;Utility;
Keywords=AI;files;code;project;
EOF

echo "✓ Desktop entry created (find it in your KDE app launcher)"
echo ""
echo "══════════════════════════════════════"
echo "  Setup complete!"
echo "  Run with:  ai-file-integrator"
echo "  Or:        python3 $INSTALL_DIR/app.py"
echo "══════════════════════════════════════"
echo ""
