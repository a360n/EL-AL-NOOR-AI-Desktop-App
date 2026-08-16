#!/usr/bin/env python3
"""
EL AL-NOOR AI - Windows Desktop Application Launcher
------------------------------------------------------
Entry point for EL AL-NOOR AI Desktop Application.
Starts the local background FastAPI server and launches a native desktop window.
Supports PyWebView, PySide6, and Native App-Window mode (Chrome/Edge App Mode) for Windows.
"""

import os
import sys
import time
import socket
import logging
import threading
import subprocess
import webbrowser
import uvicorn

# Add current folder to sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from server.app import app

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("EL_Main")


def find_free_port(start_port: int = 8000) -> int:
    """Finds an available local port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def run_server(port: int):
    """Runs Uvicorn server."""
    logger.info(f"⚡ Starting local backend on http://127.0.0.1:{port} ...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def wait_for_server(port: int, timeout: float = 8.0) -> bool:
    """Waits until server is listening on port."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def launch_native_window(url: str, title: str = "EL AL-NOOR AI ☀️🤖 - معمل النور للألواح الشمسية"):
    """
    Attempts to launch in native desktop window:
    1. pywebview if installed
    2. Google Chrome / Microsoft Edge in Standalone App Window Mode (--app=URL)
    3. Default system web browser fallback
    """
    # 1. Try pywebview
    try:
        import webview
        logger.info("🖥️ Launching PyWebView Native Desktop Window...")
        webview.create_window(
            title=title,
            url=url,
            width=1380,
            height=880,
            resizable=True,
            min_size=(1024, 700),
            background_color='#1A1A1A'
        )
        webview.start()
        return
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PyWebView launch failed: {e}")

    # 2. Try Chrome / Edge in App Window Mode (No address bar, looks 100% native desktop)
    app_launched = False
    chrome_paths = [
        # Windows Paths
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # macOS Paths
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]

    for browser_path in chrome_paths:
        if os.path.exists(browser_path):
            try:
                cmd = [browser_path, f"--app={url}", "--window-size=1400,900"]
                subprocess.Popen(cmd)
                logger.info(f"🚀 Launched in App Window Mode via: {browser_path}")
                app_launched = True
                break
            except Exception as err:
                logger.warning(f"Failed to launch {browser_path}: {err}")

    # 3. Fallback to default browser
    if not app_launched:
        logger.info("🌐 Opening in default system browser...")
        webbrowser.open(url)


def main():
    print("=" * 70)
    print("  EL AL-NOOR AI ☀️🤖 - Solar Panels Quality Inspection Platform")
    print("  Al Noor Solar Panels Factory - Desktop Application Edition v1.0.0")
    print("=" * 70)

    # 1. Check internet and apply latest updates from GitHub if available
    try:
        from core.updater import check_and_apply_update
        check_and_apply_update()
    except Exception as update_err:
        logger.warning(f"Update check skipped due to error: {update_err}")

    port = find_free_port(8000)
    server_url = f"http://127.0.0.1:{port}"

    # Start backend server in daemon thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True, name="EL_BackendServer")
    server_thread.start()

    # Wait for server readiness
    if not wait_for_server(port):
        logger.error("Failed to start backend server in time.")
        sys.exit(1)

    logger.info(f"✅ Backend server is online at: {server_url}")

    # Launch desktop window
    launch_native_window(server_url)

    # Keep main thread alive if using browser mode
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] EL AL-NOOR AI Platform closed successfully.")


if __name__ == "__main__":
    main()
