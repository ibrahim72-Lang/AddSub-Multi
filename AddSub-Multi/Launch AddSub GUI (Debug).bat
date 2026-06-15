@echo off
:: Launch AddSub-Multi GUI in DEBUG mode
:: Shows console window with debug output

cd /d "%~dp0"

set "LOG_FILE=GUI_Debug_Log.txt"
echo ============================================================
echo AddSub-Multi GUI - DEBUG MODE
echo ============================================================
echo.
echo This window will show debug output from the GUI.
echo Keep it open while using the application.
echo.
echo Output is also being saved to: %LOG_FILE%
echo.
echo Starting GUI...
echo.

:: Use python.exe with -u (unbuffered) to show console output in real-time
:: Also save output to log file using PowerShell Tee
python -u AddSub-Multi-GUI.py 2>&1 | powershell -Command "$input | Tee-Object -FilePath '%LOG_FILE%'"

echo.
echo ============================================================
echo GUI closed.
echo.
echo Debug output saved to: %LOG_FILE%
echo You can open this file to see all the debug messages.
echo.
pause
