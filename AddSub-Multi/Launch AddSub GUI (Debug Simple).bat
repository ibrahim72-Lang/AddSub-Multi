@echo off
title AddSub-Multi GUI (Debug Mode - Simple)
echo ============================================================
echo AddSub-Multi GUI - DEBUG MODE (SIMPLE)
echo ============================================================
echo.
echo This window will show debug output from the GUI.
echo Keep it open while using the application.
echo.
echo Starting GUI...
echo.

cd /d "%~dp0"

:: Use python.exe with -u (unbuffered) to show console output in real-time
python -u AddSub-Multi-GUI.py

echo.
echo ============================================================
echo GUI closed - Press any key to close this window
echo ============================================================
pause
