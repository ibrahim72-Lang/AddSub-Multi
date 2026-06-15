@echo off
echo ═══════════════════════════════════════════════════════════
echo  ADDSUBMULTI GUI - ERROR CAPTURE
echo ═══════════════════════════════════════════════════════════
echo.
echo Running GUI with full error capture...
echo If it crashes, the error will be shown here.
echo.
echo ═══════════════════════════════════════════════════════════
echo.

cd /d "%~dp0"
python AddSub-Multi-GUI.py 2>&1

echo.
echo ═══════════════════════════════════════════════════════════
echo  GUI CLOSED
echo ═══════════════════════════════════════════════════════════
echo.
echo If there was an error above, please copy it and report it.
echo.
pause
