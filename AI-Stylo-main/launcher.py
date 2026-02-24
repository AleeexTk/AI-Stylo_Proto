import os
import queue
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
APP_PATH = PROJECT_ROOT / "apps" / "web" / "streamlit_rpg" / "app.py"


class LauncherCore:
    def __init__(self, log_fn=print, status_fn=print):
        self.log_fn = log_fn
        self.status_fn = status_fn

    def run_cmd(self, cmd, env=None) -> None:
        self.log_fn(f"$ {' '.join(cmd)}")
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
            self.log_fn(line.rstrip())

        exit_code = process.wait()
        if exit_code != 0:
            raise RuntimeError(f"Команда завершилась с ошибкой: {' '.join(cmd)}")

    def has_pip(self, python_bin: Path) -> bool:
        check = subprocess.run(
            [str(python_bin), "-m", "pip", "--version"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return check.returncode == 0

    def install_pip_via_get_pip(self, python_bin: Path) -> None:
        get_pip_path = PROJECT_ROOT / "get-pip.py"
        self.log_fn("[setup] Пытаемся установить pip через get-pip.py")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_path)
        try:
            self.run_cmd([str(python_bin), str(get_pip_path)])
        finally:
            if get_pip_path.exists():
                get_pip_path.unlink()

    def ensure_pip(self, python_bin: Path) -> None:
        if self.has_pip(python_bin):
            return

        self.status_fn("Восстанавливаем pip в .venv...")
        self.log_fn("[setup] pip не найден, запускаем ensurepip")
        try:
            self.run_cmd([str(python_bin), "-m", "ensurepip", "--upgrade"])
        except Exception as exc:
            self.log_fn(f"[warn] ensurepip не сработал: {exc}")

        if not self.has_pip(python_bin):
            self.install_pip_via_get_pip(python_bin)

        if not self.has_pip(python_bin):
            raise RuntimeError(
                "pip не удалось установить в виртуальное окружение. "
                "Проверьте установку Python (должен быть полноценный installer, не embeddable build)."
            )

    def ensure_venv(self) -> Path:
        if os.name == "nt":
            python_bin = VENV_DIR / "Scripts" / "python.exe"
        else:
            python_bin = VENV_DIR / "bin" / "python"

        if not python_bin.exists():
            self.status_fn("Создаём виртуальное окружение...")
            self.log_fn("[setup] Создание .venv")
            self.run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)])

        self.ensure_pip(python_bin)
        return python_bin

    def install_requirements(self, python_bin: Path) -> None:
        self.status_fn("Устанавливаем зависимости...")
        self.log_fn("[setup] Установка зависимостей")
        self.run_cmd([str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
        self.run_cmd([str(python_bin), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])

    def run_streamlit(self, python_bin: Path) -> None:
        self.status_fn("Запускаем интерфейс проекта...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        self.run_cmd([str(python_bin), "-m", "streamlit", "run", str(APP_PATH)], env=env)

    def run(self) -> None:
        if not REQUIREMENTS_FILE.exists() or not APP_PATH.exists():
            raise FileNotFoundError(
                "Не найдены requirements.txt или app.py. Проверьте целостность распакованного zip."
            )

        python_bin = self.ensure_venv()
        self.install_requirements(python_bin)
        self.run_streamlit(python_bin)


def run_cli_mode() -> int:
    core = LauncherCore()
    try:
        core.run()
    except Exception as exc:
        print(f"[error] {exc}")
        return 1
    return 0


def run_gui_mode() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        print("[warn] Tkinter недоступен. Переключаемся в консольный режим запуска.")
        return run_cli_mode()

    class OneClickLauncher:
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("AI-Stylo • One Click Launcher")
            self.root.geometry("560x360")
            self.root.resizable(False, False)

            self.status_var = tk.StringVar(value="Готово к запуску")
            self.queue = queue.Queue()

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

            self.root.after(100, self.process_queue)

        def append_log(self, text: str) -> None:
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, text + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        def process_queue(self) -> None:
            while True:
                try:
                    event, payload = self.queue.get_nowait()
                except queue.Empty:
                    break

                if event == "log":
                    self.append_log(payload)
                elif event == "status":
                    self.status_var.set(payload)
                elif event == "error":
                    self.status_var.set("Ошибка запуска")
                    self.append_log(f"[error] {payload}")
                    messagebox.showerror("AI-Stylo", payload)
                    self.run_button.configure(state=tk.NORMAL)
                elif event == "done":
                    self.status_var.set("Процесс завершён")
                    self.run_button.configure(state=tk.NORMAL)

            self.root.after(100, self.process_queue)

        def worker(self) -> None:
            core = LauncherCore(
                log_fn=lambda msg: self.queue.put(("log", msg)),
                status_fn=lambda msg: self.queue.put(("status", msg)),
            )
            try:
                core.run()
                self.queue.put(("done", None))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        def start(self) -> None:
            self.run_button.configure(state=tk.DISABLED)
            t = threading.Thread(target=self.worker, daemon=True)
            t.start()

        def run(self) -> None:
            self.root.mainloop()

    OneClickLauncher().run()
    return 0


def main() -> None:
    use_cli = "--cli" in sys.argv
    code = run_cli_mode() if use_cli else run_gui_mode()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
