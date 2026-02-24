import subprocess
import sys
from pathlib import Path


def detect_project_dir(base: Path) -> Path:
    candidates = [base / "AI-Stylo-main", base]
    for candidate in candidates:
        if (candidate / "launcher.py").exists() and (candidate / "requirements.txt").exists():
            return candidate
    raise FileNotFoundError(
        "Не удалось найти папку проекта. Ожидался launcher.py и requirements.txt в текущей папке "
        "или в подпапке AI-Stylo-main."
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    try:
        project_dir = detect_project_dir(root)
    except FileNotFoundError as exc:
        print(f"[error] {exc}")
        return 1

    launcher = project_dir / "launcher.py"
    cmd = [sys.executable, str(launcher), *sys.argv[1:]]
    print(f"[info] Запуск из: {project_dir}")

    result = subprocess.run(cmd, cwd=project_dir)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
