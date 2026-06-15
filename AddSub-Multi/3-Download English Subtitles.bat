@echo off
setlocal enabledelayedexpansion

REM Enable ANSI escape support
for /f "delims=" %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"

echo Enter the FULL path to your folder containing the video files:
set /p inputPath="Path: "
set inputPath=%inputPath:"=%

if not exist "%inputPath%" (
    echo Folder not found.
    pause
    exit /b
)

set "subfolder=%inputPath%\Downloaded Subtitles"
if not exist "%subfolder%" mkdir "%subfolder%"

echo.
echo Processing folder: %inputPath%
echo Subtitles will be saved in: %subfolder%
echo.

for %%V in ("%inputPath%\*.mp4") do call :process "%%~V"
for %%V in ("%inputPath%\*.mkv") do call :process "%%~V"
for %%V in ("%inputPath%\*.avi") do call :process "%%~V"
for %%V in ("%inputPath%\*.mov") do call :process "%%~V"
for %%V in ("%inputPath%\*.wmv") do call :process "%%~V"

echo All subtitles processed.
pause
exit /b

:process
set "video=%~nx1"
set "name=%~n1"

echo -----------------------------------------

REM Movie name in GREEN
echo !ESC![92mVideo: !video!!ESC![0m

REM Check if any subtitle already exists (any format)
set "exists=0"
for %%E in (srt ass ssa vtt sub txt sbv xml ttml dfxp) do (
    if exist "%subfolder%\!name!.%%E" set "exists=1"
)

if "!exists!"=="1" (
    REM Skipping in MAGENTA
    echo !ESC![95mSubtitle already exists. Skipping.!ESC![0m
) else (
    REM Download line in YELLOW
    echo !ESC![93mDownloading subtitle for: !video!!ESC![0m

    python -m subliminal download -l en -d "%subfolder%" "%~1"

    REM Rename ANY subtitle format downloaded
    for %%S in (
        "%subfolder%\!name!*.srt"
        "%subfolder%\!name!*.ass"
        "%subfolder%\!name!*.ssa"
        "%subfolder%\!name!*.vtt"
        "%subfolder%\!name!*.sub"
        "%subfolder%\!name!*.txt"
        "%subfolder%\!name!*.sbv"
        "%subfolder%\!name!*.xml"
        "%subfolder%\!name!*.ttml"
        "%subfolder%\!name!*.dfxp"
    ) do (
        if exist "%%~fS" (
            echo Found downloaded subtitle: %%~nxS
            echo Renaming to: !name!%%~xS
            move /Y "%%~fS" "%subfolder%\!name!%%~xS" >nul
        )
    )

    REM Done in BLUE
    echo !ESC![94mDone.!ESC![0m
)

echo.
goto :eof