@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   CHECK FOR MISSING SUBTITLES
echo ============================================
echo.

REM === Ask user for folder path ===
set /p "FOLDER=Enter folder path to scan: "

if not exist "%FOLDER%" (
    echo.
    echo Folder does not exist.
    pause
    exit /b
)

REM === Extract folder name for report file ===
for %%A in ("%FOLDER%") do set "FOLDERNAME=%%~nA"

REM === Report file path (saved next to the .bat file) ===
set "REPORT=No Subtitle Report - %FOLDERNAME%.txt"

REM === Clear old report if exists ===
if exist "%REPORT%" del "%REPORT%"

echo Generating report: "%REPORT%"
echo.

REM === Subtitle extensions to check ===
set "SUBS=.srt .vtt .ass .sub .ssa"

REM === Write header to report ===
echo Folder Path: %FOLDER%>>"%REPORT%"
echo.>>"%REPORT%"
echo ============================================>>"%REPORT%"
echo   List of Movies with No Subtitles>>"%REPORT%"
echo ============================================>>"%REPORT%"
echo.>>"%REPORT%"

echo ============================================
echo   MOVIES WITHOUT SUBTITLES
echo ============================================
echo.

REM === Loop through ALL files in folder ===
for %%F in ("%FOLDER%\*") do (
    if not "%%~xF"=="" (
        REM Skip subtitle files
        set "ext=%%~xF"
        set "is_sub=0"

        for %%S in (%SUBS%) do (
            if /I "%%S"=="!ext!" set "is_sub=1"
        )

        if !is_sub! equ 0 (
            REM This is a video file
            set "movie=%%~nF"
            set "found_sub=0"

            REM Check for ANY subtitle starting with movie name
            for %%X in (%SUBS%) do (
                for %%Z in ("%FOLDER%\!movie!*%%X") do (
                    if exist "%%~Z" (
                        set "found_sub=1"
                    )
                )
            )

            if !found_sub! equ 0 (
                echo Missing subtitles: %%~nxF
                echo %%~nxF>>"%REPORT%"
            )
        )
    )
)

echo.
echo ============================================
echo   REPORT COMPLETE
echo Saved to: "%REPORT%"
echo ============================================
echo.
pause
