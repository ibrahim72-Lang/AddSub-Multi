# 🎬 AddSub-Multi GUI v6.0

A modern graphical interface for AddSub-Multi-6.0.bat

## 🚀 Quick Start

### Option 1: Double-Click Launcher
Simply double-click: **`Launch AddSub GUI.bat`**

### Option 2: Run Directly
```bash
python AddSub-Multi-GUI.py
```

## ✨ Features

### 🎯 Core Features
- **Two-Column Layout** - Left panel for controls, right panel for console output
- **Real-Time Console** - Live processing logs displayed in dedicated panel
- **Drag & Drop Interface** - Drop video files or folders directly
- **Modern Card-Based UI** - Each video gets its own status card
- **Real-Time Progress** - See processing status for each file
- **Dark Theme** - Modern dark interface
- **Multi-Instance Support** - Multiple windows with automatic queuing
- **Process Control** - Pause, resume, or cancel processing anytime

### 🔒 Multi-Instance Handling
- ✅ Launch multiple instances simultaneously
- ✅ Automatic queue system (first come, first served)
- ✅ Visual waiting dialog shows your queue position
- ✅ Timer displays how long you've been waiting
- ✅ Automatic start when previous session completes
- ✅ Cancel waiting anytime

### 📊 Statistics Display
- **Files Counter** - Shows how many files selected (max 10)
- **Daily Downloads** - Tracks subtitle downloads (0/1000 daily limit)
- **Defective Streak** - Monitors subtitle quality (0/3 limit)

### ⚙️ Options (Always Visible)
Options are now displayed directly in the main UI below the browse buttons:

- **Process Subfolders** - Process videos in subfolders when selecting a folder
- **Re-process Policy** - Choose how to handle previously processed files:
  - Skip all previously processed files (default)
  - Re-process all files
  - Ask me for each file

## 📖 How to Use

### Step 1: Add Files
You can add files in three ways:
1. **Drag & Drop** - Drag video files or a folder onto the drop zone
2. **Browse Files** - Click "📄 Browse Files" to select individual video files
3. **Browse Folder** - Click "📁 Browse Folder" to select a folder

### Step 2: Configure (Optional)
- Set your options directly in the main UI (below browse buttons)

### Step 3: Start Processing
- Click **▶️ Start Processing** button
- Watch real-time progress in the console panel (right side)
- Cards will show status: Waiting → Processing → Downloading → Embedding → Completed

### Step 4: Control Processing
- **⏸️ Pause** - Temporarily pause processing
- **▶️ Resume** - Continue from where you paused
- **❌ Cancel** - Abort the current operation

### Step 5: Multiple Sessions
If you launch another instance while processing:
- A waiting dialog appears showing your queue position
- Window automatically starts when ready
- You can cancel and close the waiting window anytime

## 🎨 Status Indicators

### Card Status Icons
- ⏱️ **Waiting** - Queued for processing (gray)
- 🔄 **Processing** - Currently being processed (cyan)
- ⬇️ **Downloading** - Downloading subtitles (cyan)
- ⚙️ **Embedding** - Embedding subtitles into video (cyan)
- ✅ **Success** - Completed successfully (green)
- ❌ **Error** - Error occurred (red)
- ⏭️ **Skip** - File was skipped (gray)

### Stats Bar
- 📊 **Files: X/10** - Number of selected files (max 10)
- ⬇️ **Today: X/1000** - Subtitle downloads today
- 🔹 **Streak: X/3** - Defective subtitle streak

## 📁 File Limits

- **Individual Files**: Max 10 video files per session
- **Folders**: 1 folder per session (processes all videos inside)
- **Daily Downloads**: 1000 subtitle downloads per day (OpenSubtitles limit)

## 🛠️ Technical Details

### Zero Modification Approach
- ✅ **No changes** to `AddSub-Multi-6.0.bat`
- ✅ **No changes** to any Python helper scripts
- ✅ Pure wrapper - GUI calls the batch file as subprocess
- ✅ Batch file can still be used independently

### Requirements
- Python 3.x
- customtkinter (installed automatically)
- tkinterdnd2 (installed automatically)
- All dependencies from AddSub-Multi-6.0.bat

### File Structure
```
Your Folder/
├── Launch AddSub GUI.bat          ← Double-click to launch GUI
├── AddSub-Multi-GUI.py            ← GUI application
├── AddSub-Multi-6.0.bat           ← Original batch file (unchanged)
├── split_input_paths.py           ← Helper scripts (unchanged)
├── use_provided_english_sub.py    
├── validate_subs.py               
├── fix_srt_overlaps.py            
├── detect_downloaded_dual_subs.py 
├── combine_dual_subs.py           
└── validate_subs_ffmpeg.py        
```

### Queue System
The GUI uses the same queue/lock system as the batch file:
- **Lock Directory**: `%LOCALAPPDATA%\AddSub-Multi\AddSub-Multi.lock\`
- **Queue Directory**: `%LOCALAPPDATA%\AddSub-Multi\AddSub-Multi.queue\`
- **State File**: `%LOCALAPPDATA%\AddSub-Multi\subtitle_download_state.txt`

## 🆘 Troubleshooting

### GUI Won't Launch
**Error: "CustomTkinter is required"**
```bash
pip install customtkinter tkinterdnd2
```

**Error: "AddSub-Multi-6.0.bat not found"**
- Ensure `AddSub-Multi-GUI.py` is in the same folder as `AddSub-Multi-6.0.bat`

### Processing Issues
- The GUI calls the batch file directly
- All processing logic is handled by the batch file
- Check batch file dependencies (ffmpeg, python, subliminal, etc.)

### Multiple Instances Not Working
- Check that `%LOCALAPPDATA%\AddSub-Multi\` directory exists and is writable
- Ensure no other program is locking the queue directory

## 🎯 Tips & Tricks

1. **Minimize While Waiting** - Waiting dialog can be minimized to taskbar
2. **Batch File Still Works** - You can still drag-drop files onto the .bat file
3. **Settings Persist** - Re-process policy and subfolder settings are remembered
4. **Cancel Anytime** - Close the waiting dialog to cancel queuing

## 📝 Version

**GUI Version**: 6.0  
**Compatible with**: AddSub-Multi-6.0.bat  
**Last Updated**: 2026

## 🙏 Credits

GUI wrapper created for AddSub-Multi subtitle automation tool.

---

**Enjoy the modern interface! 🎉**
