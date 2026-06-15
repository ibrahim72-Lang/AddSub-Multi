@echo off
title Clear AddSub-Multi Queue and Locks
echo ============================================================
echo Clear AddSub-Multi Queue and Locks
echo ============================================================
echo.
echo This will clear any stuck queue tickets or locks from
echo previous sessions that didn't exit cleanly.
echo.
echo Use this if the GUI says "Another session is running"
echo but no other instance is actually running.
echo.
pause
echo.
echo Clearing queue and locks...

set "QUEUE_DIR=%LOCALAPPDATA%\AddSub-Multi\AddSub-Multi.queue"
set "LOCK_DIR=%LOCALAPPDATA%\AddSub-Multi\AddSub-Multi.lock"
set "STATE_FILE=%LOCALAPPDATA%\AddSub-Multi\subtitle_download_state.txt"

if exist "%QUEUE_DIR%" (
    del /f /q "%QUEUE_DIR%\*.ticket" >nul 2>&1
    echo - Cleared queue tickets
) else (
    echo - No queue directory found
)

if exist "%LOCK_DIR%" (
    rd /s /q "%LOCK_DIR%" >nul 2>&1
    echo - Cleared lock directory
) else (
    echo - No lock directory found
)

if exist "%STATE_FILE%" (
    del /f /q "%STATE_FILE%" >nul 2>&1
    echo - Cleared state file (defective streak + daily count reset)
) else (
    echo - No state file found
)

echo.
echo ============================================================
echo Done! You can now run the GUI.
echo ============================================================
echo.
pause
