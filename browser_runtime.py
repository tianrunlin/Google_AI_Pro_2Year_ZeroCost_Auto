"""Chrome discovery and lifecycle helpers for macOS, Windows, and Linux."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request


def find_chrome_path() -> str:
    override = os.environ.get("CHROME_PATH")
    if override:
        return os.path.expanduser(override)
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif os.name == "nt":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = [shutil.which(name) for name in ("google-chrome", "chromium", "chromium-browser")]
    return next((p for p in candidates if p and os.path.isfile(p)), "")


def ensure_debug_port_available(port: int):
    # Never kill or attach to an unrelated browser already listening on this port.
    with socket.socket() as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # A previous Chrome connection may still be in TIME_WAIT after exit.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"调试端口 {port} 已被占用，请先停止该任务或更换端口") from exc


def launch_chrome(args: list[str]) -> subprocess.Popen:
    if not args[0] or not os.path.isfile(args[0]):
        raise RuntimeError("找不到 Chrome，请安装 Google Chrome 或设置 CHROME_PATH 为可执行文件路径")
    return subprocess.Popen(args, start_new_session=os.name != "nt")


async def wait_for_chrome(proc: subprocess.Popen, port: int, timeout: float = 20):
    def probe():
        # Bypass proxy environment variables for this local control connection.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=0.5) as response:
            return bool(json.load(response).get("webSocketDebuggerUrl"))

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Chrome 启动失败，退出码: {proc.returncode}；请先关闭该账号的独立 Chrome 窗口再重试")
        try:
            if await asyncio.to_thread(probe):
                return
        except (OSError, ValueError):
            pass
        await asyncio.sleep(0.2)
    raise RuntimeError("等待 Chrome 调试接口超时")


def stop_chrome(proc: subprocess.Popen):
    if os.name == "nt":
        if proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        proc.wait(timeout=5)
        return
    # launch_chrome creates this dedicated process group. Never use killall Chrome.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except ProcessLookupError:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
