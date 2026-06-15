@echo off
setlocal enabledelayedexpansion
for /f "delims=" %%E in ('echo prompt $E^| cmd') do set "ESC=%%E"
set "C_STATUS=!ESC![97m"
set "C_SUCCESS=!ESC![92m"
set "C_WARN=!ESC![93m"
set "C_PROCESS=!ESC![96m"
set "C_OPTIONAL=!ESC![95m"
set "C_ERROR=!ESC![91m"
set "C_SKIP=!ESC![90m"
set "C_RESET=!ESC![0m"

:: ============================================================
:: 0. DEPENDENCY CHECK
:: ============================================================
set "DEP_ERROR="
where ffmpeg >nul 2>nul || (echo !C_ERROR![Error] ffmpeg not found in PATH. Please install ffmpeg and add it to your system PATH.!C_RESET! & set "DEP_ERROR=1")
where ffprobe >nul 2>nul || (echo !C_ERROR![Error] ffprobe not found in PATH. Please install ffmpeg ^(includes ffprobe^) and add it to your system PATH.!C_RESET! & set "DEP_ERROR=1")
where python >nul 2>nul || (echo !C_ERROR![Error] python not found in PATH. Please install Python and add it to your system PATH.!C_RESET! & set "DEP_ERROR=1")
where subliminal >nul 2>nul || (echo !C_ERROR![Error] subliminal not found in PATH. Please install it: pip install subliminal!C_RESET! & set "DEP_ERROR=1")
for %%F in (split_input_paths.py use_provided_english_sub.py validate_subs.py fix_srt_overlaps.py detect_downloaded_dual_subs.py combine_dual_subs.py validate_subs_ffmpeg.py) do (
    if not exist "%~dp0%%F" (echo !C_ERROR![Error] Missing required file: %%F!C_RESET! & set "DEP_ERROR=1")
)
if defined DEP_ERROR (
    echo.
    echo !C_ERROR![Stop] One or more dependencies are missing. Please fix the above errors and try again.!C_RESET!
    if not defined GUI_MODE pause
    exit /b 1
)

:: ============================================================
:: 1. CONFIGURATION & LANGUAGES
:: ============================================================
for /f %%A in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N').Substring(0,12)"') do set "RUN_ID=%%A"
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmssfff"') do set "QUEUE_TIME=%%A"
set "tempRoot=%~dp0Temp"
if not exist "!tempRoot!" mkdir "!tempRoot!"
call :CleanupStaleTempRuns
set "stateRoot=%LOCALAPPDATA%\AddSub-Multi"
if not exist "!stateRoot!" mkdir "!stateRoot!"
set "lockDir=!stateRoot!\AddSub-Multi.lock"
set "queueDir=!stateRoot!\AddSub-Multi.queue"
if not exist "!queueDir!" mkdir "!queueDir!"
set "queueTicket=!queueDir!\!QUEUE_TIME!_!RUN_ID!.ticket"
set "LOCK_ACQUIRED="
set "output=!tempRoot!\Run_!RUN_ID!"
if not exist "!output!" mkdir "!output!"
set "stateDir=!stateRoot!\Run_!RUN_ID!"
if not exist "!stateDir!" mkdir "!stateDir!"
set "stateFile=!stateRoot!\subtitle_download_state.txt"
set "dailyLimitLock=%~dp0daily_limit_reached.txt"
set /a DAILY_LIMIT=1000
set /a DEFECTIVE_LIMIT=10
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%A"
call :LoadState
if exist "!dailyLimitLock!" (
    set "LOCK_DATE="
    for /f "usebackq delims=" %%A in ("!dailyLimitLock!") do if not defined LOCK_DATE set "LOCK_DATE=%%A"
    if "!LOCK_DATE!"=="!TODAY!" (
        call :DailyLimitMessage
        if not defined GUI_MODE pause
        call :CleanupTemp
        call :ReleaseSingleInstance
        exit /b 1
    ) else (
        del /f /q "!dailyLimitLock!" >nul 2>nul
    )
)
if !DOWNLOADS_TODAY! GEQ !DAILY_LIMIT! (
    >"!dailyLimitLock!" echo(!TODAY!
    call :DailyLimitMessage
    if not defined GUI_MODE pause
    call :CleanupTemp
    call :ReleaseSingleInstance
    exit /b 1
)
set "inputList=!stateDir!\input_items.txt"
set "videoList=!stateDir!\video_list.txt"
set "explicitFileList=!stateDir!\explicit_files.txt"
set "guiFileList=!stateRoot!\gui_video_list.txt"
if defined FILE_LIST_READY (
    echo !C_STATUS![GUI] Using pre-populated file list from GUI...!C_RESET!
    copy /y "!guiFileList!" "!inputList!" >nul 2>nul
    copy /y "!guiFileList!" "!videoList!" >nul 2>nul
    set /a VIDEO_COUNT=0
    for /f "usebackq delims=" %%V in ("!videoList!") do set /a VIDEO_COUNT+=1
    :: Must mirror ORDERED_LANGS + lang names set below (line 172-174) since we jump past them
    set "ORDERED_LANGS=en fr de es ru zh ar it"
    set "en=English"&set "fr=French"&set "de=German"&set "es=Spanish"&set "ru=Russian"&set "zh=Chinese"&set "ar=Arabic"&set "it=Italian"
    goto SkipInputScan
)

:ReadInput
del /f /q "!inputList!" "!videoList!" "!explicitFileList!" >nul 2>nul

if "%~1"=="" (
    echo ______________________________________________________________________
    echo.
    echo Paste the FULL path to one video file or a folder.
    echo You can also paste or drag and drop up to 10 video files, or paste/drop up to 5 folders.
    echo Pasted or scanned videos will be processed newest Date Created first.
    set /p inputPath="Path: "
    set "INPUT_PATH_RAW=!inputPath!"
    python "%~dp0split_input_paths.py" "!INPUT_PATH_RAW!" >> "!inputList!"
) else (
    if defined FORCE_PROMPT (
        echo ______________________________________________________________________
        echo.
        echo Paste the FULL path to one video file or a folder.
        echo You can also paste or drag and drop up to 10 video files, or paste/drop up to 5 folders.
        echo Pasted or scanned videos will be processed newest Date Created first.
        set /p inputPath="Path: "
        set "INPUT_PATH_RAW=!inputPath!"
        python "%~dp0split_input_paths.py" "!INPUT_PATH_RAW!" >> "!inputList!"
    ) else (
        call :ReadDroppedArgs %*
    )
)
set "INCLUDE_SUBFOLDERS="
set "SUBFOLDER_VIDEOS_FOUND="
set /a FOLDER_INPUT_COUNT=0
for /f %%A in ('powershell -NoProfile -Command "@(Get-Content -LiteralPath $env:inputList -ErrorAction SilentlyContinue | Where-Object { $p=$_.Trim(); $p -and (Test-Path -LiteralPath $p -PathType Container) }).Count"') do set /a FOLDER_INPUT_COUNT=%%A
if !FOLDER_INPUT_COUNT! GTR 5 (
    echo !C_ERROR![Error] Maximum 5 folders can be selected per run.!C_RESET!
    echo !C_ERROR![Error] Please paste/drop up to 5 folders, or select a maximum of 10 video files.!C_RESET!
    call :InvalidInputStop
    call :CleanupTemp
    call :ReleaseSingleInstance
    exit /b 1
)
for /f %%A in ('powershell -NoProfile -Command "$videoExts=@('.mp4','.mkv','.avi','.m4v','.mov','.wmv','.flv','.webm','.mpg','.mpeg','.ts','.m2ts'); foreach($line in Get-Content -LiteralPath $env:inputList -ErrorAction SilentlyContinue){ $path=$line.Trim(); if(-not $path){ continue }; if(Test-Path -LiteralPath $path -PathType Container){ $hit=Get-ChildItem -LiteralPath $path -Directory -ErrorAction SilentlyContinue | Where-Object { @(Get-ChildItem -LiteralPath $_.FullName -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $videoExts -contains $_.Extension.ToLowerInvariant() } | Select-Object -First 1).Count -gt 0 } | Select-Object -First 1; if($hit){ '1'; exit } } }"') do set "SUBFOLDER_VIDEOS_FOUND=1"
if defined SUBFOLDER_VIDEOS_FOUND (
    :: Only prompt if SUBFOLDER_CHOICE not already set (e.g., from GUI)
    if not defined SUBFOLDER_CHOICE (
        set "SUBFOLDER_CHOICE="
        set /p SUBFOLDER_CHOICE="!C_WARN!Subfolders containing video files were detected. Process videos in subfolders? [Y/N]: !C_RESET!"
    )
    if /i "!SUBFOLDER_CHOICE!"=="Y" set "INCLUDE_SUBFOLDERS=1"
)
powershell -NoProfile -Command "$videoExts=@('.mp4','.mkv','.avi','.m4v','.mov','.wmv','.flv','.webm','.mpg','.mpeg','.ts','.m2ts'); $files=@(); foreach($line in Get-Content -LiteralPath $env:inputList){ $path=$line.Trim(); if(-not $path){ continue }; if(Test-Path -LiteralPath $path -PathType Leaf){ $item=Get-Item -LiteralPath $path; if($videoExts -contains $item.Extension.ToLowerInvariant()){ $files += $item } } }; $files=@($files | Sort-Object @{Expression='CreationTimeUtc';Descending=$true}, @{Expression='LastWriteTimeUtc';Descending=$true}, FullName -Unique); foreach($file in $files){ $file.FullName }" > "!explicitFileList!"
for /f %%A in ('powershell -NoProfile -Command "@(Get-Content -LiteralPath $env:explicitFileList -ErrorAction SilentlyContinue | Where-Object { $_.Trim() }).Count"') do set /a EXPLICIT_VIDEO_COUNT=%%A
if !EXPLICIT_VIDEO_COUNT! GTR 10 (
    echo !C_ERROR![Error] Multi-file selection is limited to 10 video files.!C_RESET!
    echo !C_ERROR![Error] Please select a maximum of 10 video files, or paste/drop up to 5 folders instead.!C_RESET!
    call :InvalidInputStop
    call :CleanupTemp
    call :ReleaseSingleInstance
    exit /b 1
)

powershell -NoProfile -Command "$videoExts=@('.mp4','.mkv','.avi','.m4v','.mov','.wmv','.flv','.webm','.mpg','.mpeg','.ts','.m2ts'); $subtitleExts=@('.srt','.ass','.ssa','.vtt','.sub','.idx','.smi','.sami','.sbv','.dfxp','.ttml','.stl','.sup','.usf','.txt'); $videos=@(); $recursive=($env:INCLUDE_SUBFOLDERS -eq '1'); foreach($line in Get-Content -LiteralPath $env:inputList){ $path=$line.Trim(); if(-not $path){ continue }; if(Test-Path -LiteralPath $path -PathType Container){ if($recursive){ $items=Get-ChildItem -LiteralPath $path -File -Recurse -ErrorAction SilentlyContinue } else { $items=Get-ChildItem -LiteralPath $path -File -ErrorAction SilentlyContinue }; foreach($item in $items){ if($videoExts -contains $item.Extension.ToLowerInvariant()){ $videos += $item } } } elseif(Test-Path -LiteralPath $path -PathType Leaf){ $item=Get-Item -LiteralPath $path; $ext=$item.Extension.ToLowerInvariant(); if($videoExts -contains $ext){ continue } elseif($subtitleExts -contains $ext){ Write-Host ($item.Name + ' - Subtitle File Will be Checked for use') } else { Write-Host ($item.Name + ' - File skipped - Not a Video File') } } else { Write-Host ('[Warning] Path not found: ' + $path) } }; foreach($line in Get-Content -LiteralPath $env:explicitFileList -ErrorAction SilentlyContinue){ $path=$line.Trim(); if($path -and (Test-Path -LiteralPath $path -PathType Leaf)){ $videos += Get-Item -LiteralPath $path } }; $videos=@($videos | Sort-Object @{Expression='CreationTimeUtc';Descending=$true}, @{Expression='LastWriteTimeUtc';Descending=$true}, FullName -Unique); foreach($video in $videos){ $video.FullName }" > "!videoList!"

for %%A in ("!videoList!") do if %%~zA==0 (
    echo !C_ERROR![Error] No supported video files found. Supported: .mp4 .mkv .avi .m4v .mov .wmv .flv .webm .mpg .mpeg .ts .m2ts!C_RESET!
    call :WaitForNewInput
    set "FORCE_PROMPT=1"
    goto ReadInput
)
set /a VIDEO_COUNT=0
for /f "usebackq delims=" %%V in ("!videoList!") do set /a VIDEO_COUNT+=1
set "SINGLE_EXPLICIT_VIDEO="
if !VIDEO_COUNT! EQU 1 (
    for /f %%A in ('powershell -NoProfile -Command "$videos=@(Get-Content -LiteralPath $env:videoList -ErrorAction SilentlyContinue | Where-Object { $_.Trim() }); $explicit=@(Get-Content -LiteralPath $env:explicitFileList -ErrorAction SilentlyContinue | Where-Object { $_.Trim() }); if($videos.Count -eq 1 -and $explicit.Count -eq 1){ $v=(Get-Item -LiteralPath $videos[0]).FullName; $e=(Get-Item -LiteralPath $explicit[0]).FullName; if($v -ieq $e){ '1' } }"') do set "SINGLE_EXPLICIT_VIDEO=1"
)
:: Preserve REPROCESS_POLICY if already set (e.g., from GUI)
if not defined REPROCESS_POLICY set "REPROCESS_POLICY="
if not defined SINGLE_EXPLICIT_VIDEO (
    for /f %%A in ('powershell -NoProfile -Command "$found=0; foreach($path in Get-Content -LiteralPath $env:videoList -ErrorAction SilentlyContinue){ $path=$path.Trim(); if(-not $path){ continue }; $json=& ffprobe -v error -select_streams s -show_entries format_tags:stream_tags=title -of json $path 2>$null; if($json){ $data=$json | ConvertFrom-Json; $tags=$data.format.tags; if($tags){ foreach($prop in $tags.PSObject.Properties){ if($prop.Name -ieq 'subtitle_batch_processed' -and [string]$prop.Value -eq '1'){ $found=1; break } } }; if(-not $found -and @($data.streams).Count -ge 4){ $found=1 }; if($found){ '1'; exit } } }"') do set "PROCESSED_FOUND_IN_SESSION=1"
    if defined PROCESSED_FOUND_IN_SESSION call :PromptSessionReprocessPolicy
)
set /a SKIPPED_PROCESSED_COUNT=0
call :AcquireSingleInstance

:: Professional Order: Default (English) -> Major Global -> Regional -> Secondary
set "ORDERED_LANGS=en fr de es ru zh ar it"
set "en=English"&set "fr=French"&set "de=German"&set "es=Spanish"&set "ru=Russian"&set "zh=Chinese"&set "ar=Arabic"&set "it=Italian"

:SkipInputScan
set "SINGLE_EXPLICIT_VIDEO="
if !VIDEO_COUNT! EQU 1 (
    for /f %%A in ('powershell -NoProfile -Command "$videos=@(Get-Content -LiteralPath $env:videoList -ErrorAction SilentlyContinue | Where-Object { $_.Trim() }); $explicit=@(Get-Content -LiteralPath $env:explicitFileList -ErrorAction SilentlyContinue | Where-Object { $_.Trim() }); if($videos.Count -eq 1 -and $explicit.Count -eq 1){ $v=(Get-Item -LiteralPath $videos[0]).FullName; $e=(Get-Item -LiteralPath $explicit[0]).FullName; if($v -ieq $e){ '1' } }"') do set "SINGLE_EXPLICIT_VIDEO=1"
)
:: Preserve REPROCESS_POLICY if already set (e.g., from GUI)
if not defined REPROCESS_POLICY set "REPROCESS_POLICY="
if not defined SINGLE_EXPLICIT_VIDEO (
    for /f %%A in ('powershell -NoProfile -Command "$found=0; foreach($path in Get-Content -LiteralPath $env:videoList -ErrorAction SilentlyContinue){ $path=$path.Trim(); if(-not $path){ continue }; $json=& ffprobe -v error -select_streams s -show_entries format_tags:stream_tags=title -of json $path 2>$null; if($json){ $data=$json | ConvertFrom-Json; $tags=$data.format.tags; if($tags){ foreach($prop in $tags.PSObject.Properties){ if($prop.Name -ieq 'subtitle_batch_processed' -and [string]$prop.Value -eq '1'){ $found=1; break } } }; if(-not $found -and @($data.streams).Count -ge 4){ $found=1 }; if($found){ '1'; exit } } }"') do set "PROCESSED_FOUND_IN_SESSION=1"
    if defined PROCESSED_FOUND_IN_SESSION call :PromptSessionReprocessPolicy
)
set /a SKIPPED_PROCESSED_COUNT=0
call :AcquireSingleInstance

:: ============================================================
:: 2. PROCESSING ENGINE
:: ============================================================
for /f "usebackq delims=" %%V in ("!videoList!") do (
    set "origFile=%%~fV"
    set "name=%%~nV"
    set "videoFolder=%%~dpV"
    set "targetFile=%%~dpnV.mkv"
    
    set "VIDEO_MODIFIED="
    set "DOWNLOAD_ATTEMPTED="
    set /a VALID_AFTER_DOWNLOAD=0

    set "ALREADY_PROCESSED="
    for /f %%A in ('powershell -NoProfile -Command "$json=& ffprobe -v error -select_streams s -show_entries format_tags:stream_tags=title -of json $env:origFile 2>$null; if($json){ $data=$json | ConvertFrom-Json; $tags=$data.format.tags; if($tags){ foreach($prop in $tags.PSObject.Properties){ if($prop.Name -ieq 'subtitle_batch_processed' -and [string]$prop.Value -eq '1'){ '1'; exit } } }; $count=@($data.streams).Count; if($count -ge 4){ '1' } }"') do set "ALREADY_PROCESSED=1"
    if defined ALREADY_PROCESSED (
        if /i "!REPROCESS_POLICY!"=="SKIP_ALL" (
            set /a SKIPPED_PROCESSED_COUNT+=1
        ) else (
            echo.
            echo !ESC![96m============================================================!ESC![0m
            echo !ESC![93mProcessing Video: !ESC![92m%%~nxV!ESC![0m
            echo !ESC![96m============================================================!ESC![0m
        )
    ) else (
        echo.
        echo !ESC![96m============================================================!ESC![0m
        echo !ESC![93mProcessing Video: !ESC![92m%%~nxV!ESC![0m
        echo !ESC![96m============================================================!ESC![0m
    )
    set "EXPLICIT_FILE_SELECTED="
    for /f %%A in ('powershell -NoProfile -Command "$orig=(Get-Item -LiteralPath $env:origFile).FullName; foreach($line in Get-Content -LiteralPath $env:inputList -ErrorAction SilentlyContinue){ $p=$line.Trim(); if(-not $p){ continue }; if(Test-Path -LiteralPath $p -PathType Leaf){ $item=Get-Item -LiteralPath $p; if($item.FullName -ieq $orig){ '1'; exit } } }"') do set "EXPLICIT_FILE_SELECTED=1"
    if defined ALREADY_PROCESSED (
        if defined SINGLE_EXPLICIT_VIDEO (
            call :PromptReprocess
        ) else (
            call :ApplySessionReprocessPolicy
        )
    )
    if defined ALREADY_PROCESSED (
        if /i not "!REPROCESS_POLICY!"=="SKIP_ALL" (
            echo !C_SKIP![Skip] Already processed. Dual subtitle tracks found.!C_RESET!
            echo !C_SKIP![Skip] External subtitle cleanup skipped because no validation/mux gate ran.!C_RESET!
        )
    ) else (

    del /f /q "!output!\*.*" >nul 2>nul

    rem Capture original timestamps before modification
    for /f %%A in ('powershell -NoProfile -Command "(Get-Item -LiteralPath $env:origFile).LastWriteTimeUtc.ToFileTimeUtc()"') do set "tsWrite=%%A"
    for /f %%A in ('powershell -NoProfile -Command "(Get-Item -LiteralPath $env:origFile).CreationTimeUtc.ToFileTimeUtc()"') do set "tsCreate=%%A"
    set "subtitleSearchFile=!origFile!"
    set "subtitleSearchName=!name!"
    set "subtitleSearchTemp="
    set "metadataTitleFile=!output!\metadata_title.txt"
    powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; $raw=& ffprobe -v error -show_entries format_tags=title -of default=noprint_wrappers=1:nokey=1 $env:origFile 2>$null | Select-Object -First 1; if($null -ne $raw){ $title=([string]$raw).Trim(); if($title){ if($title -match '\|'){ $parts=$title -split '\|'; $title=([string]$parts[-1]).Trim() }; $title=$title -replace '[\\/:*?""<>|]',' '; $title=$title -replace '\s+',' '; $title=$title.Trim().TrimEnd('.'); $markers='(?i)\b(19|20)\d{2}\b|BluRay|BRRip|BDRip|WEB[- .]?DL|WEBRip|HDRip|DVDRip|HDTV|x264|x265|H\.?264|H\.?265|HEVC|AVC|10bit|8bit|2160p|1080p|720p|480p|AAC|AC3|DTS|DDP?|5\.1|7\.1|6CH|-[A-Za-z0-9]+$'; if($title -and $title -ne $env:name -and $title -match $markers){ $title } } }" > "!metadataTitleFile!" 2>nul
    for /f "usebackq delims=" %%T in ("!metadataTitleFile!") do if not defined RELEASE_SEARCH_NAME set "RELEASE_SEARCH_NAME=%%T"
    if defined RELEASE_SEARCH_NAME (
        set "subtitleSearchName=!RELEASE_SEARCH_NAME!"
        set "subtitleSearchTemp=!output!\!subtitleSearchName!%%~xV"
        powershell -NoProfile -Command "try { New-Item -ItemType HardLink -Path $env:subtitleSearchTemp -Target $env:origFile -Force | Out-Null } catch { Copy-Item -LiteralPath $env:origFile -Destination $env:subtitleSearchTemp -Force }"
        if exist "!subtitleSearchTemp!" (
            set "subtitleSearchFile=!subtitleSearchTemp!"
            echo !C_STATUS![Status] Using metadata release title for subtitle search: !subtitleSearchName!!C_RESET!
        ) else (
            set "subtitleSearchFile=!origFile!"
            set "subtitleSearchName=!name!"
            set "subtitleSearchTemp="
        )
    )
    set "RELEASE_SEARCH_NAME="

    rem Check for complete provided subtitles before downloading
    set "PROVIDED_ENGLISH="
    python "%~dp0use_provided_english_sub.py" "!videoFolder!." "!output!" "!name!" "!inputList!"
    python "%~dp0validate_subs.py" "!output!" "!origFile!"
    python "%~dp0validate_subs_ffmpeg.py" "!output!"
    for /f %%A in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath $env:output -Filter ($env:name + '*.srt') -File -ErrorAction SilentlyContinue).Count"') do set /a PROVIDED_SRT_COUNT=%%A
    set "embeddedLangsFile=!output!\embedded_langs.txt"
    powershell -NoProfile -Command "$map=@{eng='en';en='en';fre='fr';fra='fr';fr='fr';ger='de';deu='de';de='de';spa='es';es='es';rus='ru';ru='ru';chi='zh';zho='zh';zh='zh';ara='ar';ar='ar';ita='it';it='it'}; $safe=@('subrip','ass','ssa','webvtt','mov_text'); $langs=@(); $fallbackDir=Join-Path $env:output 'fallback_dual'; $json=& ffprobe -v error -select_streams s -show_entries stream=index,codec_name:stream_tags=language,title -of json $env:origFile 2>$null; if($json){ $data=$json | ConvertFrom-Json; foreach($s in @($data.streams)){ $codec=[string]$s.codec_name; $raw=[string]$s.tags.language; $title=[string]$s.tags.title; if($safe -notcontains $codec -or -not $raw){ continue }; $key=$raw.ToLowerInvariant(); if(-not $map.ContainsKey($key)){ continue }; $lang=$map[$key]; if($title -match '(?i)(english|dual)' -and $title -match '-'){ if(-not (Test-Path -LiteralPath $fallbackDir)){ New-Item -ItemType Directory -Path $fallbackDir | Out-Null }; $fallback=Join-Path $fallbackDir ($env:name + '.' + $lang + '-en.srt'); & ffmpeg -hide_banner -y -i $env:origFile -map ('0:' + $s.index) -c:s srt $fallback 2>$null; Write-Host ('[Embedded] Existing dual subtitle track saved as fallback and skipped: ' + $title); continue }; $target=Join-Path $env:output ($env:name + '.' + $lang + '.srt'); if(Test-Path -LiteralPath $target){ Write-Host ('[Embedded] Valid external/provided ' + $lang + ' subtitle already exists. Embedded track skipped.'); continue }; Write-Host ('[Embedded] Extracting embedded ' + $lang + ' subtitle for validation.'); & ffmpeg -hide_banner -y -i $env:origFile -map ('0:' + $s.index) -c:s srt $target 2>$null; if(Test-Path -LiteralPath $target){ $langs += $lang } } }; $langs | Sort-Object -Unique | Set-Content -LiteralPath $env:embeddedLangsFile -Encoding ASCII"
    python "%~dp0validate_subs.py" "!output!" "!origFile!"
    python "%~dp0validate_subs_ffmpeg.py" "!output!"
    powershell -NoProfile -Command "$langs=@(); foreach($lang in @('en','fr','de','es','ru','zh','ar','it')){ if(Test-Path -LiteralPath (Join-Path $env:output ($env:name + '.' + $lang + '.srt'))){ $langs += $lang } }; $langs | Sort-Object -Unique | Set-Content -LiteralPath $env:embeddedLangsFile -Encoding ASCII"

    rem Download all target subtitles in one pass
    if exist "!output!\!name!.en.srt" (
        set "PROVIDED_ENGLISH=1"
        echo !C_STATUS![Status] Valid English subtitle already available. Skipping English download.!C_RESET!
    )
    set "DOWNLOAD_LANGS="
    for %%L in (%ORDERED_LANGS%) do (
        if exist "!output!\!name!.%%L.srt" (
            if not "%%L"=="en" echo !C_STATUS![Status] Provided !%%L! subtitle found. Skipping !%%L! download.!C_RESET!
        ) else (
            findstr /x /i "%%L" "!embeddedLangsFile!" >nul 2>nul
            if not errorlevel 1 (
                echo !C_STATUS![Status] Embedded !%%L! subtitle found. Skipping !%%L! download.!C_RESET!
            ) else (
                set "DOWNLOAD_LANGS=!DOWNLOAD_LANGS! -l %%L"
            )
        )
    )
    if defined DOWNLOAD_LANGS (
        set "DOWNLOAD_ATTEMPTED=1"
        call :BeforeDownload
        subliminal download -d "!output!" -f --force -F srt -w 8 -W -pp opensubtitles -R omdb -R tmdb !DOWNLOAD_LANGS! --no-hearing-impaired "!subtitleSearchFile!" 2>>"!output!\subliminal_error.log"
        if not "!subtitleSearchName!"=="!name!" (
            powershell -NoProfile -Command "$old=$env:subtitleSearchName; $new=$env:name; Get-ChildItem -LiteralPath $env:output -Filter ($old + '*.srt') -File -ErrorAction SilentlyContinue | ForEach-Object { $target=Join-Path $_.DirectoryName ($_.Name -replace [regex]::Escape($old), $new); Move-Item -LiteralPath $_.FullName -Destination $target -Force }"
        )
        call :AfterDownload
        if defined STOP_SCRIPT (
            if not defined GUI_MODE pause
            call :CleanupTemp
            call :ReleaseSingleInstance
            exit /b 1
        )
    ) else (
        echo !C_STATUS![Status] All target subtitles were provided locally. Skipping subtitle download.!C_RESET!
    )
    python "%~dp0validate_subs.py" "!output!" "!origFile!"
    call :CountValidDownloaded
    set "HAS_VALID_AFTER_FIRST="
    for %%S in ("!output!\!name!*.srt") do (
        if exist "%%~fS" set "HAS_VALID_AFTER_FIRST=1"
    )
    if defined DOWNLOAD_LANGS if not defined HAS_VALID_AFTER_FIRST if not "!subtitleSearchFile!"=="!origFile!" (
        echo !C_STATUS![Status] Metadata-title subtitle search found no valid subtitles. Retrying with original filename...!C_RESET!
        set "DOWNLOAD_ATTEMPTED=1"
        call :BeforeDownload
        subliminal download -d "!output!" -f --force -F srt -w 8 -W -pp opensubtitles -R omdb -R tmdb !DOWNLOAD_LANGS! --no-hearing-impaired "!origFile!" 2>>"!output!\subliminal_error.log"
        call :AfterDownload
        if defined STOP_SCRIPT (
            if not defined GUI_MODE pause
            call :CleanupTemp
            call :ReleaseSingleInstance
            exit /b 1
        )
        python "%~dp0validate_subs.py" "!output!" "!origFile!"
        call :CountValidDownloaded
    )

    if not exist "!output!\!name!*.en.srt" (
        findstr /x /i "en" "!embeddedLangsFile!" >nul 2>nul
        if errorlevel 1 (
            echo !C_STATUS![Status] English subtitle missing after first pass. Retrying English with OpenSubtitles...!C_RESET!
            set "DOWNLOAD_ATTEMPTED=1"
            call :BeforeDownload
            subliminal download -d "!output!" -f --force -F srt -w 8 -W -p opensubtitles -R omdb -R tmdb -l en --no-hearing-impaired "!origFile!" 2>>"!output!\subliminal_error.log"
            if not "!subtitleSearchName!"=="!name!" (
                powershell -NoProfile -Command "$old=$env:subtitleSearchName; $new=$env:name; Get-ChildItem -LiteralPath $env:output -Filter ($old + '*.srt') -File -ErrorAction SilentlyContinue | ForEach-Object { $target=Join-Path $_.DirectoryName ($_.Name -replace [regex]::Escape($old), $new); Move-Item -LiteralPath $_.FullName -Destination $target -Force }"
            )
            call :AfterDownload
            if defined STOP_SCRIPT (
                if not defined GUI_MODE pause
                call :CleanupTemp
                call :ReleaseSingleInstance
                exit /b 1
            )
            python "%~dp0validate_subs.py" "!output!" "!origFile!"
            call :CountValidDownloaded
        ) else (
            echo !C_STATUS![Status] Embedded English subtitle available. Skipping English retry download.!C_RESET!
        )
    )

    set "HAS_ANY_SUB="
    for %%S in ("!output!\!name!*.srt") do (
        if exist "%%~fS" set "HAS_ANY_SUB=1"
    )
    for /f %%A in ('powershell -NoProfile -Command "if(Test-Path -LiteralPath $env:embeddedLangsFile){ @(Get-Content -LiteralPath $env:embeddedLangsFile | Where-Object { $_.Trim() }).Count } else { 0 }"') do if %%A GTR 0 set "HAS_ANY_SUB=1"
    if not defined HAS_ANY_SUB (
        set "cleanName=!name!"
        set "cleanName=!cleanName:.9.11.=.9-11.!"
        set "cleanName=!cleanName:.= !"
        if /i not "!cleanName!"=="!name!" (
            echo !C_STATUS![Status] No subtitles found. Retrying with parser-friendly temporary filename: !cleanName!%%~xV!C_RESET!
            copy /y "!origFile!" "!output!\!cleanName!%%~xV" >nul
            set "DOWNLOAD_ATTEMPTED=1"
            call :BeforeDownload
            subliminal download -d "!output!" -f --force -F srt -w 8 -W -pp opensubtitles -R omdb -R tmdb -l en -l fr -l de -l es -l ru -l zh -l ar -l it --no-hearing-impaired "!output!\!cleanName!%%~xV" 2>>"!output!\subliminal_error.log"
            call :AfterDownload
            if defined STOP_SCRIPT (
                if not defined GUI_MODE pause
                call :CleanupTemp
                call :ReleaseSingleInstance
                exit /b 1
            )
            del /f /q "!output!\!cleanName!%%~xV" >nul 2>nul
            for %%S in ("!output!\!cleanName!*.srt") do (
                if exist "%%~fS" (
                    powershell -NoProfile -Command "$path = Get-Item -LiteralPath '%%~fS'; $newName = $path.Name.Replace($env:cleanName, $env:name); Rename-Item -LiteralPath $path.FullName -NewName $newName -Force"
                )
            )
            python "%~dp0validate_subs.py" "!output!" "!origFile!"
            call :CountValidDownloaded
        )
    )

    if exist "!output!\!name!*.en.srt" (
        echo !C_STATUS![Status] English subtitle kept unchanged. Skipping English sync.!C_RESET!
    )
    python "%~dp0fix_srt_overlaps.py" "!output!"
    python "%~dp0validate_subs.py" "!output!" "!origFile!"
    python "%~dp0validate_subs_ffmpeg.py" "!output!"

    rem Detect downloaded subtitles that already contain dual-language text
    python "%~dp0detect_downloaded_dual_subs.py" "!output!" "!name!"
    python "%~dp0detect_downloaded_dual_subs.py" "!output!" "!name!" --extract-standalone-from-existing-duals

    rem Create optional dual-language subtitles using English as the second line
    python "%~dp0combine_dual_subs.py" "!output!" "!name!"
    python "%~dp0fix_srt_overlaps.py" "!output!"
    python "%~dp0detect_downloaded_dual_subs.py" "!output!" "!name!" --clean-script-standalone-only
    powershell -NoProfile -Command "$fallbackDir=Join-Path $env:output 'fallback_dual'; if(Test-Path -LiteralPath $fallbackDir){ foreach($lang in @('fr','de','es','ru','zh','ar','it')){ $fallback=Join-Path $fallbackDir ($env:name + '.' + $lang + '-en.srt'); $target=Join-Path $env:output ($env:name + '.' + $lang + '-en.srt'); if((Test-Path -LiteralPath $fallback) -and -not (Test-Path -LiteralPath $target)){ Copy-Item -LiteralPath $fallback -Destination $target -Force; Write-Host ('[Embedded] Restored fallback ' + $lang + '-English dual subtitle because no replacement was created.') } } }"
    python "%~dp0detect_downloaded_dual_subs.py" "!output!" "!name!" --extract-standalone-from-existing-duals
    python "%~dp0validate_subs.py" "!output!" "!origFile!"
    python "%~dp0validate_subs_ffmpeg.py" "!output!"

    set "HAS_DUAL="
    for %%L in (fr de es ru zh ar it) do (
        if exist "!output!\!name!*.%%L-en.srt" set "HAS_DUAL=1"
    )
    if not defined HAS_DUAL (
        echo !C_WARN![Warning] No dual subtitles were created. Continuing with single subtitles only.!C_RESET!
    )

    rem Final FFmpeg readability check before muxing
    python "%~dp0validate_subs_ffmpeg.py" "!output!"

    rem Build muxing map in fixed language order
    set "SUBS=" & set "MAPS=" & set "DISPS=" & set "HAS_EN=" & set /a SUBIDX=0 & set /a INPUTIDX=1
    for %%L in (%ORDERED_LANGS%) do (
        for %%S in ("!output!\!name!*.%%L.srt") do (
            if exist "%%~fS" (
                set SUBS=!SUBS! -i "%%~fS"
                set "MAPS=!MAPS! -map !INPUTIDX!:s:0 -metadata:s:s:!SUBIDX! language=%%L"
                if "%%L"=="en" (
                    set "DISPS=!DISPS! -disposition:s:!SUBIDX! default"
                    set "HAS_EN=1"
                ) else (
                    set "DISPS=!DISPS! -disposition:s:!SUBIDX! 0"
                )
                set /a INPUTIDX+=1 & set /a SUBIDX+=1
            )
        )
    )

    for %%L in (%ORDERED_LANGS%) do (
        if not "%%L"=="en" (
            for %%S in ("!output!\!name!*.%%L-en.srt") do (
                if exist "%%~fS" (
                    set SUBS=!SUBS! -i "%%~fS"
                    set "MAPS=!MAPS! -map !INPUTIDX!:s:0 -metadata:s:s:!SUBIDX! language=%%L -metadata:s:s:!SUBIDX! title=!%%L!-English"
                    set "DISPS=!DISPS! -disposition:s:!SUBIDX! 0"
                    set /a INPUTIDX+=1 & set /a SUBIDX+=1
                )
            )
        )
    )

    set "HAS_MUX_SUBS="
    if defined SUBS set "HAS_MUX_SUBS=1"

    if not defined HAS_EN (
        echo !C_WARN![Warning] English subtitle was not downloaded. No subtitle will be forced as default.!C_RESET!
    )

    rem Pre-mux conversion: probe the actual video codec and convert if it is a
    rem known-problematic legacy codec (DivX/Xvid/WMV/VC-1/etc.) regardless of container.
    set "muxInput=!origFile!"
    set "CONVERTED_INPUT="
    set "videoCodec="
    for /f "delims=" %%C in ('powershell -NoProfile -Command "& ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 $env:origFile 2>$null"') do set "videoCodec=%%C"
    set "NEEDS_CONVERT="
    for %%K in (mpeg4 msmpeg4v2 msmpeg4v3 divx h263 wmv1 wmv2 wmv3 vc1 theora) do (
        if /i "!videoCodec!"=="%%K" set "NEEDS_CONVERT=1"
    )
    if defined NEEDS_CONVERT (
        echo !C_STATUS![Status] Legacy codec detected ^(!videoCodec!^). Converting to H.264/MP4 before muxing...!C_RESET!
        echo !C_STATUS![Status] This may take several minutes depending on file size. Please wait.!C_RESET!
        set "convertedMp4=!output!\converted_source.mp4"
        set "convertLog=!output!\convert_error.log"

        rem Get total duration in seconds for progress calculation
        set "totalDuration=0"
        for /f "delims=" %%D in ('powershell -NoProfile -Command "& ffprobe -v error -select_streams v:0 -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $env:origFile 2>$null"') do set "totalDuration=%%D"

        rem Run ffmpeg and pipe stderr through PowerShell to report milestone percentages.
        rem Milestones 15/25/50/70/90/95/100 are printed exactly once each as crossed.
        ffmpeg -hide_banner -y -i "!origFile!" -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 192k "!convertedMp4!" 2>&1 | powershell -NoProfile -Command "$totalSec=[double]$env:totalDuration; $milestones=@(15,25,50,70,90,95,100); $nextIdx=0; $log=@(); foreach($line in $input){ $log+=$line; if($totalSec -gt 0 -and $line -match 'time=(\d+):(\d+):([\d.]+)'){ $e=[int]$Matches[1]*3600+[int]$Matches[2]*60+[double]$Matches[3]; $p=[math]::Min(99,[int]($e/$totalSec*100)); while($nextIdx -lt $milestones.Count -and $p -ge $milestones[$nextIdx]){ Write-Host ('[Progress] '+$milestones[$nextIdx]+'%% Complete'); $nextIdx++ } } }; Write-Host '[Progress] 100%% Complete'; $log | Set-Content -LiteralPath $env:convertLog -Encoding UTF8"

        if not exist "!convertedMp4!" (
            if exist "!convertLog!" type "!convertLog!"
            echo !C_ERROR![Error] Pre-mux conversion to MP4 failed. Attempting mux with original file anyway.!C_RESET!
        ) else (
            echo !C_STATUS![Status] Conversion complete. Using converted MP4 for muxing.!C_RESET!
            set "muxInput=!convertedMp4!"
            set "CONVERTED_INPUT=1"
        )
    )

    rem Muxing sequence
    if defined HAS_MUX_SUBS (
        echo !ESC![96m------------------------------------------------------------!ESC![0m
        echo !ESC![93mVideo: !ESC![92m%%~nxV!ESC![0m
        echo !C_WARN![Result]!C_PROCESS! Usable subtitle tracks ready for muxing: !SUBIDX!!C_RESET!
        echo !ESC![96m------------------------------------------------------------!ESC![0m
    )
    if not defined HAS_MUX_SUBS (
        echo !C_WARN![Warning] No valid subtitles remained after cleanup. File was not modified.!C_RESET!
    )
    if defined HAS_MUX_SUBS (
        if exist "!output!\ffmpeg_error.log" del /f /q "!output!\ffmpeg_error.log"
        echo !C_STATUS![Status] Muxing subtitles into MKV...!C_RESET!
        ffmpeg -hide_banner -y -i "!muxInput!" !SUBS! -map 0:v -map 0:a !MAPS! -map_metadata 0 -metadata subtitle_batch_processed=1 -c copy -c:s srt !DISPS! "!output!\final.mkv" >"!output!\ffmpeg_error.log" 2>&1
        set "FFMPEG_FAILED="
        if errorlevel 1 set "FFMPEG_FAILED=1"
        findstr /i /c:"Error muxing" /c:"Error writing trailer" /c:"Invalid argument" "!output!\ffmpeg_error.log" >nul 2>nul
        if not errorlevel 1 set "FFMPEG_FAILED=1"
        if defined FFMPEG_FAILED (
            type "!output!\ffmpeg_error.log"
            echo !C_ERROR![Error] FFmpeg muxing failed. Original file was NOT replaced.!C_RESET!
            if exist "!output!\final.mkv" del /f /q "!output!\final.mkv"
        )
        if not defined FFMPEG_FAILED if not exist "!output!\final.mkv" (
            type "!output!\ffmpeg_error.log"
            echo !C_ERROR![Error] FFmpeg finished without creating final.mkv. Original file was NOT replaced.!C_RESET!
            set "FFMPEG_FAILED=1"
        )
        
        rem Metadata Restoration & Replacement
        if not defined FFMPEG_FAILED if exist "!output!\final.mkv" (
            move /y "!origFile!" "!origFile!.bak" >nul
            if exist "!origFile!.bak" (
                move /y "!output!\final.mkv" "!targetFile!" >nul
                if exist "!targetFile!" (
                    set "VIDEO_MODIFIED=1"
                    echo !C_STATUS![Status] MKV created: !targetFile!!C_RESET!
                    echo !C_STATUS![Status] Applying metadata...!C_RESET!
                    powershell -NoProfile -Command "$target=[DateTime]::FromFileTimeUtc([Int64]$env:tsWrite); $create=[DateTime]::FromFileTimeUtc([Int64]$env:tsCreate); $ok=$false; for($i=0;$i -lt 5;$i++){ $f=Get-Item -LiteralPath $env:targetFile; $f.CreationTimeUtc=$create; $f.LastWriteTimeUtc=$target; Start-Sleep -Milliseconds 300; $f=Get-Item -LiteralPath $env:targetFile; if([Math]::Abs(($f.CreationTimeUtc-$create).TotalSeconds) -le 2 -and [Math]::Abs(($f.LastWriteTimeUtc-$target).TotalSeconds) -le 2){ $ok=$true; break } }; if(-not $ok){ Write-Error ('Timestamp verification failed. Created=' + $f.CreationTimeUtc + ' expected=' + $create + '; Modified=' + $f.LastWriteTimeUtc + ' expected=' + $target); exit 1 }"
                    powershell -NoProfile -Command "$manifest=Join-Path $env:output 'provided_sources.txt'; if(Test-Path -LiteralPath $manifest){ foreach($line in Get-Content -LiteralPath $manifest -Encoding UTF8){ if(-not $line.Trim()){ continue }; $parts=$line -split \"`t\",2; if($parts.Count -ne 2){ continue }; $source=$parts[0]; $validated=Join-Path $env:output $parts[1]; if((Test-Path -LiteralPath $source -PathType Leaf) -and (Test-Path -LiteralPath $validated -PathType Leaf)){ Remove-Item -LiteralPath $source -Force; Write-Host ('[Cleanup] Removed validated external subtitle: ' + (Split-Path -Leaf $source)) } else { Write-Host ('[Cleanup] Kept external subtitle because validation gate did not pass: ' + (Split-Path -Leaf $source)) } } }"
                    if errorlevel 1 (
                        echo !C_WARN![Warning] File replaced, but timestamp sync failed.!C_RESET!
                    ) else (
                        echo !C_SUCCESS![Success] Timestamp synced, file replaced, and validated external subtitles cleaned up.!C_RESET!
                    )
                    del /f /q "!origFile!.bak" >nul 2>nul
                ) else (
                    move /y "!origFile!.bak" "!origFile!" >nul
                    echo !C_ERROR![Error] Replacement failed. Original file restored.!C_RESET!
                )
            )
        )
    )

    rem Clean up converted source MP4 if one was created
    if defined CONVERTED_INPUT (
        if exist "!output!\converted_source.mp4" del /f /q "!output!\converted_source.mp4" >nul 2>nul
    )

    rem Cleanup workspace
    if defined DOWNLOAD_ATTEMPTED if not defined VIDEO_MODIFIED (
        if !VALID_AFTER_DOWNLOAD! EQU 0 (
            set /a DEFECTIVE_STREAK+=1
        ) else (
            set /a DEFECTIVE_STREAK=0
        )
        call :SaveState
        if !DEFECTIVE_STREAK! GEQ !DEFECTIVE_LIMIT! (
            call :CleanupTemp
            call :DefectiveSubtitlesMessage
            if not defined GUI_MODE pause
            call :ReleaseSingleInstance
            exit /b 1
        )
    )
    if defined VIDEO_MODIFIED (
        set /a DEFECTIVE_STREAK=0
        call :SaveState
    )
    del /f /q "!output!\*.*" >nul 2>nul
    for /d %%D in ("!output!\*") do rd /s /q "%%~fD" >nul 2>nul
    )
)

if defined SKIPPED_PROCESSED_COUNT (
    echo !C_SKIP![Skip] Previously processed files skipped this session: !SKIPPED_PROCESSED_COUNT!!C_RESET!
)
call :CleanupTemp
echo !C_SUCCESS!All finished!!C_RESET!
call :ReleaseSingleInstance
if not defined GUI_MODE pause
exit /b 0

:AcquireSingleInstance
>"!queueTicket!" echo(!RUN_ID!
set "WAIT_MESSAGE_SHOWN="
:WaitForQueueTurn
set "FIRST_QUEUE_TICKET="
for /f "usebackq delims=" %%Q in (`powershell -NoProfile -Command "$first=Get-ChildItem -LiteralPath $env:queueDir -Filter '*.ticket' -File -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -First 1; if($first){ $first.FullName }"`) do set "FIRST_QUEUE_TICKET=%%Q"
if /i not "!FIRST_QUEUE_TICKET!"=="!queueTicket!" (
    if not defined WAIT_MESSAGE_SHOWN (
        echo.
        echo !C_WARN![Wait] Another session of this program is running.!C_RESET!
        echo !C_WARN![Wait] Processing will start automatically when the other session is complete.!C_RESET!
        set "WAIT_MESSAGE_SHOWN=1"
    )
    timeout /t 5 /nobreak >nul
    goto WaitForQueueTurn
)
mkdir "!lockDir!" >nul 2>nul
if not errorlevel 1 (
    set "LOCK_ACQUIRED=1"
    >"!lockDir!\owner.txt" echo(!RUN_ID!
    for /f %%P in ('powershell -NoProfile -Command "[System.Diagnostics.Process]::GetCurrentProcess().Id"') do >"!lockDir!\pid.txt" echo(%%P
    if defined WAIT_MESSAGE_SHOWN echo !C_STATUS![Status] Previous session completed. Starting processing now.!C_RESET!
    exit /b 0
)
if not defined WAIT_MESSAGE_SHOWN (
    echo.
    echo !C_WARN![Wait] Another session of this program is running.!C_RESET!
    echo !C_WARN![Wait] Processing will start automatically when the other session is complete.!C_RESET!
    set "WAIT_MESSAGE_SHOWN=1"
)
timeout /t 5 /nobreak >nul
goto WaitForQueueTurn

:ReleaseSingleInstance
if defined LOCK_ACQUIRED if exist "!lockDir!" rd /s /q "!lockDir!" >nul 2>nul
if exist "!queueTicket!" del /f /q "!queueTicket!" >nul 2>nul
set "LOCK_ACQUIRED="
exit /b 0

:LoadState
set /a DOWNLOADS_TODAY=0
set /a DEFECTIVE_STREAK=0
if exist "!stateFile!" (
    for /f "usebackq tokens=1,* delims==" %%A in ("!stateFile!") do (
        if /i "%%A"=="DATE" set "STATE_DATE=%%B"
        if /i "%%A"=="DOWNLOADS_TODAY" set /a DOWNLOADS_TODAY=%%B
    )
)
if not "!STATE_DATE!"=="!TODAY!" (
    set /a DOWNLOADS_TODAY=0
    call :SaveState
)
exit /b 0

:SaveState
(
    echo DATE=!TODAY!
    echo DOWNLOADS_TODAY=!DOWNLOADS_TODAY!
) > "!stateFile!"
exit /b 0

:BeforeDownload
for /f %%A in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath $env:output -Filter '*.srt' -File -ErrorAction SilentlyContinue).Count"') do set /a SRT_COUNT_BEFORE=%%A
exit /b 0

:AfterDownload
for /f %%A in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath $env:output -Filter '*.srt' -File -ErrorAction SilentlyContinue).Count"') do set /a SRT_COUNT_AFTER=%%A
set /a NEW_DOWNLOADS=SRT_COUNT_AFTER-SRT_COUNT_BEFORE
if !NEW_DOWNLOADS! LSS 0 set /a NEW_DOWNLOADS=0
if !NEW_DOWNLOADS! GTR 0 (
    set /a DOWNLOADS_TODAY+=NEW_DOWNLOADS
    call :SaveState
)
if !DOWNLOADS_TODAY! GEQ !DAILY_LIMIT! (
    >"!dailyLimitLock!" echo(!TODAY!
    call :CleanupTemp
    call :DailyLimitMessage
    set "STOP_SCRIPT=1"
)
exit /b 0

:CountValidDownloaded
for /f %%A in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath $env:output -Filter ($env:name + '*.srt') -File -ErrorAction SilentlyContinue).Count"') do set /a CURRENT_VALID_SRT_COUNT=%%A
set /a VALID_AFTER_DOWNLOAD=CURRENT_VALID_SRT_COUNT-PROVIDED_SRT_COUNT
if !VALID_AFTER_DOWNLOAD! LSS 0 set /a VALID_AFTER_DOWNLOAD=0
exit /b 0

:PromptReprocess
:: Honor preset policy (e.g., from GUI) so single-video reprocessing follows the session setting
if /i "!REPROCESS_POLICY!"=="REPROCESS_ALL" (
    set "ALREADY_PROCESSED="
    echo !C_STATUS![Status] Re-process all policy active — re-processing previously processed file.!C_RESET!
    exit /b 0
)
if /i "!REPROCESS_POLICY!"=="SKIP_ALL" (
    echo !C_SKIP![Skip] Skip-all policy active — skipping previously processed file.!C_RESET!
    exit /b 0
)
echo !C_WARN![Prompt] This file appears to have been previously processed:!C_RESET!
echo !C_WARN![Prompt] !origFile!!C_RESET!
set "REPROCESS_CHOICE="
<nul set /p "=!C_WARN!Re-process this file anyway? [Y/N]: !C_RESET!"
choice /c YN /n >nul
set "REPROCESS_CHOICE=!errorlevel!"
if not "!REPROCESS_CHOICE!"=="1" (
    echo !C_SKIP![Skip] User chose not to re-process previously processed file.!C_RESET!
    exit /b 0
)
set "ALREADY_PROCESSED="
echo !C_STATUS![Status] User chose to re-process previously processed file.!C_RESET!
echo !C_STATUS![Status] Reprocess mode enabled. Embedded subtitles will be extracted, cleaned, and rebuilt.!C_RESET!
exit /b 0

:ApplySessionReprocessPolicy
if not defined REPROCESS_POLICY call :PromptSessionReprocessPolicy
if /i "!REPROCESS_POLICY!"=="REPROCESS_ALL" (
    set "ALREADY_PROCESSED="
    echo !C_STATUS![Status] Session policy: re-processing previously processed file.!C_RESET!
    echo !C_STATUS![Status] Reprocess mode enabled. Embedded subtitles will be extracted, cleaned, and rebuilt.!C_RESET!
    exit /b 0
)
if /i "!REPROCESS_POLICY!"=="ASK_EACH" (
    call :PromptReprocess
    exit /b 0
)
if /i "!REPROCESS_POLICY!"=="SKIP_ALL" (
    if not defined SKIP_ALL_NOTICE_SHOWN (
        echo !C_SKIP![Skip] Session policy: skipping all previously processed files.!C_RESET!
        set "SKIP_ALL_NOTICE_SHOWN=1"
    )
) else (
    echo !C_SKIP![Skip] Session policy: skipping previously processed file.!C_RESET!
)
exit /b 0

:PromptSessionReprocessPolicy
:: If policy already set (e.g., from GUI), don't prompt
if defined REPROCESS_POLICY (
    echo !C_STATUS![Status] Reprocess policy already set to: !REPROCESS_POLICY!!C_RESET!
    exit /b 0
)

echo.
echo ________________________________________________________________________________
echo.
echo !C_WARN![Warning] Previously processed video files were found in this session.!C_RESET!
echo.
echo !C_WARN!Choose how to handle previously processed files:!C_RESET!
echo.
echo !C_PROCESS![1] Skip all.!C_RESET!
echo !C_PROCESS![2] Re-process all.!C_RESET!
echo !C_PROCESS![3] Ask me to decide for every file.!C_RESET!
echo.
set "REPROCESS_POLICY_CHOICE="
<nul set /p "=!C_WARN!Choice [1/2/3]: !C_RESET!"
choice /c 123 /n >nul
set "REPROCESS_POLICY_CHOICE=!errorlevel!"
if "!REPROCESS_POLICY_CHOICE!"=="2" (
    set "REPROCESS_POLICY=REPROCESS_ALL"
    echo.
    echo !C_STATUS![Status] Selected: [2] Re-process all.!C_RESET!
    exit /b 0
)
if "!REPROCESS_POLICY_CHOICE!"=="3" (
    set "REPROCESS_POLICY=ASK_EACH"
    echo.
    echo !C_STATUS![Status] Selected: [3] Ask me to decide for every file.!C_RESET!
    exit /b 0
)
set "REPROCESS_POLICY=SKIP_ALL"
echo.
echo !C_STATUS![Status] Selected: [1] Skip all.!C_RESET!
exit /b 0

:CleanupStaleTempRuns
powershell -NoProfile -Command "$root=$env:tempRoot; if(-not $root -or -not (Test-Path -LiteralPath $root)){ exit }; $cutoff=(Get-Date).AddHours(-24); Get-ChildItem -LiteralPath $root -Directory -Filter Run_* -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cutoff } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
exit /b 0

:CleanupTemp
if exist "!output!" (
    rd /s /q "!output!" >nul 2>nul
)
if exist "!stateDir!" (
    rd /s /q "!stateDir!" >nul 2>nul
)
exit /b 0

:WaitForNewInput
powershell -NoProfile -Command "try { while([Console]::KeyAvailable){ [Console]::ReadKey($true) | Out-Null } } catch {}"
echo !C_WARN![Prompt] Press any key when ready to enter a new path or selection.!C_RESET!
powershell -NoProfile -Command "try { [Console]::ReadKey($true) | Out-Null; while([Console]::KeyAvailable){ [Console]::ReadKey($true) | Out-Null } } catch { Read-Host 'Press Enter when ready' | Out-Null }"
exit /b 0

:InvalidInputStop
echo !C_WARN![Prompt] Please restart the script and provide a valid selection.!C_RESET!
echo !C_WARN![Prompt] Press any key to close this window.!C_RESET!
pause >nul
exit /b 1

:ReadDroppedArgs
if "%~1"=="" exit /b 0
>>"!inputList!" echo(%~f1
shift
goto ReadDroppedArgs

:DailyLimitMessage
echo.
echo !C_ERROR![Stop] The maximum number of 1000 subtitle downloads per day set by the hosting site has been reached.!C_RESET!
echo !C_ERROR![Stop] Processing has stopped for today. The current video file was left untouched.!C_RESET!
echo !C_ERROR![Stop] Please try again tomorrow.!C_RESET!
echo.
exit /b 0

:DefectiveSubtitlesMessage
echo.
echo !C_ERROR![Stop] Subtitles downloaded from OpenSubtitles are defective.!C_RESET!
echo !C_ERROR![Stop] Either the subscription has expired or the stored credentials need to be revalidated.!C_RESET!
echo !C_ERROR![Stop] Check with the hosting site or confirm the credentials stored in the local configuration files.!C_RESET!
echo !C_ERROR![Stop] Likely Subliminal configuration locations:!C_RESET!
echo !C_ERROR![Stop] C:\Users\ibrah\AppData\Roaming\subliminal\!C_RESET!
echo !C_ERROR![Stop] C:\Users\ibrah\AppData\Local\subliminal\!C_RESET!
echo !C_ERROR![Stop] The current video file was left untouched.!C_RESET!
echo.
exit /b 0
