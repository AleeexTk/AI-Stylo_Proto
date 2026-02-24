#!/usr/bin/env python3
"""One-click bootstrap and launch for AI-Stylo from an unpacked zip."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

DEFAULT_OLLAMA = {
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_CHAT_MODEL": "llama3",
    "OLLAMA_EMBED_MODEL": "nomic-embed-text",
    "OLLAMA_TIMEOUT": "30",
    "USE_GOOGLE_RAG_FALLBACK": "0",
}


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)


def venv_python(venv_dir: Path) -> Path:
    if platform.system().lower().startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_streamlit(venv_dir: Path) -> Path:
    if platform.system().lower().startswith("win"):
        return venv_dir / "Scripts" / "streamlit.exe"
    return venv_dir / "bin" / "streamlit"


def bootstrap(project_root: Path, venv_dir: Path) -> tuple[Path, Path]:
    python_bin = venv_python(venv_dir)
    streamlit_bin = venv_streamlit(venv_dir)

    if not python_bin.exists():
        print("[AI-Stylo] First run detected: creating virtual environment...")
        run([sys.executable, "-m", "venv", str(venv_dir)])

    print("[AI-Stylo] Installing/updating dependencies...")
    run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_bin), "-m", "pip", "install", "-r", str(project_root / "requirements.txt")])

    return python_bin, streamlit_bin


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    for key, value in DEFAULT_OLLAMA.items():
        env.setdefault(key, value)
    return env


def app_path(project_root: Path, mode: str) -> Path:
    if mode == "b2b":
        return project_root / "apps" / "web" / "streamlit_b2b" / "app.py"
    return project_root / "apps" / "web" / "streamlit_rpg" / "app.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-Stylo one-click launcher for local unpacked repository."
    )
    parser.add_argument(
        "--mode",
        choices=["rpg", "b2b"],
        default="rpg",
        help="Which UI experience to launch (default: rpg).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    venv_dir = project_root / ".venv"

    _, streamlit_bin = bootstrap(project_root, venv_dir)

    app = app_path(project_root, args.mode)
    if not app.exists():
        print(f"[AI-Stylo] App file not found: {app}")
        sys.exit(1)

    env = build_env()
    print(f"[AI-Stylo] Launching {args.mode.upper()} interface...")
    run([str(streamlit_bin), "run", str(app)], env=env)


if __name__ == "__main__":
    main()
