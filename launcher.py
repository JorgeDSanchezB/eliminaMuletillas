"""EliminaMuletillas — Lanzador portable para Windows.

Arranca el servidor Streamlit local (headless) y lo muestra dentro de una
ventana nativa de escritorio (WebView2), sin abrir el navegador.
Si la ventana nativa no puede abrirse, cae al navegador como plan B.
"""
import ctypes
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def log_path() -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    return base / "launcher.log"


logging.basicConfig(
    filename=log_path(),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("launcher")


def show_error(title: str, message: str) -> None:
    """Mensaje de error nativo de Windows (no requiere consola ni tkinter)."""
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        log.exception("No se pudo mostrar el mensaje de error")


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_for_server(url: str, timeout_s: float = 180) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def open_native_window(url: str) -> bool:
    """Abre la app en una ventana nativa. Devuelve True si lo logró."""
    try:
        import webview

        def _on_started() -> None:
            log.info("Ventana nativa abierta.")

        log.info("Abriendo ventana nativa...")
        webview.create_window(
            "EliminaMuletillas",
            url,
            width=1320,
            height=880,
            min_size=(1024, 700),
            background_color="#FAF5EC",
        )
        webview.start(func=_on_started, private_mode=False)
        log.info("Ventana cerrada por el usuario.")
        return True
    except Exception:
        log.exception("Fallo al abrir ventana nativa")
        return False


def main() -> int:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent

    runtime_py = base_dir / "runtime" / "python.exe"
    app_py = base_dir / "app" / "app.py"

    if not (runtime_py.is_file() and app_py.is_file()):
        show_error(
            "EliminaMuletillas",
            "No se encontró runtime\\python.exe o app\\app.py.\n\n"
            "Asegúrate de mantener el ejecutable junto a las carpetas "
            "runtime y app.",
        )
        log.error("Faltan runtime/python.exe o app/app.py en %s", base_dir)
        return 1

    env = dict(os.environ)
    extra_path = [
        str(base_dir / "bin"),       # ffmpeg / ffprobe
        str(base_dir / "runtime"),   # python embebido
        str(base_dir),
    ]
    env["PATH"] = os.pathsep.join(extra_path) + os.pathsep + env.get("PATH", "")

    port = 8501
    while not is_port_free(port) and port < 8560:
        port += 1

    cmd = [
        str(runtime_py), "-m", "streamlit", "run", str(app_py),
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--server.port", str(port),
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
    ]
    log.info("Arrancando Streamlit en el puerto %s (cwd=%s)", port, base_dir)

    proc = subprocess.Popen(cmd, cwd=str(base_dir), env=env)
    url = f"http://127.0.0.1:{port}"

    ready = wait_for_server(url)
    if not ready:
        log.error("El servidor no respondió a tiempo.")
        try:
            proc.terminate()
        except Exception:
            pass
        show_error(
            "EliminaMuletillas",
            "No se pudo iniciar el motor interno del programa.\n\n"
            f"Detalles en:\n{log_path()}",
        )
        return 1

    log.info("Servidor listo en %s", url)

    if not open_native_window(url):
        # Plan B: navegador normal.
        log.warning("Usando navegador como alternativa.")
        webbrowser.open(url)

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    log.info("Programa detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
