#!/usr/bin/env python3
"""
EL AL-NOOR AI - Automated Windows Executable (.exe) Builder
------------------------------------------------------------
Runs PyInstaller to compile the desktop application into a standalone Windows .exe package.
"""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SCRIPT_DIR)
SPEC_FILE = os.path.join(SCRIPT_DIR, "el_alnoor_ai.spec")

def build():
    print("=" * 70)
    print("  EL AL-NOOR AI ☀️🤖 - Windows .exe Build System  ")
    print("=" * 70)

    # Check PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller is available.")
    except ImportError:
        print("❌ PyInstaller not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print(f"\n📦 Compiling desktop application from spec: {SPEC_FILE} ...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", os.path.join(APP_DIR, "dist"),
        "--workpath", os.path.join(APP_DIR, "build"),
        SPEC_FILE
    ]

    result = subprocess.run(cmd)
    if result.returncode == 0:
        dist_dir = os.path.join(APP_DIR, "dist", "EL_ALNOOR_AI_Desktop")
        print("\n" + "=" * 70)
        print("🎉 اكتمل بناء التطبيق المكتبي بنجاح!")
        print(f"📁 مجلد التطبيق القابل للتشغيل: {dist_dir}")
        print(f"🚀 ملف التشغيل: {os.path.join(dist_dir, 'EL_ALNOOR_AI.exe')}")
        print("=" * 70)
    else:
        print(f"\n❌ فشل التجميع برمز خطأ: {result.returncode}")

if __name__ == "__main__":
    build()
