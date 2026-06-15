"""
AddSub-Multi GUI Wrapper v6.0
A modern graphical interface for AddSub-Multi-6.0.bat
Zero modifications to existing batch/Python files - pure wrapper approach
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import json
import subprocess
import threading
import os
import shutil
import time
import re
import traceback
import psutil
from pathlib import Path
from datetime import datetime
import queue as thread_queue
import win32api
import win32gui
import win32con
import win32ui
from PIL import Image, ImageTk
import ctypes
from ctypes import wintypes, byref, sizeof, windll

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Pause/Resume: thread-suspension infrastructure (module-level, registered once) ──
TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002

class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize",             wintypes.DWORD),
        ("cntUsage",           wintypes.DWORD),
        ("th32ThreadID",       wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri",          wintypes.LONG),
        ("tpDeltaPri",         wintypes.LONG),
        ("dwFlags",            wintypes.DWORD),
    ]

_kernel32 = windll.kernel32
_kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel32.CreateToolhelp32Snapshot.restype  = wintypes.HANDLE
_kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
_kernel32.Thread32First.restype  = wintypes.BOOL
_kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
_kernel32.Thread32Next.restype  = wintypes.BOOL
_kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenThread.restype  = wintypes.HANDLE
_kernel32.SuspendThread.argtypes = [wintypes.HANDLE]
_kernel32.SuspendThread.restype  = wintypes.DWORD
_kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
_kernel32.ResumeThread.restype  = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype  = wintypes.BOOL

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

class VideoCard(ctk.CTkFrame):
    """Individual card for each video file"""

    _SPINNER_CHARS = ['◐', '◓', '◑', '◒']

    def __init__(self, parent, filepath, on_remove=None, icon_getter=None, initial_status=None):
        super().__init__(parent, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=4,
                        border_width=1, border_color=("#C8C8C8", "#383838"))
        
        self.filepath = filepath
        self.on_remove = on_remove
        self.status = "waiting"
        self.subtitle_count = 0
        if initial_status is None:
            initial_status = "⏱️ Queued for processing"
        self._spinner_job = None
        self._spinner_idx = 0
        self._spinner_active = False
        self._highlighted = False
        self._base_fg = ("#E0E0E0", "#2B2B2B")
        
        # Single-row layout: icon | filename | status | X
        self.grid_columnconfigure(1, weight=1)
        
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filepath)[1].lstrip('.')
        
        # File-type icon
        icon_img = None
        if icon_getter:
            icon_img = icon_getter(ext)
        if icon_img:
            icon_lbl = ctk.CTkLabel(self, image=icon_img, text="", width=16)
        else:
            icon_lbl = ctk.CTkLabel(self, text="📹", width=16, font=ctk.CTkFont(family="Segoe UI", size=11))
        icon_lbl.grid(row=0, column=0, padx=(6, 3), pady=3)
        
        self.filename_label = ctk.CTkLabel(
            self, 
            text=filename, 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w"
        )
        self.filename_label.grid(row=0, column=1, sticky="w", padx=(0, 6), pady=3)
        
        self.status_label = ctk.CTkLabel(
            self, 
            text=initial_status, 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="e"
        )
        self.status_label.grid(row=0, column=2, sticky="e", padx=(8, 4), pady=3)
        
        if on_remove:
            self.remove_btn = ctk.CTkButton(
                self, 
                text="✕", 
                width=14, 
                height=14,
                command=lambda: on_remove(self),
                fg_color="#FF5252",
                hover_color="#FF1744",
                font=ctk.CTkFont(family="Segoe UI", size=9)
            )
            self.remove_btn.grid(row=0, column=3, padx=(4, 6), pady=3)
        else:
            self.remove_btn = None

    def _start_spinner(self):
        """Start the rotating spinner animation"""
        if self._spinner_active:
            return
        self._spinner_active = True
        self._spinner_idx = 0
        self._tick_spinner()

    def _tick_spinner(self):
        """Advance spinner one frame"""
        if not self._spinner_active:
            return
        self._spinner_idx = (self._spinner_idx + 1) % len(self._SPINNER_CHARS)
        self._spinner_job = self.after(200, self._tick_spinner)
        self._redraw()

    def _stop_spinner(self):
        """Stop the spinner animation"""
        self._spinner_active = False
        if self._spinner_job is not None:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None

    @staticmethod
    def _shorten_status(text):
        """Reduce verbose status text to 1-2 words for compact display"""
        if not text or not text.strip():
            return "Ready"
        # "📁 FolderName — 25 videos found" → "📁 FolderName"
        if text.startswith('📁 '):
            return re.sub(r'\s*—\s*\d+\s*videos?\s*found\s*$', '', text)
        # Strip any leading emoji/icon the text may already carry
        clean = re.sub(r'^[^\w]+', '', text).strip()
        if not clean:
            return "Ready"
        lower = clean.lower()
        if 'queued' in lower or 'queue' in lower:
            return 'Queued'
        if 'reprocess' in lower:
            return 'Ready'
        if 'converting' in lower:
            return 'Converting'
        if 'downloading' in lower or 'download' in lower:
            return 'Downloading'
        if 'muxing' in lower or 'embedding' in lower or 'embed' in lower:
            return 'Embedding'
        if 'completed' in lower:
            return 'Done'
        if 'processing' in lower or 'process' in lower:
            return 'Processing'
        if 'skipped' in lower or 'skip' in lower:
            return 'Skipped'
        if 'error' in lower:
            return 'Error'
        if 'searching' in lower or 'search' in lower:
            return 'Searching'
        if 'syncing' in lower or 'sync' in lower:
            return 'Syncing'
        if 'validating' in lower or 'validate' in lower:
            return 'Validating'
        if 'applying metadata' in lower or 'metadata' in lower:
            return 'Finalizing'
        if 'retry' in lower:
            return 'Retrying'
        if 'legacy' in lower or 'codec' in lower:
            return 'Processing'
        if 'provided' in lower:
            return 'Using existing'
        if 'created' in lower:
            return 'Muxing'
        if len(clean) <= 12:
            return clean
        return clean[:12] + '…'

    def _redraw(self):
        """Re-render the status icon on the card (text/percentage live in global status bar)"""
        status_type = self._status_type
        
        terminal_icons = {
            "waiting": "⏱️",
            "success": "✅",
            "error": "❌",
            "skip": "⏭️",
        }
        active_types = {"processing", "downloading", "embedding"}
        
        if status_type in terminal_icons:
            icon = terminal_icons[status_type]
        elif status_type in active_types:
            icon = self._SPINNER_CHARS[self._spinner_idx]
        else:
            icon = "ℹ️"
        
        colors = {
            "waiting": ("gray50", "gray60"),
            "processing": ("#F9A825", "#FFF176"),
            "downloading": ("#F9A825", "#FFF176"),
            "embedding": ("#F9A825", "#FFF176"),
            "success": ("#00D787", "#00D787"),
            "error": ("#FF5252", "#FF5252"),
            "skip": ("gray50", "gray60")
        }
        color = colors.get(status_type, ("gray50", "gray60"))
        
        self.status_label.configure(text=icon, text_color=color)

    def update_status(self, status_text, status_type="info", percentage=None, subtitle_count=None):
        """Update card status"""
        self.status = status_type
        self._status_text = status_text
        self._status_type = status_type
        self._percentage = percentage
        
        # TEMP DEBUG: trace percentage chain
        if status_type == "success":
            print(f"DEBUG update_status [{os.path.basename(self.filepath)}]: type={status_type!r} pct={percentage} subs={subtitle_count} text={status_text[:50]!r}")
        
        if subtitle_count is not None:
            self.subtitle_count = subtitle_count
        
        # Highlight card when it becomes active (persists for the session)
        if status_type in ("processing", "downloading", "embedding") and not self._highlighted:
            self._highlighted = True
            self.configure(fg_color=("#E3F2FD", "#0D47A1"),
                           border_color=("#90CAF9", "#1565C0"))
        
        # Start/stop spinner based on state
        if status_type in ("processing", "downloading", "embedding"):
            if not self._spinner_active:
                self._start_spinner()
        else:
            self._stop_spinner()
        
        self._redraw()

    def set_processing_state(self, processing):
        """Show/hide the remove button based on processing state"""
        if self.remove_btn is None:
            return
        if processing:
            self.remove_btn.grid_remove()
        else:
            self.remove_btn.grid()


class WaitingDialog(ctk.CTkToplevel):
    """Dialog shown when waiting for another instance"""
    def __init__(self, parent, queue_position, queue_ticket):
        super().__init__(parent)
        
        self.title("Waiting for Previous Session")
        self.geometry("500x400")
        self.resizable(False, False)
        
        self.queue_ticket = queue_ticket
        self.cancelled = False
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (400 // 2)
        self.geometry(f"500x400+{x}+{y}")
        
        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Title
        title = ctk.CTkLabel(
            content,
            text="⏳ WAITING FOR PREVIOUS SESSION",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=(0, 20))
        
        # Info frame
        info_frame = ctk.CTkFrame(content, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=10)
        info_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        info_content = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            info_content,
            text="Another instance is currently processing",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 15))
        
        self.position_label = ctk.CTkLabel(
            info_content,
            text=f"Your queue position: #{queue_position}",
            font=ctk.CTkFont(size=13)
        )
        self.position_label.pack(pady=(0, 15))
        
        ctk.CTkLabel(
            info_content,
            text="🔄 Checking every 5 seconds...",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        ).pack(pady=(0, 15))
        
        ctk.CTkLabel(
            info_content,
            text="This window will automatically start\nprocessing when the other session completes",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        ).pack(pady=(0, 15))
        
        self.timer_label = ctk.CTkLabel(
            info_content,
            text="⏱️ Waiting for: 00:00:00",
            font=ctk.CTkFont(size=13)
        )
        self.timer_label.pack()
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            content,
            text="Cancel and Close This Window",
            command=self.cancel,
            fg_color="#FF5252",
            hover_color="#FF1744",
            height=40
        )
        cancel_btn.pack(fill="x")
        
        # Timer
        self.start_time = time.time()
        self.update_timer()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
    def update_timer(self):
        """Update waiting timer"""
        if self.cancelled:
            return
            
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        self.timer_label.configure(text=f"⏱️ Waiting for: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
        if self.winfo_exists():
            self.after(1000, self.update_timer)
    
    def update_position(self, position):
        """Update queue position"""
        self.position_label.configure(text=f"Your queue position: #{position}")
    
    def cancel(self):
        """Cancel waiting"""
        self.cancelled = True
        if os.path.exists(self.queue_ticket):
            try:
                os.remove(self.queue_ticket)
            except:
                pass
        self.destroy()


class AddSubGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    """Main application window"""
    def __init__(self):
        super().__init__()
        
        # TkinterDnD setup
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("AddSub-Multi 6.0")
        self.geometry("850x780")
        self.minsize(850, 680)
        
        # Paths
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.batch_file = os.path.join(self.script_dir, "AddSub-Multi-6.0.bat")
        self.state_root = os.path.join(os.getenv('LOCALAPPDATA'), 'AddSub-Multi')
        self.lock_dir = os.path.join(self.state_root, 'AddSub-Multi.lock')
        self.queue_dir = os.path.join(self.state_root, 'AddSub-Multi.queue')
        self.state_file = os.path.join(self.state_root, 'subtitle_download_state.txt')
        self.temp_dir = os.path.join(self.script_dir, 'Temp')
        
        # State
        self.video_cards = []
        self.video_files = []
        self.processing = False
        self.process = None
        self._paused = False
        self._cancelled = False
        self.include_subfolders = tk.BooleanVar(value=False)
        self.reprocess_policy = tk.StringVar(value="skip")
        self.output_queue = thread_queue.Queue()
        self.activity_folder = None
        self._activity_job = None
        self._activity_snapshot = None
        self._known_run_folders = set()
        self.icon_cache = {}
        
        # Create queue directory if it doesn't exist
        os.makedirs(self.queue_dir, exist_ok=True)
        
        # Setup UI
        self.setup_ui()
        
        # Load state
        self.update_daily_stats()
        
        # Handle window close via title bar (X button)
        self.protocol("WM_DELETE_WINDOW", self.close_or_cancel)
        
        # Check for batch file
        if not os.path.exists(self.batch_file):
            messagebox.showerror(
                "Error", 
                f"AddSub-Multi-6.0.bat not found in:\n{self.script_dir}\n\nPlease place the GUI in the same folder as the batch file."
            )
            self.quit()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Main container with two columns (left panel and right console area)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=3, minsize=330)  # Left panel (330px)
        main_container.grid_columnconfigure(1, weight=5, minsize=460)  # Right area (console + options + buttons) (460px)
        
        # Left panel container
        left_panel = ctk.CTkFrame(main_container, fg_color="transparent", width=330)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_panel.grid_rowconfigure(3, weight=1)  # File container gets the expanding space
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Enable drag and drop on entire left panel
        left_panel.drop_target_register(DND_FILES)
        left_panel.dnd_bind('<<Drop>>', self.on_drop)
        
        # Header
        header = ctk.CTkFrame(left_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        header.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(
            header,
            text="🎬 AddSub-Multi",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w")
        
        # Settings button
        self.settings_btn = ctk.CTkButton(
            header,
            text="⚙",
            width=40,
            command=self.show_settings_menu
        )
        self.settings_btn.grid(row=0, column=2)
        
        # Drop zone (shown when no files) - Smaller and compact
        self.drop_zone = ctk.CTkFrame(
            left_panel,
            fg_color=("#D0D0D0", "#2B2B2B"),
            border_color=("#00BCD4", "#00BCD4"),
            border_width=2,
            corner_radius=10,
            height=100
        )
        self.drop_zone.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        self.drop_zone.grid_propagate(False)
        
        drop_content = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        drop_content.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(
            drop_content,
            text="💫 Drop video files here",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=3)
        
        ctk.CTkLabel(
            drop_content,
            text="Up to 50 files or 5 folders",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        ).pack()
        
        # Setup drag and drop
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self.on_drop)
        
        # Browse buttons row (always visible)
        button_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        button_row.grid_columnconfigure(2, weight=0)
        
        browse_files_btn = ctk.CTkButton(
            button_row,
            text="📄 Select Files",
            command=self.browse_files_only,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        browse_files_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        browse_folder_btn = ctk.CTkButton(
            button_row,
            text="📁 Select Folder",
            command=self.browse_folder_only,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        browse_folder_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        self.clear_list_btn = ctk.CTkButton(
            button_row,
            text="🗑",
            command=self.clear_file_list,
            height=35,
            width=40,
            font=ctk.CTkFont(size=14),
            fg_color=("#E0E0E0", "#3A3A3A"),
            hover_color=("#FF5252", "#FF5252"),
            text_color=("gray40", "gray60"),
            state="disabled"
        )
        self.clear_list_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))
        
        # File list container (hidden initially, appears in row 3)
        self.file_container = ctk.CTkScrollableFrame(
            left_panel,
            fg_color="transparent"
        )
        self.file_container.grid(row=3, column=0, sticky="nsew", pady=(0, 15))
        self.file_container.grid_remove()
        
        # Enable drag and drop on file container
        self.file_container.drop_target_register(DND_FILES)
        self.file_container.dnd_bind('<<Drop>>', self.on_drop)
        
        # Stats bar
        stats_frame = ctk.CTkFrame(left_panel, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=10)
        stats_frame.grid(row=5, column=0, sticky="ew")
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=1)
        stats_frame.grid_columnconfigure(2, weight=1)
        
        self.files_label = ctk.CTkLabel(
            stats_frame,
            text="📊 Files: 0/50",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.files_label.grid(row=0, column=0, padx=10, pady=8)
        
        self.downloads_label = ctk.CTkLabel(
            stats_frame,
            text="⬇ Today: 0/1000",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.downloads_label.grid(row=0, column=1, padx=10, pady=8)
        
        self.streak_label = ctk.CTkLabel(
            stats_frame,
            text="🔹 Streak: 0/3",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.streak_label.grid(row=0, column=2, padx=10, pady=8)
        
        # Right panel container (activity + status + console + buttons)
        right_panel = ctk.CTkFrame(main_container, fg_color="transparent", width=400)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_panel.grid_propagate(False)  # Force grid to control sizes, not widgets
        right_panel.grid_rowconfigure(0, weight=0)                       # global status (fixed, top)
        right_panel.grid_rowconfigure(1, weight=3, uniform="right_col")  # 60% console (middle)
        right_panel.grid_rowconfigure(2, weight=2, uniform="right_col")  # 40% activity (bottom)
        right_panel.grid_rowconfigure(3, weight=0)                       # options (fixed)
        right_panel.grid_rowconfigure(4, weight=0)                       # buttons (fixed)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # ── Global processing status (below activity, above console) ──
        self.global_status_frame = ctk.CTkFrame(
            right_panel,
            fg_color=("#E0E0E0", "#2B2B2B"),
            corner_radius=10
        )
        self.global_status_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 8))
        self.global_status_frame.grid_rowconfigure(0, weight=1)
        self.global_status_frame.grid_columnconfigure(0, weight=0)  # "Status:" label
        self.global_status_frame.grid_columnconfigure(1, weight=1)  # dynamic text

        self._status_prefix_label = ctk.CTkLabel(
            self.global_status_frame,
            text="Status:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w"
        )
        self._status_prefix_label.grid(row=0, column=0, sticky="w", padx=(15, 4), pady=(12, 12))

        self.global_status_label = ctk.CTkLabel(
            self.global_status_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#B8860B", "#FFD700"),  # yellow/gold that pops on both light/dark
            anchor="w",
            justify="left",
            wraplength=330
        )
        self.global_status_label.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=(12, 12))
        
        # Console output panel
        console_panel = ctk.CTkFrame(right_panel, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=10)
        console_panel.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        console_panel.grid_rowconfigure(1, weight=1)
        console_panel.grid_columnconfigure(0, weight=1)
        
        # Console header
        console_header = ctk.CTkLabel(
            console_panel,
            text="📋 Console Output",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        console_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        
        # Console text widget
        self.console_text = ctk.CTkTextbox(
            console_panel,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            wrap="word",
            state="disabled"
        )
        self.console_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Enable drag and drop on console area
        console_panel.drop_target_register(DND_FILES)
        console_panel.dnd_bind('<<Drop>>', self.on_drop)
        self.console_text.drop_target_register(DND_FILES)
        self.console_text.dnd_bind('<<Drop>>', self.on_drop)
        right_panel.drop_target_register(DND_FILES)
        right_panel.dnd_bind('<<Drop>>', self.on_drop)
        
        # Configure color tags for ANSI colors
        self.setup_console_colors()
        
        # Activity panel (session temp folder viewer)
        activity_panel = ctk.CTkFrame(right_panel, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=10)
        activity_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        activity_panel.grid_rowconfigure(1, weight=1)
        activity_panel.grid_columnconfigure(0, weight=1)
        
        self.activity_header = ctk.CTkLabel(
            activity_panel,
            text="📂 Session Activity",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w"
        )
        self.activity_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 6))
        
        self.activity_frame = ctk.CTkScrollableFrame(
            activity_panel,
            fg_color="transparent"
        )
        self.activity_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        
        self.activity_placeholder = ctk.CTkLabel(
            self.activity_frame,
            text="No active session",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray50", "gray60")
        )
        self.activity_placeholder.pack(fill="x")
        
        # Options section (compact, above buttons)
        options_frame = ctk.CTkFrame(right_panel, fg_color=("#E0E0E0", "#2B2B2B"), corner_radius=8)
        options_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        options_frame.grid_columnconfigure(0, weight=0)  # Fixed width for checkbox
        options_frame.grid_columnconfigure(1, weight=1)  # Expandable for dropdown
        
        # Enable drag and drop on options frame
        options_frame.drop_target_register(DND_FILES)
        options_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        # Subfolder checkbox (left side, text left, checkbox right)
        self.subfolder_container = ctk.CTkFrame(options_frame, fg_color="transparent")
        self.subfolder_container.grid(row=0, column=0, sticky="w", padx=(15, 10), pady=12)
        
        # Label on left
        ctk.CTkLabel(
            self.subfolder_container,
            text="📁 Process\nSubfolders",
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="left"
        ).pack(side="left", padx=(0, 8))
        
        # Checkbox on right (no text)
        self.subfolder_check = ctk.CTkCheckBox(
            self.subfolder_container,
            text="",
            variable=self.include_subfolders,
            width=24
        )
        self.subfolder_check.pack(side="left")
        
        # Re-process dropdown (right side)
        reprocess_container = ctk.CTkFrame(options_frame, fg_color="transparent")
        reprocess_container.grid(row=0, column=1, sticky="e", padx=12, pady=10)
        
        ctk.CTkLabel(
            reprocess_container,
            text="🔄 Re-process\nFiles:",
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="left"
        ).pack(side="left", padx=(0, 8))
        
        self.reprocess_dropdown = ctk.CTkComboBox(
            reprocess_container,
            values=["Skip processed", "Re-process all", "Ask me to decide"],
            width=165,
            height=30,
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=12),
            state="readonly",
            command=self.on_reprocess_change
        )
        self.reprocess_dropdown.set("Skip processed")
        self.reprocess_dropdown.pack(side="left")
        
        # Control buttons (below options, always visible)
        button_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        button_frame.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 15))
        button_frame.grid_columnconfigure(0, weight=1)  # Start button - expandable
        button_frame.grid_columnconfigure(1, weight=0)  # Pause button - fixed
        button_frame.grid_columnconfigure(2, weight=0)  # Cancel button - fixed
        
        # Enable drag and drop on button frame
        button_frame.drop_target_register(DND_FILES)
        button_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        self.start_button = ctk.CTkButton(
            button_frame,
            text="▶️ Start",
            command=self.start_processing,
            height=45,
            width=160,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#00D787",
            hover_color="#00C878",
            text_color="#000000",
            text_color_disabled="#404040"
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.start_button.configure(state="disabled")
        
        self.pause_button = ctk.CTkButton(
            button_frame,
            text="⏸ Pause",
            command=self.pause_processing,
            height=45,
            width=75,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#FFA726",
            hover_color="#FF9800",
            text_color="#000000",
            text_color_disabled="#404040",
            state="disabled"
        )
        self.pause_button.grid(row=0, column=1, sticky="", padx=(0, 5))
        
        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="❌ Close",
            command=self.close_or_cancel,
            height=45,
            width=75,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#FF5252",
            hover_color="#FF1744",
            text_color="#000000",
            text_color_disabled="#404040",
            state="normal"
        )
        self.cancel_button.grid(row=0, column=2, sticky="")
    
    def show_settings_menu(self):
        """Show settings popup menu below the settings button"""
        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.overrideredirect(True)
        menu.resizable(False, False)
        menu.configure(fg_color=("#F0F0F0", "#2B2B2B"))
        
        menu.update_idletasks()
        mw, mh = 280, 205
        
        # Position below the settings button using its actual screen coordinates
        btn_x = self.settings_btn.winfo_rootx()
        btn_y = self.settings_btn.winfo_rooty()
        btn_h = self.settings_btn.winfo_height()
        settings_x = btn_x + self.settings_btn.winfo_width() - mw
        settings_y = btn_y + btn_h + 4
        menu.geometry(f"{mw}x{mh}+{settings_x}+{settings_y}")
        
        menu.grab_set()
        menu.focus_set()
        
        def on_dismiss(_event=None):
            menu.destroy()
        
        menu.bind("<FocusOut>", on_dismiss)
        menu.bind("<Escape>", on_dismiss)
        
        # ── Title ──
        ctk.CTkLabel(
            menu, text="⚙ Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(12, 8))
        
        # ── Process Subfolders ──
        subfolder_row = ctk.CTkFrame(menu, fg_color="transparent")
        subfolder_row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(
            subfolder_row, text="📁 Process Subfolders",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        ctk.CTkCheckBox(
            subfolder_row, text="",
            variable=self.include_subfolders,
            width=24
        ).pack(side="right")
        
        # ── Re-process Policy ──
        ctk.CTkLabel(
            menu, text="🔄 Re-process Files:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 2))
        
        policy_var = tk.StringVar(value=self.reprocess_policy.get())
        
        def apply_policy():
            self.reprocess_policy.set(policy_var.get())
            # Sync the main UI dropdown
            mapping = {"skip": "Skip processed", "reprocess": "Re-process all", "ask": "Ask me to decide"}
            self.reprocess_dropdown.set(mapping.get(policy_var.get(), "Skip processed"))
        
        policies = [
            ("Skip all processed files", "skip"),
            ("Re-process all files", "reprocess"),
            ("Ask me for each file", "ask"),
        ]
        for text, val in policies:
            ctk.CTkRadioButton(
                menu, text=text,
                variable=policy_var, value=val,
                command=apply_policy,
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w", padx=24, pady=1)
        
        # ── Separator ──
        ctk.CTkFrame(menu, height=1, fg_color=("gray70", "gray50")).pack(fill="x", padx=12, pady=(8, 4))
        
        # ── Reset Counter ──
        def on_reset_counter():
            menu.destroy()
            state_file = os.path.join(os.getenv('LOCALAPPDATA'), 'AddSub-Multi', 'subtitle_download_state.txt')
            if os.path.isfile(state_file):
                try:
                    os.remove(state_file)
                    self.update_daily_stats()
                    messagebox.showinfo("Reset", "✅ Counter reset — 1000 downloads/day restored")
                except:
                    messagebox.showerror("Error", "❌ Could not reset counter")
            else:
                messagebox.showinfo("Reset", "✅ No counter to reset — fresh start already active")
        
        ctk.CTkButton(
            menu,
            text="📥 Reset counter for 1000 downloads/day",
            command=on_reset_counter,
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="transparent",
            hover_color=("#CCCCCC", "#3A3A3A"),
            text_color=("gray10", "gray90"),
            anchor="w"
        ).pack(fill="x", padx=8, pady=(2, 8))
    
    def clear_state(self):
        """Clear lock directories, queue tickets, and state file"""
        import glob
        
        local_appdata = os.path.join(os.getenv('LOCALAPPDATA'), 'AddSub-Multi')
        cleared = []
        
        # Clear queue tickets
        queue_dir = os.path.join(local_appdata, 'AddSub-Multi.queue')
        if os.path.isdir(queue_dir):
            for f in glob.glob(os.path.join(queue_dir, '*.ticket')):
                try:
                    os.remove(f)
                    cleared.append(f"Queue ticket: {os.path.basename(f)}")
                except:
                    pass
        
        # Clear lock directory
        lock_dir = os.path.join(local_appdata, 'AddSub-Multi.lock')
        if os.path.isdir(lock_dir):
            try:
                import shutil
                shutil.rmtree(lock_dir)
                cleared.append("Lock directory")
            except:
                pass
        
        # Clear state file (resets defective streak and daily count)
        state_file = os.path.join(local_appdata, 'subtitle_download_state.txt')
        if os.path.isfile(state_file):
            try:
                os.remove(state_file)
                cleared.append("State file (streak + daily count)")
            except:
                pass
        
        if cleared:
            messagebox.showinfo("Cleared", "Reset complete:\n• " + "\n• ".join(cleared))
        else:
            messagebox.showinfo("Nothing to clear", "No locks, queue tickets, or state file found.")
    
    def setup_console_colors(self):
        """Configure color tags for ANSI terminal colors"""
        # ANSI color mapping (standard terminal colors)
        colors = {
            'black': '#000000',
            'red': '#FF5555',
            'green': '#50FA7B',
            'yellow': '#F1FA8C',
            'blue': '#8BE9FD',
            'magenta': '#FF79C6',
            'cyan': '#8BE9FD',
            'white': '#F8F8F2',
            'bright_black': '#6272A4',
            'bright_red': '#FF6E6E',
            'bright_green': '#69FF94',
            'bright_yellow': '#FFFFA5',
            'bright_blue': '#D6FCFF',
            'bright_magenta': '#FF92DF',
            'bright_cyan': '#A4FFFF',
            'bright_white': '#FFFFFF',
        }
        
        # Configure tags in the underlying tk.Text widget
        text_widget = self.console_text._textbox
        for name, color in colors.items():
            text_widget.tag_config(name, foreground=color)
        text_widget.tag_config('bold', font=('Consolas', 14, 'bold'))
    
    def parse_ansi_text(self, text):
        """Parse ANSI color codes and return list of (text, tag) tuples"""
        ansi_pattern = re.compile(r'\x1b\[([0-9;]*)m')
        
        # ANSI code to tag mapping
        ansi_to_tag = {
            '0': None,      # Reset
            '1': 'bold',    # Bold
            '30': 'black', '31': 'red', '32': 'green', '33': 'yellow',
            '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white',
            '90': 'bright_black', '91': 'bright_red', '92': 'bright_green', '93': 'bright_yellow',
            '94': 'bright_blue', '95': 'bright_magenta', '96': 'bright_cyan', '97': 'bright_white',
        }
        
        segments = []
        current_tag = None
        last_pos = 0
        
        for match in ansi_pattern.finditer(text):
            # Add text before this code
            if match.start() > last_pos:
                plain_text = text[last_pos:match.start()]
                if plain_text:
                    segments.append((plain_text, current_tag))
            
            # Update current tag based on ANSI code
            codes = match.group(1).split(';')
            for code in codes:
                if code in ansi_to_tag:
                    current_tag = ansi_to_tag[code]
            
            last_pos = match.end()
        
        # Add remaining text
        if last_pos < len(text):
            remaining = text[last_pos:]
            if remaining:
                segments.append((remaining, current_tag))
        
        return segments if segments else [(text, None)]
    
    def on_reprocess_change(self, choice):
        """Update reprocess policy when dropdown changes"""
        mapping = {
            "Skip processed": "skip",
            "Re-process all": "reprocess",
            "Ask me to decide": "ask"
        }
        val = mapping.get(choice, "skip")
        self.reprocess_policy.set(val)
        print(f"DEBUG: Reprocess dropdown changed to '{choice}' -> policy='{val}'")
    
    def browse_files_only(self):
        """Browse for video files only"""
        files = filedialog.askopenfilenames(
            title="Select Video Files (Max 50)",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.avi *.m4v *.mov *.wmv *.flv *.webm *.mpg *.mpeg *.ts *.m2ts"),
                ("All Files", "*.*")
            ]
        )
        if files:
            self.add_files(list(files))
    
    def browse_folder_only(self):
        """Browse for folder only"""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self.add_folder(folder)
    
    def on_drop(self, event):
        """Handle drag and drop"""
        files = self.parse_drop_data(event.data)
        
        if not files:
            return
        
        # Check if any dropped item is a directory
        folders = [f for f in files if os.path.isdir(f)]
        video_files = [f for f in files if os.path.isfile(f) and self.is_video_file(f)]
        
        if folders:
            if len(folders) > 5:
                messagebox.showerror("Error", "Maximum 5 folders can be selected per run.")
                return
            for folder in folders:
                self.add_folder(folder)
        elif video_files:
            self.add_files(video_files)
        else:
            messagebox.showwarning("Warning", "No valid video files or folders found.")
    
    def parse_drop_data(self, data):
        """Parse drag and drop data"""
        # Handle Windows file paths with spaces
        files = []
        current = ""
        in_braces = False
        
        for char in data:
            if char == '{':
                in_braces = True
                current = ""
            elif char == '}':
                in_braces = False
                if current:
                    files.append(current)
                current = ""
            elif char == ' ' and not in_braces:
                if current:
                    files.append(current)
                current = ""
            else:
                current += char
        
        if current:
            files.append(current)
        
        return [f.strip() for f in files if f.strip()]
    
    def is_video_file(self, filepath):
        """Check if file is a video"""
        video_exts = {'.mp4', '.mkv', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.ts', '.m2ts'}
        return Path(filepath).suffix.lower() in video_exts
    
    def add_files(self, files):
        """Add video files to the list"""
        video_files = [f for f in files if self.is_video_file(f)]
        
        if not video_files:
            messagebox.showwarning("Warning", "No valid video files selected.")
            return
        
        # If video_files is currently folders, clear first
        if self.video_files and any(os.path.isdir(vf) for vf in self.video_files):
            self.video_files = []
        
        # Add new files, avoiding duplicates
        for video_file in video_files:
            if video_file not in self.video_files:
                self.video_files.append(video_file)
        
        # Check total count
        if len(self.video_files) > 50:
            messagebox.showerror("Error", f"Cannot add files. Total would exceed 50 files limit.\nCurrent: {len(self.video_files) - len(video_files)}, Adding: {len(video_files)}")
            # Remove the files we just tried to add
            for video_file in video_files:
                if video_file in self.video_files:
                    self.video_files.remove(video_file)
            return
        
        self.display_files()
    
    def add_folder(self, folder):
        """Add a folder"""
        if not os.path.isdir(folder):
            messagebox.showerror("Error", "Invalid folder path.")
            return
        
        # If video_files currently has individual files, clear them first (no mixing)
        if self.video_files and not any(os.path.isdir(vf) for vf in self.video_files):
            self.video_files = []
        
        # Don't add duplicates
        if folder in self.video_files:
            self.display_files()
            return
        
        # Cap at 5 folders
        current_folders = [vf for vf in self.video_files if os.path.isdir(vf)]
        if len(current_folders) >= 5:
            messagebox.showerror("Error", "Maximum 5 folders allowed per run.")
            return
        
        # Count videos in folder for display
        video_exts = {'.mp4', '.mkv', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.ts', '.m2ts'}
        count = 0
        if self.include_subfolders.get():
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in video_exts:
                        count += 1
        else:
            for f in os.listdir(folder):
                full = os.path.join(folder, f)
                if os.path.isfile(full) and os.path.splitext(f)[1].lower() in video_exts:
                    count += 1
        if count == 0:
            messagebox.showwarning("Warning", "No video files found in the selected folder.")
            return
        
        # Accumulate per-folder video count
        if not hasattr(self, '_folder_video_counts'):
            self._folder_video_counts = {}
        self._folder_video_counts[folder] = count
        self._folder_video_count = sum(self._folder_video_counts.values())
        
        self.video_files.append(folder)
        self.display_files()
    
    def display_files(self):
        """Display selected files/folders as cards"""
        print(f"[DEBUG display_files] called with {len(self.video_files)} files", flush=True)
        
        # Clear existing cards
        for card in self.video_cards:
            card.destroy()
        self.video_cards.clear()
        
        if not self.video_files:
            print("[DEBUG display_files] no files -> showing drop_zone", flush=True)
            self.drop_zone.grid()
            self.file_container.grid_remove()
            self.subfolder_container.grid()
            self.start_button.configure(state="disabled")
            self.clear_list_btn.configure(state="disabled")
            self.update_file_count()
            return
        
        # Hide drop zone, show file list
        self.drop_zone.grid_remove()
        self.file_container.grid()
        print(f"[DEBUG display_files] file_container.grid() done, winfo_exists={self.file_container.winfo_exists()}", flush=True)
        self.file_container.update_idletasks()
        print(f"[DEBUG display_files] file_container after update: width={self.file_container.winfo_width()}, "
              f"height={self.file_container.winfo_height()}, reqwidth={self.file_container.winfo_reqwidth()}, "
              f"reqheight={self.file_container.winfo_reqheight()}", flush=True)
        
        # Create cards
        is_folder_mode = self.video_files and os.path.isdir(self.video_files[0])
        for filepath in self.video_files:
            try:
                initial_status = None
                if is_folder_mode:
                    folder_name = os.path.basename(filepath)
                    if hasattr(self, '_folder_video_counts') and filepath in self._folder_video_counts:
                        vcount = self._folder_video_counts[filepath]
                        initial_status = f"📁 {folder_name} — {vcount} video{'s' if vcount != 1 else ''} found"
                    else:
                        initial_status = f"📁 {folder_name}"
                    card = VideoCard(self.file_container, filepath, on_remove=self.remove_card,
                                    icon_getter=self._get_file_icon, initial_status=initial_status)
                else:
                    card = VideoCard(self.file_container, filepath, on_remove=self.remove_card,
                                    icon_getter=self._get_file_icon)
                card.pack(fill="x", pady=2)
                self.video_cards.append(card)
                print(f"[DEBUG display_files] card created: {os.path.basename(filepath)}", flush=True)
            except Exception as e:
                print(f"[DEBUG display_files] ERROR creating card: {e}", flush=True)
                import traceback; traceback.print_exc()
        
        print(f"[DEBUG display_files] total cards: {len(self.video_cards)}", flush=True)
        
        # Force geometry update
        self.file_container.update_idletasks()
        self.update_idletasks()
        
        for i, card in enumerate(self.video_cards):
            print(f"[DEBUG display_files] card[{i}]: winfo_exists={card.winfo_exists()}, "
                  f"width={card.winfo_width()}, height={card.winfo_height()}, "
                  f"visible={card.winfo_viewable()}", flush=True)
        print(f"[DEBUG display_files] file_container children: {len(self.file_container.winfo_children())}", flush=True)
        
        # Show/hide subfolder checkbox based on selection type
        if is_folder_mode:
            self.subfolder_container.grid()
        else:
            self.subfolder_container.grid_remove()
        
        # Update UI
        self.update_file_count()
        self.start_button.configure(state="normal")
        self.clear_list_btn.configure(state="normal")
    
    def remove_card(self, card):
        """Remove a file card"""
        if self.processing:
            messagebox.showwarning("Warning", "Cannot remove files while processing.")
            return
        
        self.video_cards.remove(card)
        self.video_files.remove(card.filepath)
        card.destroy()
        
        # Clean up per-folder count if applicable
        if hasattr(self, '_folder_video_counts') and card.filepath in self._folder_video_counts:
            del self._folder_video_counts[card.filepath]
            self._folder_video_count = sum(self._folder_video_counts.values()) if self._folder_video_counts else 0
        
        if not self.video_cards:
            self._folder_video_count = 0
            self.drop_zone.grid()
            self.file_container.grid_remove()
            self.subfolder_container.grid()
            self.start_button.configure(state="disabled")
            self.clear_list_btn.configure(state="disabled")
        
        self.update_file_count()
    
    def clear_file_list(self):
        """Clear all files from the list"""
        if self.processing:
            messagebox.showwarning("Warning", "Cannot clear files while processing.")
            return
        
        if not self.video_files:
            return
        
        self.video_files.clear()
        for card in self.video_cards:
            card.destroy()
        self.video_cards.clear()
        
        self._folder_video_count = 0
        if hasattr(self, '_folder_video_counts'):
            self._folder_video_counts.clear()
        self.drop_zone.grid()
        self.file_container.grid_remove()
        self.subfolder_container.grid()
        self.start_button.configure(state="disabled")
        self.clear_list_btn.configure(state="disabled")
        self.update_file_count()
    
    def update_file_count(self):
        """Update file count display"""
        if not self.video_files:
            self.files_label.configure(text=f"📊 Files: 0/50 | Folders: 0/5")
            return
        is_folder_mode = os.path.isdir(self.video_files[0])
        if is_folder_mode:
            self.files_label.configure(text=f"📊 Folders: {len(self.video_files)}/5")
        else:
            self.files_label.configure(text=f"📊 Files: {len(self.video_files)}/50")
    
    def update_daily_stats(self):
        """Update daily download statistics"""
        downloads_today = 0
        defective_streak = 0
        
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    for line in f:
                        if line.startswith('DOWNLOADS_TODAY='):
                            downloads_today = int(line.split('=')[1].strip())
                        elif line.startswith('DEFECTIVE_STREAK='):
                            defective_streak = int(line.split('=')[1].strip())
            except:
                pass
        
        if not self.winfo_exists():
            return
        self.downloads_label.configure(text=f"⬇ Today: {downloads_today}/1000")
        self.streak_label.configure(text=f"🔹 Streak: {defective_streak}/3")
        
        # Schedule next update
        self._stats_job = self.after(5000, self.update_daily_stats)
    
    def _is_stale_lock(self):
        """Check if the lock directory is stale - no batch process is actually running"""
        if not os.path.exists(self.lock_dir):
            return True  # no lock at all, trivially "stale"

        # 1) Check our own subprocess first (fast path)
        if hasattr(self, 'process') and self.process and self.process.poll() is None:
            return False  # our own batch process is still running

        # 2) Check lock directory age — if very new it's likely active
        try:
            lock_age = time.time() - os.path.getmtime(self.lock_dir)
            if lock_age < 5:  # < 5 seconds old, almost certainly active
                return False
            if lock_age > 600:  # > 10 minutes, almost certainly stale
                return True
        except OSError:
            pass

        # 3) Check PID file in lock directory (most reliable)
        pid_file = os.path.join(self.lock_dir, 'pid.txt')
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    lock_pid = int(f.read().strip())
                if psutil.pid_exists(lock_pid):
                    try:
                        proc = psutil.Process(lock_pid)
                        cmdline = ' '.join(proc.cmdline()).lower()
                        if 'cmd.exe' in proc.name().lower() or 'addsub-multi' in cmdline:
                            return False  # lock PID is alive and appears to be the batch
                        # PID exists but command line doesn't match — could be PID reuse
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception:
                pass

        # 4) Broad search for any cmd.exe running the batch file
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = (proc.info['name'] or '').lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                if 'addsub-multi-6.0.bat' in cmdline.replace('"', '').replace("'", ''):
                    if name in ('cmd.exe', 'python.exe', 'pythonw.exe'):
                        return False  # batch process is genuinely running
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return True  # lock exists but no matching batch process found

    def _release_lock(self):
        """Remove the lock directory and any stale queue tickets"""
        try:
            if os.path.exists(self.lock_dir):
                shutil.rmtree(self.lock_dir, ignore_errors=True)
        except Exception:
            pass

    def _get_file_icon(self, ext):
        """Extract Windows system icon for a file extension (cached)."""
        ext = ext.lower()
        if ext in self.icon_cache:
            return self.icon_cache[ext]
        hicon = None
        hdc = None
        hdc_mem = None
        hbmp = None
        try:
            from win32comext.shell import shell, shellcon
            flags = shellcon.SHGFI_SMALLICON | shellcon.SHGFI_ICON | shellcon.SHGFI_USEFILEATTRIBUTES
            _, info = shell.SHGetFileInfo(
                '.' + ext if ext else '.txt',
                win32con.FILE_ATTRIBUTE_NORMAL,
                flags
            )
            hicon = info[0]
            if hicon:
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, 16, 16)
                hdc_mem = hdc.CreateCompatibleDC()
                hdc_mem.SelectObject(hbmp)
                win32gui.DrawIconEx(hdc_mem.GetHandleOutput(), 0, 0, hicon, 16, 16, 0, None, 3)
                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                       bmpstr, 'raw', 'BGRA', 0, 1)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(16, 16))
                self.icon_cache[ext] = ctk_img
                return ctk_img
        except Exception:
            pass
        finally:
            if hicon:
                win32gui.DestroyIcon(hicon)
            if hdc_mem:
                try:
                    hdc_mem.DeleteDC()
                except Exception:
                    pass
            if hbmp:
                try:
                    win32gui.DeleteObject(hbmp.GetHandle())
                except Exception:
                    pass
            if hdc:
                try:
                    win32gui.ReleaseDC(0, hdc.GetHandleOutput())
                except Exception:
                    pass
        self.icon_cache[ext] = None
        return None

    def _refresh_activity_panel(self):
        """Poll the run temp folder and update the activity panel."""
        if not self.activity_folder:
            self._activity_job = self.after(3000, self._refresh_activity_panel)
            return
        if not os.path.isdir(self.activity_folder):
            self._stop_activity_poll()
            return
        try:
            entries = []
            for name in os.listdir(self.activity_folder):
                fp = os.path.join(self.activity_folder, name)
                if os.path.isfile(fp):
                    st = os.stat(fp)
                    entries.append((name, st.st_size, datetime.fromtimestamp(st.st_mtime)))
        except Exception:
            entries = []  # transient error — treat as empty, poll will retry
        _vid_exts = {'mp4','mkv','avi','m4v','mov','wmv','flv','webm','mpg','mpeg','ts','m2ts','mts'}
        _sub_exts = {'srt','ass','ssa','sub','idx','vtt','sup','pgs'}
        def _priority(name):
            ext = os.path.splitext(name)[1].lstrip('.').lower()
            if ext in _vid_exts:
                return (0, name.lower())
            if ext in _sub_exts:
                return (1, name.lower())
            return (2, name.lower())
        entries.sort(key=lambda e: _priority(e[0]))
        # Only rebuild UI when file list actually changed (name+size fingerprint)
        snap = tuple(n for n, _, _ in entries)
        if snap == self._activity_snapshot:
            self._activity_job = self.after(3000, self._refresh_activity_panel)
            return
        self._activity_snapshot = snap
        for w in self.activity_frame.winfo_children():
            w.destroy()
        if not entries:
            ctk.CTkLabel(self.activity_frame, text="Waiting for files...",
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=("gray50", "gray60")).pack(fill="x")
        else:
            for name, size, mtime in entries:
                row = ctk.CTkFrame(self.activity_frame, fg_color="transparent")
                row.pack(fill="x", padx=2, pady=0)
                ext = os.path.splitext(name)[1].lstrip('.')
                icon = self._get_file_icon(ext)
                if icon:
                    icon_lbl = ctk.CTkLabel(row, image=icon, text="", width=20)
                else:
                    icon_lbl = ctk.CTkLabel(row, text="📄", width=20, font=ctk.CTkFont(size=12))
                icon_lbl.pack(side="left")
                if size < 1024:
                    sz = f"{size} B"
                elif size < 1024 * 1024:
                    sz = f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    sz = f"{size / (1024 * 1024):.1f} MB"
                else:
                    sz = f"{size / (1024 * 1024 * 1024):.1f} GB"
                time_str = mtime.strftime("%H:%M")
                info = f"{name}    {sz}    {time_str}"
                ctk.CTkLabel(row, text=info, font=ctk.CTkFont(family="Segoe UI", size=11),
                             anchor="w").pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._activity_job = self.after(3000, self._refresh_activity_panel)

    def _start_activity_poll(self):
        """Find a *new* Run_* folder created after this session started and begin polling."""
        if not self.processing:
            return
        try:
            runs = [d for d in os.listdir(self.temp_dir)
                    if d.startswith('Run_') and os.path.isdir(os.path.join(self.temp_dir, d))]
            if runs:
                # Only consider folders NOT in the pre-existing set (created by THIS batch run)
                fresh = [d for d in runs if d not in self._known_run_folders]
                if fresh:
                    # Pick the newest among fresh folders
                    fresh.sort(key=lambda d: os.path.getctime(os.path.join(self.temp_dir, d)), reverse=True)
                    self.activity_folder = os.path.join(self.temp_dir, fresh[0])
                    self.activity_header.configure(text=f"📂 Session — {fresh[0]}")
                    self._refresh_activity_panel()
                    self._activity_job = self.after(3000, self._refresh_activity_panel)
                    return
        except Exception as e:
            print(f"Activity poll start error: {e}")
        # Retry in 2 seconds if batch hasn't created its Run_* folder yet
        if self.processing:
            self._activity_job = self.after(2000, self._start_activity_poll)

    def _stop_activity_poll(self):
        """Stop polling and reset the panel."""
        if self._activity_job is not None:
            self.after_cancel(self._activity_job)
            self._activity_job = None
        self.activity_folder = None
        self._activity_snapshot = None
        for w in self.activity_frame.winfo_children():
            w.destroy()
        self.activity_placeholder = ctk.CTkLabel(
            self.activity_frame, text="No active session",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("gray50", "gray60")
        )
        self.activity_placeholder.pack(fill="x")
        self.activity_header.configure(text="📂 Session Activity")

    def start_processing(self):
        """Start processing files"""
        print("DEBUG: start_processing called")
        print(f"DEBUG: video_files = {self.video_files}")
        print(f"DEBUG: processing = {self.processing}")
        
        if not self.video_files:
            print("DEBUG: No files selected, showing warning")
            messagebox.showwarning("Warning", "No files selected.")
            return
        
        if self.processing:
            print("DEBUG: Already processing, returning")
            return
        
        print("DEBUG: Checking batch file lock directory...")
        if os.path.exists(self.lock_dir):
            if self._is_stale_lock():
                print("DEBUG: Lock dir is stale (no batch running), cleaning up")
                self._release_lock()
                self.run_batch_process()
            else:
                print(f"DEBUG: Lock dir exists, another instance is processing")
                queue_ticket = self.create_queue_ticket()
                position = self.get_queue_position(queue_ticket)
                waiting_dialog = WaitingDialog(self, position, queue_ticket)
                self._poll_batch_lock(waiting_dialog, queue_ticket)
        else:
            print("DEBUG: No lock, starting batch process immediately")
            self.run_batch_process()
    
    def create_queue_ticket(self):
        """Create a queue ticket"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        run_id = os.urandom(6).hex()
        ticket_path = os.path.join(self.queue_dir, f"{timestamp}_{run_id}.ticket")
        
        try:
            with open(ticket_path, 'w') as f:
                f.write(run_id)
        except:
            pass
        
        return ticket_path
    
    def get_queue_position(self, ticket_path):
        """Get position in queue"""
        try:
            tickets = sorted([f for f in os.listdir(self.queue_dir) if f.endswith('.ticket')])
            ticket_name = os.path.basename(ticket_path)
            if ticket_name in tickets:
                return tickets.index(ticket_name) + 1
        except:
            pass
        return 1
    
    def _poll_batch_lock(self, waiting_dialog, queue_ticket):
        """Poll for the batch file's lock directory to disappear"""
        def poll_thread():
            while not waiting_dialog.cancelled:
                if not os.path.exists(self.lock_dir):
                    self.after(0, waiting_dialog.destroy)
                    try:
                        if os.path.exists(queue_ticket):
                            os.remove(queue_ticket)
                    except:
                        pass
                    self.after(100, self.run_batch_process)
                    break
                position = self.get_queue_position(queue_ticket)
                self.after(0, lambda p=position: waiting_dialog.update_position(p))
                time.sleep(5)
        
        threading.Thread(target=poll_thread, daemon=True).start()
    
    def run_batch_process(self):
        """Run the batch file process"""
        print("DEBUG: run_batch_process called")
        print(f"DEBUG: batch_file = {self.batch_file}")
        print(f"DEBUG: video_files = {self.video_files}")
        
        self.processing = True
        self._paused = False
        self._cancelled = False
        self.start_button.configure(state="disabled", text="⏸ Processing...", fg_color="#505050")
        self.pause_button.configure(state="normal")
        self.cancel_button.configure(text="❌ Cancel", state="normal")
        self.clear_list_btn.configure(state="disabled")
        
        # Clear console and global status
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.configure(state="disabled")
        self.write_console("=== Processing Started ===")
        self.global_status_label.configure(text="")
        
        # Update cards to processing state (keep completed/error/skipped intact)
        for card in self.video_cards:
            if card.status not in ("success", "error", "skip"):
                card.update_status("Queued for processing", "waiting")
            card.set_processing_state(True)
        
        # Prepare environment variables for batch file
        env = os.environ.copy()
        
        # Set GUI mode to skip pause at the end
        env['GUI_MODE'] = '1'
        
        # Pass subfolder setting
        if self.include_subfolders.get():
            env['SUBFOLDER_CHOICE'] = 'Y'
            env['INCLUDE_SUBFOLDERS'] = '1'
        else:
            env['SUBFOLDER_CHOICE'] = 'N'
        
        # Pass reprocess policy
        policy = self.reprocess_policy.get()
        if policy == "skip":
            env['REPROCESS_POLICY'] = 'SKIP_ALL'
            env['SESSION_REPROCESS_POLICY'] = 'SKIP_ALL'
        elif policy == "reprocess":
            env['REPROCESS_POLICY'] = 'REPROCESS_ALL'
            env['SESSION_REPROCESS_POLICY'] = 'REPROCESS_ALL'
        else:  # "ask" — pre-scan with ffprobe to find files already processed by this tool
            # Detect using the same criteria as the batch: ffprobe metadata tag or ≥4 subtitle streams
            ffprobe_exe = os.path.join(self.script_dir, "ffprobe.exe")
            processed_files = []

            # Expand any folder paths into individual video files for the pre-scan
            video_exts = {'.mp4', '.mkv', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.ts', '.m2ts'}
            scan_targets = []
            for vf in self.video_files:
                if os.path.isdir(vf):
                    for root, dirs, files in os.walk(vf):
                        for f in files:
                            if Path(f).suffix.lower() in video_exts:
                                scan_targets.append(os.path.join(root, f))
                else:
                    scan_targets.append(vf)

            print(f"DEBUG: Pre-scanning {len(scan_targets)} files for processed detection...")
            self.write_console(f"Scanning {len(scan_targets)} file(s) for previously processed videos...")

            for vf in scan_targets:
                try:
                    result = subprocess.run(
                        [ffprobe_exe, "-v", "error", "-select_streams", "s",
                         "-show_entries", "format_tags:stream_tags=title", "-of", "json", vf],
                        capture_output=True, text=True, timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode != 0 or not result.stdout.strip():
                        print(f"DEBUG: ffprobe skip for {os.path.basename(vf)} (rc={result.returncode})")
                        continue
                    data = json.loads(result.stdout)
                    # Criterion A: subtitle_batch_processed=1 in format tags
                    tags = data.get("format", {}).get("tags", {})
                    found = False
                    for key, val in tags.items():
                        if key.lower() == "subtitle_batch_processed" and str(val) == "1":
                            processed_files.append(os.path.basename(vf))
                            found = True
                            print(f"DEBUG: Found processed (tag): {os.path.basename(vf)}")
                            break
                    if not found:
                        # Criterion B: ≥4 subtitle streams
                        streams = data.get("streams", [])
                        if len(streams) >= 4:
                            processed_files.append(os.path.basename(vf))
                            print(f"DEBUG: Found processed (streams={len(streams)}): {os.path.basename(vf)}")
                except Exception as e:
                    print(f"DEBUG: ffprobe exception for {os.path.basename(vf)}: {e}")

            print(f"DEBUG: Pre-scan complete. {len(processed_files)} processed file(s) detected.")

            if not processed_files:
                # No files match the tool's criteria — skip dialog, proceed normally
                env['REPROCESS_POLICY'] = ''
                env['SESSION_REPROCESS_POLICY'] = ''
            else:
                ask_dialog = ctk.CTkToplevel(self)
                ask_dialog.title("Ask Me to Decide — Re-process Policy")
                ask_dialog.resizable(False, False)
                ask_dialog.transient(self)
                ask_dialog.grab_set()
                ask_dialog.lift()
                ask_dialog.focus_force()
                
                ask_dialog.grid_rowconfigure(0, weight=0)   # header
                ask_dialog.grid_rowconfigure(1, weight=0)   # sub-header
                ask_dialog.grid_rowconfigure(2, weight=0)   # count label
                ask_dialog.grid_rowconfigure(3, weight=1)   # scrollable list
                ask_dialog.grid_rowconfigure(4, weight=0)   # buttons
                ask_dialog.grid_columnconfigure(0, weight=1)
                
                ctk.CTkLabel(ask_dialog, text="🔄 Re-process Policy",
                            font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=(20, 5), padx=20, sticky="ew")
                
                ctk.CTkLabel(ask_dialog,
                            text="These files were already processed with AddSub-Multi.\nChoose how to handle them:",
                            font=ctk.CTkFont(size=12),
                            wraplength=450).grid(row=1, column=0, pady=(0, 10), padx=20, sticky="ew")
                
                ctk.CTkLabel(ask_dialog,
                            text=f"📋 {len(processed_files)} previously processed file(s) found",
                            font=ctk.CTkFont(size=11),
                            text_color=("gray50", "gray60")).grid(row=2, column=0, pady=(0, 5), padx=20, sticky="ew")
                
                list_frame = ctk.CTkScrollableFrame(ask_dialog, width=400)
                list_frame.grid(row=3, column=0, padx=20, pady=(0, 5), sticky="nsew")
                for f in processed_files:
                    ctk.CTkLabel(list_frame, text=f"  • {f}",
                                font=ctk.CTkFont(size=10), anchor="w").pack(fill="x", pady=1)
                
                result = {"value": None}
                def set_answer(val):
                    result["value"] = val
                    ask_dialog.destroy()
                
                btn_frame = ctk.CTkFrame(ask_dialog, fg_color="transparent")
                btn_frame.grid(row=4, column=0, pady=(15, 15), padx=20, sticky="ew")
                
                ctk.CTkButton(btn_frame, text="🔄 Process All",
                             command=lambda: set_answer("reprocess"),
                             width=180, height=36,
                             font=ctk.CTkFont(size=13),
                             fg_color="#2E7D32", hover_color="#388E3C").pack(side="left", padx=6)
                
                ctk.CTkButton(btn_frame, text="🗑️ Do not Process, Remove",
                             command=lambda: set_answer("skip"),
                             width=180, height=36,
                             font=ctk.CTkFont(size=13),
                             fg_color="#6D4C41", hover_color="#795548").pack(side="left", padx=6)
                
                ctk.CTkButton(btn_frame, text="❌ Cancel",
                             command=lambda: set_answer("cancel"),
                             width=80, height=36,
                             font=ctk.CTkFont(size=13),
                             fg_color="#757575", hover_color="#9E9E9E").pack(side="left", padx=6)
                
                # Handle window close (X) same as Cancel
                ask_dialog.protocol("WM_DELETE_WINDOW", lambda: set_answer("cancel"))
                
                ask_dialog.update_idletasks()
                pw, ph = self.winfo_width(), self.winfo_height()
                px, py = self.winfo_x(), self.winfo_y()
                dw = 540
                nfiles = len(processed_files)
                dh = 310 if nfiles <= 3 else min(310 + (nfiles - 3) * 22, 600)
                ask_dialog.geometry(f"{dw}x{dh}+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
                
                self.wait_window(ask_dialog)
                
                if result["value"] == "reprocess":
                    env['REPROCESS_POLICY'] = 'REPROCESS_ALL'
                    env['SESSION_REPROCESS_POLICY'] = 'REPROCESS_ALL'
                elif result["value"] == "skip":
                    # Remove previously processed files from the list, then reset
                    # so the check re-runs when user hits Start again
                    processed_set = set(processed_files)
                    new_videos = [vf for vf in self.video_files
                                  if os.path.basename(vf) not in processed_set]
                    if not new_videos:
                        # All files removed — nothing left to process
                        self.processing = False
                        self.start_button.configure(state="normal", text="▶ Start Processing")
                        self.pause_button.configure(state="disabled")
                        self.cancel_button.configure(text="❌ Close", state="normal")
                        for card in self.video_cards:
                            card.destroy()
                        self.video_cards = []
                        self.video_files = []
                        self.update_file_count()
                        return
                    self.video_files = new_videos
                    # Remove corresponding cards
                    for card in list(self.video_cards):
                        base = os.path.basename(card.filepath) if hasattr(card, 'filepath') else ''
                        if base in processed_set:
                            card.destroy()
                            self.video_cards.remove(card)
                    self.update_file_count()
                    # Reset: don't continue processing — let user hit Start again
                    self.processing = False
                    self.start_button.configure(state="normal", text="▶ Start Processing", fg_color="#00D787")
                    self.pause_button.configure(state="disabled")
                    self.cancel_button.configure(text="❌ Close", state="normal")
                    for card in self.video_cards:
                        card.update_status("", "")
                    self.write_console("Removed previously processed files. Press Start to proceed with remaining files.")
                    return
                else:
                    # Dialog closed (X) or Cancel — cancel run, do nothing until Start is pressed again
                    self.processing = False
                    self.start_button.configure(state="normal", text="▶ Start Processing", fg_color="#00D787")
                    self.pause_button.configure(state="disabled")
                    self.cancel_button.configure(text="❌ Close", state="normal")
                    for card in self.video_cards:
                        card.update_status("", "")
                    return
        
        print(f"DEBUG: SUBFOLDER_CHOICE = {env.get('SUBFOLDER_CHOICE')}")
        print(f"DEBUG: REPROCESS_POLICY = {env.get('REPROCESS_POLICY')}")
        
        # Write file paths to temp file to avoid Windows 8191-char command line limit
        gui_list_path = os.path.join(self.state_root, 'gui_video_list.txt')
        env['FILE_LIST_READY'] = '1'
        try:
            with open(gui_list_path, 'w', encoding='utf-8') as f:
                for vf in self.video_files:
                    f.write(vf + '\n')
            print(f"DEBUG: Wrote {len(self.video_files)} paths to {gui_list_path}")
        except Exception as e:
            print(f"ERROR: Failed to write GUI file list: {e}")
            self.processing = False
            self.start_button.configure(state="normal", text="▶ Start Processing", fg_color="#00D787")
            self.pause_button.configure(state="disabled")
            self.cancel_button.configure(text="❌ Close", state="normal")
            messagebox.showerror("Error", f"Failed to prepare file list: {e}")
            return
        
        # Launch batch with NO file arguments — it reads from the temp file via FILE_LIST_READY
        full_command = f'"{self.batch_file}"'
        
        print(f"DEBUG: Full command string: {full_command}")
        print(f"DEBUG: Working directory: {self.script_dir}")
        
        def process_thread():
            try:
                print("DEBUG: Starting subprocess.Popen...")
                # Run process with shell=True to handle complex quoting
                self.process = subprocess.Popen(
                    full_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=self.script_dir,
                    env=env,
                    shell=True
                )
                print(f"DEBUG: Process started with PID: {self.process.pid}")
                
                # Show initial status with first filename until script provides real status
                first_file = os.path.basename(self.video_files[0]) if self.video_files else "files"
                self.after(0, lambda: self._update_global_status(
                    f"Processing: {first_file}", "processing"))
                
                # Collect all output for debugging
                all_output = []
                
                # Read output line by line
                print("DEBUG: Starting to read output...")
                current_file_index = 0
                for line in self.process.stdout:
                    line = line.strip()
                    if line:
                        # Log everything for debugging
                        print(f"BATCH OUTPUT: {line}")
                        all_output.append(line)
                        
                        # Detect video switch to track correct card index
                        # Strip ANSI codes first — batch output has embedded color escapes
                        clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
                        video_match = re.search(r'Processing Video:\s*(.+)$', clean)
                        if video_match:
                            video_basename = video_match.group(1).strip()
                            prev_idx = current_file_index
                            new_idx = None
                            for i, card in enumerate(self.video_cards):
                                if os.path.basename(card.filepath) == video_basename:
                                    new_idx = i
                                    break
                            if new_idx is not None:
                                # Clean up previous card if left in active state (spinner running)
                                if prev_idx != new_idx and prev_idx < len(self.video_cards):
                                    old_card = self.video_cards[prev_idx]
                                    if old_card.status not in ("success", "error", "skip"):
                                        self.after(0, lambda c=old_card: c.update_status("Ready", "waiting"))
                                current_file_index = new_idx
                        
                        # Parse output and update UI
                        self.parse_output_line(line, current_file_index)
                        
                        # Check for completion message
                        if "All finished" in line:
                            print("DEBUG: Detected 'All finished' message")
                
                print("DEBUG: Output reading loop completed, waiting for process to exit...")
                self.process.wait()
                
                # Check return code
                print(f"DEBUG: Process finished with return code: {self.process.returncode}")
                
                # If user cancelled, skip all dialogs - cancel_processing already handled UI
                if self._cancelled:
                    return
                
                # If process failed or produced no output, show what happened
                if self.process.returncode != 0 or len(all_output) == 0:
                    error_msg = f"Batch file exited with code {self.process.returncode}\n\n"
                    if all_output:
                        error_msg += "Last 20 lines of output:\n" + "\n".join(all_output[-20:])
                    else:
                        error_msg += "No output was captured from the batch file."
                    
                    def show_error(message):
                        messagebox.showerror("Processing Error", message)
                    
                    self.after(0, lambda: show_error(error_msg))
                
                # Mark all as completed
                self.after(0, self.processing_complete)
                
            except Exception as e:
                # If user cancelled, skip error dialog - cancel_processing already handled UI
                if self._cancelled:
                    return
                error_traceback = f"Processing failed:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                print(f"ERROR: {error_traceback}")
                self.after(0, lambda: messagebox.showerror("Error", error_traceback))
                self.after(0, self.processing_complete)
        
        # Snapshot existing Run_* folders NOW (before batch creates a new one)
        # so the poll ignores stale folders from previous runs.
        self._known_run_folders = {d for d in os.listdir(self.temp_dir)
                                   if d.startswith('Run_') and os.path.isdir(os.path.join(self.temp_dir, d))}
        # Cancel any leftover poll from a previous session and reset folder discovery
        if self._activity_job is not None:
            self.after_cancel(self._activity_job)
            self._activity_job = None
        self.activity_folder = None
        self._activity_snapshot = None

        threading.Thread(target=process_thread, daemon=True).start()
        self._start_activity_poll()
    
    def write_console(self, text, parse_colors=False):
        """Write text to console panel with optional color parsing"""
        def update():
            self.console_text.configure(state="normal")
            
            if parse_colors:
                # Parse ANSI codes and apply colors
                segments = self.parse_ansi_text(text)
                text_widget = self.console_text._textbox
                
                for segment_text, tag in segments:
                    if tag:
                        text_widget.insert("end", segment_text, tag)
                    else:
                        text_widget.insert("end", segment_text)
                text_widget.insert("end", "\n")
            else:
                # Plain text insert
                self.console_text.insert("end", text + "\n")
            
            self.console_text.see("end")
            self.console_text.configure(state="disabled")
        self.after(0, update)
    
    # Percentage mapping for [Status] messages based on keywords
    _STATUS_PCT = [
        ("search", 15), ("retry", 25), ("download", 30),
        ("sync", 50), ("validate", 55), ("legacy codec", 55),
        ("convert", 60), ("muxing", 75), ("created", 90),
        ("applying metadata", 95),
    ]
    
    _GLOBAL_STATUS_ICONS = {
        "waiting": "⏱️", "success": "✅", "error": "❌", "skip": "⏭️",
        "processing": "🔄", "downloading": "⬇️", "embedding": "📦",
    }
    
    def _update_global_status(self, text, status_type, percentage=None):
        """Update the global status bar with full (unshortened) text and percentage"""
        if not self.global_status_label.winfo_exists():
            return
        icon = self._GLOBAL_STATUS_ICONS.get(status_type, "ℹ️")
        if percentage is not None:
            display = f"{icon}  {text}  ({percentage}%)"
        else:
            display = f"{icon}  {text}"
        self.global_status_label.configure(text=display)
    
    def parse_output_line(self, line, current_index):
        """Parse batch output and update UI"""
        # Write to console with colors preserved
        self.write_console(line, parse_colors=True)
        
        # Remove ANSI color codes for status detection
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        
        idx = current_index  # capture by value in lambdas below
        card = self.video_cards[idx] if idx < len(self.video_cards) else None
        
        # ── [Progress] XX% Complete (from conversion step) ──
        progress_match = re.search(r'\[Progress\]\s*(\d+)%\s*Complete', clean_line)
        if progress_match and card:
            pct = int(progress_match.group(1))
            self.after(0, lambda c=card, p=pct: c.update_status(
                f"Converting...", "processing", p
            ))
            self._update_global_status("Converting video...", "processing", pct)
            return
        
        # ── [Status] message ──
        status_match = re.match(r'\[Status\]\s+(.+)', clean_line)
        if status_match and card:
            msg = status_match.group(1).strip()
            msg_lower = msg.lower()
            # Determine percentage from keywords; only set "processing"
            # type (spinner) when the message indicates active work.
            # Messages indicating inaction (skip/unchanged/kept/already) should
            # NOT trigger the spinner even if they contain active keywords.
            _INA_KEYWORDS = ("skip", "skipping", "unchanged", "already", "kept")
            inaction = any(k in msg_lower for k in _INA_KEYWORDS)
            pct = None
            active = False
            if not inaction:
                for keyword, val in self._STATUS_PCT:
                    if keyword in msg_lower:
                        pct = val
                        active = True
                        break
            stype = "processing" if active else card.status
            self.after(0, lambda c=card, m=msg, p=pct, t=stype: c.update_status(m, t, p))
            if active:
                self._update_global_status(msg, stype, pct)
            return
        
        # ── [Result] Usable subtitle tracks ready for muxing: X,Y,Z ──
        result_match = re.search(r'\[Result\]\s*Usable subtitle tracks ready for muxing:\s*(.+)', clean_line)
        if result_match and card:
            indices = result_match.group(1).strip()
            count = len([x for x in indices.split(',') if x.strip()]) if indices else 0
            card.subtitle_count = count  # set synchronously so [Success] can read it
            self.after(0, lambda c=card, n=count: c.update_status(
                f"Muxing {n} subtitle(s)...", "embedding", 75, subtitle_count=n
            ))
            self._update_global_status(f"Muxing {count} subtitle(s) into MKV...", "embedding", 75)
            return
        
        # ── [Success] ──
        if '[Success]' in clean_line and card:
            n = card.subtitle_count
            msg = f"Completed"
            if n > 0:
                msg += f" — {n} Subtitle{'s' if n != 1 else ''} Added"
            print(f"DEBUG [Success]: subtitle_count={n}, msg={msg!r}, card.status={card.status}")
            self.after(0, lambda c=card, m=msg: c.update_status(m, "success", 100))
            self._update_global_status(msg, "success", 100)
            return
        
        # ── [Skip] ──
        if '[Skip]' in clean_line and card:
            self.after(0, lambda c=card: c.update_status("Skipped", "skip"))
            self._update_global_status("Skipped — already processed", "skip")
            return
        
        # ── [Error] ──
        if '[Error]' in clean_line and card:
            self.after(0, lambda c=card: c.update_status("Error occurred", "error"))
            self._update_global_status("Error processing file", "error")
            return
        
        # ── Fallback: legacy output patterns ──
        if card:
            if '[Processing]' in clean_line or '[Process]' in clean_line:
                self.after(0, lambda c=card: c.update_status("Processing video...", "processing", 10))
                self._update_global_status("Processing video...", "processing", 10)
            elif 'Downloading' in clean_line or 'download' in clean_line.lower():
                self.after(0, lambda c=card: c.update_status("Downloading subtitles...", "downloading", 30))
                self._update_global_status("Downloading subtitles...", "downloading", 30)
            elif 'Embedding' in clean_line or 'embed' in clean_line.lower():
                self.after(0, lambda c=card: c.update_status("Embedding subtitles...", "embedding", 70))
                self._update_global_status("Embedding subtitles...", "embedding", 70)
            elif 'All finished' in clean_line:
                self.after(0, lambda c=card: c.update_status("Completed Successfully", "success", 100))
                self._update_global_status("All files processed", "success", 100)
    
    def processing_complete(self):
        """Called when processing is complete"""
        self.processing = False
        self._paused = False
        
        # Stop activity poll
        self._stop_activity_poll()
        
        # Clean up the lock (batch should have done it, but belt and suspenders)
        self._release_lock()
        
        # Stop all remaining spinners and ensure cards reflect final state
        for card in self.video_cards:
            card._stop_spinner()
            # Cards left in active states (processing/downloading/embedding) without
            # an explicit [Success]/[Error] didn't finish properly; mark as error
            if card._status_type in ("processing", "downloading", "embedding"):
                card.update_status("Processing stopped unexpectedly", "error")
        
        # Update UI
        self.start_button.configure(state="normal", text="▶ Start Processing", fg_color="#00D787")
        self.pause_button.configure(state="disabled")
        self.cancel_button.configure(text="❌ Close", state="normal")
        self.clear_list_btn.configure(state="normal")
        self.write_console("\n=== Processing Complete ===")
        self.update_daily_stats()
        
        messagebox.showinfo("Complete", "Processing finished!")
        # File list is preserved so the user can review results; use 🗑 to clear it
    
    def pause_processing(self):
        """Pause or resume the current processing"""
        if not self.process or not self.processing:
            return
        
        try:
            pid = self.process.pid
            do_suspend = not self._paused
            
            snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
            if snapshot and snapshot != INVALID_HANDLE_VALUE:
                te32 = THREADENTRY32()
                te32.dwSize = sizeof(THREADENTRY32)
                suspended_count = 0
                if _kernel32.Thread32First(snapshot, byref(te32)):
                    while True:
                        if te32.th32OwnerProcessID == pid:
                            hThread = _kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, te32.th32ThreadID)
                            if hThread:
                                if do_suspend:
                                    _kernel32.SuspendThread(hThread)
                                    suspended_count += 1
                                else:
                                    _kernel32.ResumeThread(hThread)
                                _kernel32.CloseHandle(hThread)
                        if not _kernel32.Thread32Next(snapshot, byref(te32)):
                            break
                _kernel32.CloseHandle(snapshot)
                
                if do_suspend:
                    self._paused = True
                    self.pause_button.configure(text="▶ Resume")
                    self.write_console("\n--- Processing Paused ---")
                else:
                    self._paused = False
                    self.pause_button.configure(text="⏸ Pause")
                    self.write_console("\n--- Processing Resumed ---")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to pause/resume process: {e}")
    
    def close_or_cancel(self):
        """When processing: cancel. When idle: close the GUI."""
        if self.processing:
            self.cancel_processing()
        else:
            if messagebox.askyesno("Close", "Close AddSub-Multi and terminate the session?"):
                self._release_lock()
                if hasattr(self, '_stats_job'):
                    self.after_cancel(self._stats_job)
                self.destroy()

    def cancel_processing(self):
        """Cancel the current processing"""
        if self.process and self.processing:
            if messagebox.askyesno("Confirm Cancel", "Are you sure you want to cancel processing?"):
                try:
                    self.write_console("\n--- Processing Cancelled by User ---")
                    self._cancelled = True
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    self.process.kill()
                finally:
                    self.processing = False
                    self._paused = False
                    self._stop_activity_poll()
                    self._release_lock()
                    # Reset only unfinished cards to waiting; completed ones keep their status
                    for card in self.video_cards:
                        if card.status not in ("success", "error", "skip"):
                            card.update_status("Queued for processing", "waiting")
                        card.set_processing_state(False)
                    self.start_button.configure(state="normal", text="▶ Start Processing", fg_color="#00D787")
                    self.pause_button.configure(state="disabled", text="⏸ Pause")
                    self.cancel_button.configure(text="❌ Close", state="normal")
                    self.clear_list_btn.configure(state="normal")
                    self.global_status_label.configure(text="")


def main():
    """Main entry point"""
    # Check for CustomTkinter
    try:
        import customtkinter
    except ImportError:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "CustomTkinter is required but not installed.\n\n"
            "Please install it using:\n"
            "pip install customtkinter"
        )
        return
    
    # Check for tkinterdnd2
    try:
        import tkinterdnd2
    except ImportError:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "tkinterdnd2 is required but not installed.\n\n"
            "Please install it using:\n"
            "pip install tkinterdnd2"
        )
        return
    
    app = AddSubGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
