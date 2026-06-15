@echo off
setlocal enabledelayedexpansion

echo Enter the FULL path to your folder:
set /p inputPath="Path: "
set inputPath=%inputPath:"=%

if not exist "!inputPath!" (echo Folder not found. & pause & exit /b)

:: Create a local temp directory for processing
set "tempDir=!inputPath!\Temp"
if not exist "!tempDir!" mkdir "!tempDir!"

for %%V in ("!inputPath!\*.mp4" "!inputPath!\*.mkv" "!inputPath!\*.avi") do (
    set "origFile=%%~fV"
    set "tempFile=!tempDir!\%%~nxV"

    echo -----------------------------------------
    echo Processing: "%%~nxV"

    :: --- CHECK FOR EMBEDDED SUBS ---
    echo [Status] Checking for embedded subtitles...
    ffprobe -v error -select_streams s -show_entries stream=codec_name -of csv=p=0 "!origFile!" 2>nul | findstr /r "subrip mov_text ass ssa vtt" >nul
    
    if !errorlevel! EQU 0 (
        echo [Status] Embedded subtitles detected. Stripping...
        
        :: Strip embedded subs and save to temp
        ffmpeg -i "!origFile!" -map 0 -map -0:s -c copy -y "!tempFile!" -loglevel error
        
        :: Verify temp file exists before replacing
        if exist "!tempFile!" (
            :: Sync timestamps before replacing original
            powershell -Command "$o=Get-Item '!origFile!'; $n=Get-Item '!tempFile!'; $n.CreationTime=$o.CreationTime; $n.LastWriteTime=$o.LastWriteTime"
            
            del "!origFile!"
            move /y "!tempFile!" "!origFile!" >nul
            echo [Status] Embedded subtitles removed successfully.
        )
    ) else (
        echo [Status] No embedded subtitles found. Skipping.
    )
)

:: Cleanup temp directory
if exist "!tempDir!" rd /s /q "!tempDir!"

echo -----------------------------------------
echo All finished!
pause