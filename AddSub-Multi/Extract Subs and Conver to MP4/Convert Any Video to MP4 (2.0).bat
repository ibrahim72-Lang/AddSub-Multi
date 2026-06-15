@echo off
setlocal enabledelayedexpansion
title Video to MP4 Converter

echo ============================================
echo       Video to MP4 Batch Converter
echo ============================================
echo.

REM === Ask user for source folder ===
echo Enter the folder containing your video file(s):
set /p source_folder="Path: "
set "source_folder=%source_folder:"=%"

if not exist "%source_folder%" (
    echo [ERROR] The folder does not exist.
    pause
    exit /b
)

REM === Temp folder next to the BAT file ===
set "script_dir=%~dp0"
set "temp_folder=%script_dir%Temp"
if not exist "%temp_folder%" mkdir "%temp_folder%"

echo.
echo Source Folder: "%source_folder%"
echo Temp Folder:   "%temp_folder%"
echo.

REM === Quality profile selection ===
set "CONVERT_CRF=18"
set "CONVERT_PRESET=medium"

echo Quality profiles:
echo 1) High quality (slower)   -preset slow
echo 2) Balanced (recommended)  -preset medium
echo 3) Fast conversion          -preset fast
echo.
set /p quality_choice="Choose 1-3 (default 2): "

if "!quality_choice!"=="1" set "CONVERT_PRESET=slow"
if "!quality_choice!"=="2" set "CONVERT_PRESET=medium"
if "!quality_choice!"=="3" set "CONVERT_PRESET=fast"

echo.
echo [INFO] Preset: !CONVERT_PRESET! / CRF: !CONVERT_CRF!
echo.

REM === Counters ===
set "COUNT=0"
set "SUCCESS=0"
set "SKIP=0"
set "FAIL=0"

REM === Process all supported video formats recursively ===
for /r "%source_folder%" %%F in (*.mkv *.avi *.mov *.wmv *.flv *.webm *.mpeg *.mpg *.m4v *.3gp *.ts *.mts *.m2ts *.vob *.ogv *.asf *.divx *.xvid) do (

    echo "%%~dpF" | findstr /i /c:"\Temp\" >nul
    if errorlevel 1 (

        set /a COUNT+=1
        set "FINAL_OUT=%%~dpF%%~nF.mp4"

        echo -----------------------------------------
        echo [!COUNT!] Processing: %%~nxF
        echo.

        if exist "!FINAL_OUT!" (
            echo [SKIP] MP4 already exists: %%~nF.mp4
            set /a SKIP+=1
        ) else (

            del /q "%temp_folder%\*" 2>nul

            REM Detect audio codec
            set "audioOptions=-c:a aac -b:a 192k"
            for /f "delims=" %%A in ('ffprobe -v error -select_streams a:0 -show_entries stream^=codec_name -of default^=noprint_wrappers^=1:nokey^=1 "%%~F"') do (
                if /i "%%A"=="aac" set "audioOptions=-c:a copy"
            )

            REM Get video duration for display
            for /f "delims=" %%D in ('ffprobe -v error -select_streams v:0 -show_entries stream^=duration -of default^=noprint_wrappers^=1:nokey^=1 "%%~F"') do (
                set "DURATION=%%D"
            )
            echo Duration: !DURATION! seconds
            echo.

            set "TEMP_OUT=%temp_folder%\%%~nF.mp4"

            REM -stats shows live progress, -loglevel error hides info but keeps errors visible
            ffmpeg -hide_banner -fflags +genpts -y -i "%%~F" -c:v libx264 -preset !CONVERT_PRESET! -crf !CONVERT_CRF! !audioOptions! -movflags +faststart "!TEMP_OUT!" -loglevel error -stats

            if !errorlevel! equ 0 (
                move /y "!TEMP_OUT!" "!FINAL_OUT!" >nul

                set "SRC=%%~F"
                set "DST=!FINAL_OUT!"
                powershell -NoLogo -NoProfile -Command "$s=Get-Item $env:SRC; $d=Get-Item $env:DST; $d.CreationTime=$s.CreationTime; $d.LastWriteTime=$s.LastWriteTime; $d.LastAccessTime=$s.LastAccessTime"

                echo.
                echo [OK] Done: %%~nF.mp4
                set /a SUCCESS+=1
            ) else (
                echo.
                echo [FAIL] Conversion failed: %%~nxF
                set /a FAIL+=1
            )
        )
        echo.
    )
)

echo ============================================
echo                  SUMMARY
echo ============================================
echo  Total found           : !COUNT!
echo  Successfully converted: !SUCCESS!
echo  Skipped (MP4 exists)  : !SKIP!
echo  Failed                : !FAIL!
echo ============================================
echo.
pause
endlocal