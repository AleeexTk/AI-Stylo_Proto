import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
APP_PATH = PROJECT_ROOT / "apps" / "web" / "streamlit_rpg" / "app.py"


class OneClickLauncher:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AI-Stylo • One Click Launcher")
        self.root.geometry("560x360")
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="Готово к запуску")

        title = tk.Label(
            self.root,
            text="AI-Stylo локальный запуск",
            font=("Arial", 16, "bold"),
            pady=12,
        )
        title.pack()

        subtitle = tk.Label(
            self.root,
            text="Нажмите кнопку: установка зависимостей + запуск интерфейса",
            font=("Arial", 10),
        )
        subtitle.pack()

        self.run_button = tk.Button(
            self.root,
            text="🚀 Запустить AI-Stylo",
            font=("Arial", 12, "bold"),
            padx=12,
            pady=10,
            command=self.start,
        )
        self.run_button.pack(pady=14)

        self.log = tk.Text(self.root, height=12, width=66, state=tk.DISABLED)
        self.log.pack(padx=12, pady=6)

        status = tk.Label(self.root, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=12, pady=(0, 10))

    def append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def run_cmd(self, cmd, env=None) -> None:
        self.append_log(f"$ {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(line.rstrip())

        exit_code = process.wait()
        if exit_code != 0:
            raise RuntimeError(f"Команда завершилась с ошибкой: {' '.join(cmd)}")

    def ensure_venv(self) -> Path:
        if os.name == "nt":
            python_bin = VENV_DIR / "Scripts" / "python.exe"
        else:
            python_bin = VENV_DIR / "bin" / "python"

        if not python_bin.exists():
            self.status_var.set("Создаём виртуальное окружение...")
            self.append_log("[setup] Создание .venv")
            self.run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)])

        return python_bin

    def install_requirements(self, python_bin: Path) -> None:
        self.status_var.set("Устанавливаем зависимости...")
        self.append_log("[setup] Установка зависимостей")
        self.run_cmd([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
        self.run_cmd([str(python_bin), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])

    def run_streamlit(self, python_bin: Path) -> None:
        self.status_var.set("Запускаем интерфейс проекта...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        self.run_cmd([str(python_bin), "-m", "streamlit", "run", str(APP_PATH)], env=env)

    def workflow(self) -> None:
        self.run_button.configure(state=tk.DISABLED)
        try:
            if not REQUIREMENTS_FILE.exists() or not APP_PATH.exists():
                raise FileNotFoundError("Не найдены requirements.txt или app.py. Проверьте целостность распакованного zip.")

            python_bin = self.ensure_venv()
            self.install_requirements(python_bin)
            self.run_streamlit(python_bin)
        except Exception as exc:
            self.status_var.set("Ошибка запуска")
            self.append_log(f"[error] {exc}")
            messagebox.showerror("AI-Stylo", str(exc))
        finally:
            self.run_button.configure(state=tk.NORMAL)

    def start(self) -> None:
        worker = threading.Thread(target=self.workflow, daemon=True)
        worker.start()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    OneClickLauncher().run()


if __name__ == "__main__":
    main()
