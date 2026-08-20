# Build script for PyInstaller single-file binary distribution
import os
import sys
import subprocess
import shutil

def build():
    print("Building mock-forge binary...")
    templates_dir = os.path.abspath(os.path.join("src", "templates"))
    sep = ";" if sys.platform.startswith("win") else ":"
    add_data = f"{templates_dir}{sep}src/templates"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name", "mock-forge",
        "--onefile",
        "--add-data", add_data,
        "--hidden-import", "jinja2",
        "--hidden-import", "uvicorn",
        "--hidden-import", "fastapi",
        "--hidden-import", "faker",
        "--hidden-import", "yaml",
        "main.py",
    ]
    subprocess.run(cmd, check=True)
    print("Build finished. Executable is in dist/")

if __name__ == "__main__":
    build()
