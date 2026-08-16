@echo off
chcp 65001 > nul
title EL AL-NOOR AI - Desktop Inspection System

echo ======================================================================
echo    EL AL-NOOR AI - Solar Panels Quality Inspection Platform
echo    Al Noor Solar Panels Factory - Desktop Inspection Launcher
echo ======================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH!
    pause
    exit /b 1
)

echo [INFO] Starting EL AL-NOOR AI Desktop Application...
python "%~dp0main.py"

pause
