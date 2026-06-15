@echo off
setlocal enabledelayedexpansion
title Video to MP4 Converter

echo ============================================
echo       Video to MP4 Batch Converter
echo ============================================
echo.

:: Check if ffmpeg is available
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ffmpeg not found in PATH.
    echo Please install ffmpeg and add it to your system PATH.
    echo Download: https://ffmpeg.org/download.html
    pause
    exit /b 1
)

:: Initialize counters
set "COUNT=0"
set "SUCCESS=0"
set "SKIP=0"
set "FAIL=0"

:: Detect if files/folders were dropped
if not "%~1"=="" (
    echo [INFO] Drag-and-drop detected. Processing items...
    echo.
    for %%I in (%*) do (
        if exist "%%~I\" (
            call :ProcessDirectory "%%~I"
        ) else (
            call :ProcessFile "%%~I"
        )
    )
    goto :ShowSummary
)

:: --- Manual Input Fallback ---
echo =======================================================================
echo  HOW TO USE THIS CONVERTER:
echo  1. Drag-and-drop video files or folders directly into the window.
echo  or,
echo  2. Type/paste a folder path below to scan it recursively.
echo =======================================================================
echo.
set /p "FOLDER_PATH=Enter folder path to scan: "

if "!FOLDER_PATH!"=="" (
    echo.
    echo [ERROR] No path entered.
    echo Please check the path and try again.
    pause
    exit /b 1
)

:: Check if input contains quotes (drag-and-drop puts quotes around paths)
set "STRIPPED=!FOLDER_PATH:"=!"
if not "!STRIPPED!"=="!FOLDER_PATH!" goto :HandleQuotedInput

:: Plain unquoted path - treat as single item
if "!FOLDER_PATH:~-1!"=="\" set "FOLDER_PATH=!FOLDER_PATH:~0,-1!"

if exist "!FOLDER_PATH!\" (
    echo.
    echo [INFO] Scanning folder: !FOLDER_PATH!
    echo [INFO] Conversion speed: Medium
    echo.
    call :ProcessDirectory "!FOLDER_PATH!"
) else if exist "!FOLDER_PATH!" (
    echo.
    echo [INFO] Processing file: !FOLDER_PATH!
    echo.
    call :ProcessFile "!FOLDER_PATH!"
) else (
    echo.
    echo [ERROR] Folder or file not found: !FOLDER_PATH!
    echo Please check the path and try again.
    pause
    exit /b 1
)
goto :ShowSummary

:HandleQuotedInput
:: Use call+shift to safely parse quoted paths with special characters
:: This avoids CMD's for-in block issues with parentheses and brackets
call :ParseInput !FOLDER_PATH!
goto :ShowSummary

:ParseInput
if "%~1"=="" exit /b
set "CURRENT_ITEM=%~1"
if "!CURRENT_ITEM:~-1!"=="\" set "CURRENT_ITEM=!CURRENT_ITEM:~0,-1!"

if exist "!CURRENT_ITEM!\" (
    echo.
    echo [INFO] Scanning folder: !CURRENT_ITEM!
    echo [INFO] Conversion speed: Medium
    echo.
    call :ProcessDirectory "!CURRENT_ITEM!"
) else if exist "!CURRENT_ITEM!" (
    call :ProcessFile "!CURRENT_ITEM!"
) else (
    echo [WARN] Not found: !CURRENT_ITEM!
)
shift
goto :ParseInput


:: --- Subroutines ---

:ProcessDirectory
set "DIR_PATH=%~1"
set "OUTPUT_DIR=%DIR_PATH%\converted_mp4"
if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
)

for %%E in (avi mkv mov wmv flv webm mpeg mpg m4v 3gp ts mts m2ts vob rmvb rm ogv asf divx xvid f4v) do (
    for /r "%DIR_PATH%" %%F in (*.%%E) do (
        :: Skip files already inside any converted_mp4 folder
        echo "%%F" | findstr /i /c:"\converted_mp4\" >nul
        if errorlevel 1 (
            call :ConvertFile "%%F" "%OUTPUT_DIR%"
        )
    )
)
exit /b

:ProcessFile
set "FILE_PATH=%~1"
set "FILE_DIR=%~dp1"
set "FILE_EXT=%~x1"

:: Check if the extension is in our supported list
set "SUPPORTED=0"
for %%E in (.avi .mkv .mov .wmv .flv .webm .mpeg .mpg .m4v .3gp .ts .mts .m2ts .vob .rmvb .rm .ogv .asf .divx .xvid .f4v) do (
    if /i "%%E"=="!FILE_EXT!" set "SUPPORTED=1"
)

if "!SUPPORTED!"=="0" (
    echo [SKIP] Unsupported video format: %~nx1
    exit /b
)

:: Define output directory for this file
set "OUTPUT_DIR=%FILE_DIR%converted_mp4"
if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
)

:: Skip files already inside a converted_mp4 folder
echo "%FILE_PATH%" | findstr /i /c:"\converted_mp4\" >nul
if errorlevel 1 (
    call :ConvertFile "%FILE_PATH%" "%OUTPUT_DIR%"
) else (
    echo [SKIP] File is already in a converted_mp4 folder: %~nx1
)
exit /b

:ConvertFile
set "INPUT=%~1"
set "OUTPUT_DIR=%~2"
set "FILENAME=%~n1"
set "OUTPUT=%OUTPUT_DIR%\%FILENAME%.mp4"

set /a COUNT+=1

:: Skip if output already exists
if exist "%OUTPUT%" (
    echo [SKIP] Already converted: %~nx1
    set /a SKIP+=1
) else (
    echo [!COUNT!] Converting: %~nx1
    echo       To: %FILENAME%.mp4

    ffmpeg -i "%INPUT%" ^
        -c:v libx264 ^
        -preset medium ^
        -crf 23 ^
        -c:a aac ^
        -b:a 192k ^
        -movflags +faststart ^
        -y "%OUTPUT%" ^
        -loglevel warning

    if !errorlevel! equ 0 (
        set "SRC=%INPUT%"
        set "DST=%OUTPUT%"
        powershell -NoLogo -NoProfile -Command "$s=Get-Item $env:SRC; $d=Get-Item $env:DST; $d.CreationTime=$s.CreationTime; $d.LastWriteTime=$s.LastWriteTime; $d.LastAccessTime=$s.LastAccessTime"
        set "SRC="
        set "DST="

        echo       [OK] Done!
        set /a SUCCESS+=1
    ) else (
        echo       [FAIL] Conversion failed for: %~nx1
        set /a FAIL+=1
    )
    echo.
)
exit /b


:: --- Show Summary ---
:ShowSummary
echo ============================================
echo                  SUMMARY
echo ============================================
echo  Total videos processed: !COUNT!
echo  Successfully converted: !SUCCESS!
echo  Skipped (already exist): !SKIP!
echo  Failed                : !FAIL!
echo ============================================
echo.

if !COUNT! equ 0 (
    echo [INFO] No video files processed.
)

pause
endlocal