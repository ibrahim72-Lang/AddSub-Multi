@echo off
setlocal enabledelayedexpansion

:: Create Temp folder next to the BAT file
set "scriptFolder=%~dp0"
set "tempFolder=%scriptFolder%Temp"
if not exist "%tempFolder%\" mkdir "%tempFolder%"
if not exist "%tempFolder%\" (
    echo Could not create Temp folder:
    echo "%tempFolder%"
    pause
    exit /b
)

echo Drag and drop a video file/folder, or type the full path:
set /p "inputPath=> "

set "inputPath=%inputPath:"=%"

if not exist "%inputPath%" (
    echo File not found.
    pause
    exit /b
)

if exist "%inputPath%\" (
    set /a processed=0
    set /a failed=0
    for %%V in ("%inputPath%\*.mkv" "%inputPath%\*.mp4" "%inputPath%\*.avi" "%inputPath%\*.mov" "%inputPath%\*.m4v" "%inputPath%\*.webm") do (
        if exist "%%~fV" (
            call :ProcessVideo "%%~fV"
            if errorlevel 1 (
                set /a failed+=1
            ) else (
                set /a processed+=1
            )
        )
    )
    if "!processed!"=="0" if "!failed!"=="0" (
        echo No supported video files found in:
        echo "%inputPath%"
    )
    echo.
    echo ============================================
    echo Batch processing complete.
    echo Videos processed successfully: !processed!
    echo Videos failed: !failed!
    echo ============================================
    pause
    exit /b
)

call :ProcessVideo "%inputPath%"
if errorlevel 1 (
    echo.
    echo ============================================
    echo Failed.
    echo ============================================
    pause
    exit /b
)
echo.
echo ============================================
echo Done.
echo ============================================
pause
exit /b

:ProcessVideo
set "inputFile=%~1"
set "formatName="
set "outputFormatArgs="

:: Extract input file path and name
for %%A in ("%inputFile%") do (
    set "inDir=%%~dpA"
    set "inName=%%~nA"
    set "inExt=%%~xA"
)

set "outExt=.mp4"
for /f "usebackq delims=" %%F in (`ffprobe -v error -show_entries format^=format_name -of default^=noprint_wrappers^=1:nokey^=1 "!inputFile!"`) do (
    set "formatName=%%F"
)
set "outputFormatArgs=-f mp4"

echo.
echo ============================================
echo Processing: !inputFile!
echo Output will be created in: !tempFolder!
echo ============================================
echo.

:: ---------------------------------------------------------
:: 1) Extract video without subtitles, no re-encode
:: ---------------------------------------------------------
ffmpeg -i "!inputFile!" -map 0 -map -0:s -c copy !outputFormatArgs! "!tempFolder!\!inName!!outExt!"
if errorlevel 1 (
    echo Failed to extract video. Skipping this file.
    exit /b 1
)

:: ---------------------------------------------------------
:: 2) Extract subtitle stream info (codec + language)
:: ---------------------------------------------------------
echo Detecting subtitle tracks...
ffprobe -v error -select_streams s -show_entries stream=index,codec_name:stream_tags=language -of csv=p=0 "!inputFile!" > "!tempFolder!\subs_info.txt"
if errorlevel 1 (
    echo Failed to read subtitle tracks. Skipping this file.
    exit /b 1
)
echo.
echo Subtitle tracks found:
type "!tempFolder!\subs_info.txt"
echo.
if not exist "!tempFolder!\subs_info.txt" (
    echo Could not create subtitle info file.
    exit /b 1
)

:: ---------------------------------------------------------
:: 3) Extract each subtitle track with correct extension + language
:: ---------------------------------------------------------
set /a count=0

for /f "usebackq tokens=1,2,3 delims=," %%a in ("!tempFolder!\subs_info.txt") do (
    set "idx=%%a"
    set "codec=%%b"
    set "lang=%%c"
    set "ext="

    if "!lang!"=="" set "lang=und"

    rem Determine extension based on codec
    if /i "!codec!"=="subrip"  set "ext=srt"
    if /i "!codec!"=="ass"     set "ext=ass"
    if /i "!codec!"=="hdmv_pgs_subtitle" set "ext=sup"
    if /i "!codec!"=="dvd_subtitle"      set "ext=sub"
    if /i "!codec!"=="mov_text"          set "ext=srt"
    if /i "!ext!"=="" set "ext=srt"
    set "subtitleCodec=copy"
    if /i "!codec!"=="mov_text" set "subtitleCodec=srt"

    set "outFile=!tempFolder!\!inName!.!lang!.!ext!"
    if exist "!outFile!" set "outFile=!tempFolder!\!inName!.!lang!.!count!.!ext!"

    echo Extracting subtitle track !idx!  [!lang!]  codec: !codec!

    ffmpeg -i "!inputFile!" -map 0:!idx! -c:s !subtitleCodec! "!outFile!" -y
    if errorlevel 1 (
        echo Failed to extract subtitle track !idx!.
    ) else (
        echo Created: !outFile!
    )

    set /a count+=1
)

if "!count!"=="0" (
    echo No subtitle tracks were detected by ffprobe.
    echo This MKV may not contain subtitles, or ffprobe may not be installed/found.
)

:: ---------------------------------------------------------
:: 4) Create dual subtitles, clean duplicates, move files to movie folder
:: ---------------------------------------------------------
echo.
if exist "!scriptFolder!combine_dual_subs.py" (
    echo Creating dual subtitles...
    python "!scriptFolder!combine_dual_subs.py" "!tempFolder!" "!inName!"
) else (
    echo combine_dual_subs.py not found. Dual subtitles skipped.
)

echo Removing numbered duplicate raw subtitles...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '!tempFolder!' -File | Where-Object { $_.Name -match ('^' + [regex]::Escape('!inName!') + '\.[a-z][a-z][a-z]?\.\d+\.(srt|ass|sup|sub)$') } | Remove-Item -Force"

set "movieFolder=!tempFolder!\!inName! (Video+Subs)"
set "finalFolder=!inDir!!inName! (Video+Subs)"

if exist "!movieFolder!\" rmdir /S /Q "!movieFolder!"
if exist "!finalFolder!\" rmdir /S /Q "!finalFolder!"
mkdir "!movieFolder!"

echo Moving video and subtitles to folder...
move /Y "!tempFolder!\!inName!!outExt!" "!movieFolder!\" >nul 2>&1
move /Y "!tempFolder!\!inName!.*.srt" "!movieFolder!\" >nul 2>&1
move /Y "!tempFolder!\!inName!.*.ass" "!movieFolder!\" >nul 2>&1
move /Y "!tempFolder!\!inName!.*.sup" "!movieFolder!\" >nul 2>&1
move /Y "!tempFolder!\!inName!.*.sub" "!movieFolder!\" >nul 2>&1

echo Moving folder to input folder...
move /Y "!movieFolder!" "!inDir!"

echo.
echo ============================================
echo Done.
echo Folder saved to: !finalFolder!
echo ============================================
exit /b 0
