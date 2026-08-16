#!/usr/bin/env bash
# ======================================================================
# EL AL-NOOR AI - 1-Click Desktop Launcher for macOS
# ======================================================================

# Move to the script directory
cd "$(dirname "$0")"

echo "======================================================================"
echo "   EL AL-NOOR AI ☀️🤖 - Solar Panels Quality Inspection Platform"
echo "   Al Noor Solar Panels Factory - macOS Desktop Application"
echo "======================================================================"
echo ""

# Find Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3 is not installed or not in PATH!"
    read -p "Press Enter to exit..."
    exit 1
fi

# Run application
$PYTHON_CMD main.py
