#!/usr/bin/env bash
set -e

echo "Building standalone Mock Forge executable with PyInstaller..."
if command -v pyinstaller >/dev/null 2>&1; then
    pyinstaller mock-forge.spec --clean --noconfirm
elif [ -f ".venv/bin/pyinstaller" ]; then
    .venv/bin/pyinstaller mock-forge.spec --clean --noconfirm
else
    echo "PyInstaller not found in PATH or .venv. Installing or running via python module..."
    python3 -m PyInstaller mock-forge.spec --clean --noconfirm
fi

echo "Build complete. Executable generated at dist/mock-forge"
