"""Quick import test - diagnostic script for VideoCard import issues."""
import sys, time, traceback

t0 = time.time()
print(f"[{time.time()-t0:.3f}s] Starting imports...", flush=True)

try:
    import customtkinter as ctk
    print(f"[{time.time()-t0:.3f}s] customtkinter {ctk.__version__} OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] customtkinter FAIL: {e}", flush=True)
    traceback.print_exc()

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    print(f"[{time.time()-t0:.3f}s] tkinter OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] tkinter FAIL: {e}", flush=True)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    print(f"[{time.time()-t0:.3f}s] tkinterdnd2 OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] tkinterdnd2 FAIL: {e}", flush=True)

try:
    import json, subprocess, threading, os, shutil, re
    print(f"[{time.time()-t0:.3f}s] stdlib imports OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] stdlib imports FAIL: {e}", flush=True)

try:
    import psutil
    print(f"[{time.time()-t0:.3f}s] psutil OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] psutil FAIL: {e}", flush=True)

try:
    from pathlib import Path
    from datetime import datetime
    import queue as thread_queue
    print(f"[{time.time()-t0:.3f}s] more stdlib OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] more stdlib FAIL: {e}", flush=True)

try:
    import win32api, win32gui, win32con, win32ui
    print(f"[{time.time()-t0:.3f}s] pywin32 OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] pywin32 FAIL: {e}", flush=True)

try:
    from PIL import Image, ImageTk
    print(f"[{time.time()-t0:.3f}s] Pillow OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] Pillow FAIL: {e}", flush=True)

try:
    import ctypes
    from ctypes import wintypes, byref, sizeof, windll
    print(f"[{time.time()-t0:.3f}s] ctypes OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] ctypes FAIL: {e}", flush=True)

print(f"[{time.time()-t0:.3f}s] All imports done!", flush=True)

# Now try module-level code
try:
    ctk.set_appearance_mode("dark")
    print(f"[{time.time()-t0:.3f}s] appearance_mode set", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] appearance_mode FAIL: {e}", flush=True)

try:
    ctk.set_default_color_theme("dark-blue")
    print(f"[{time.time()-t0:.3f}s] color_theme set", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] color_theme FAIL: {e}", flush=True)

# ctypes definitions
try:
    TH32CS_SNAPTHREAD = 0x00000004
    THREAD_SUSPEND_RESUME = 0x0002
    print(f"[{time.time()-t0:.3f}s] constants OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] constants FAIL: {e}", flush=True)

try:
    class THREADENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]
    print(f"[{time.time()-t0:.3f}s] THREADENTRY32 struct OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] THREADENTRY32 struct FAIL: {e}", flush=True)

try:
    _kernel32 = windll.kernel32
    _kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    _kernel32.Thread32First.restype = wintypes.BOOL
    _kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    _kernel32.Thread32Next.restype = wintypes.BOOL
    _kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenThread.restype = wintypes.HANDLE
    _kernel32.SuspendThread.argtypes = [wintypes.HANDLE]
    _kernel32.SuspendThread.restype = wintypes.DWORD
    _kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    _kernel32.ResumeThread.restype = wintypes.DWORD
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    print(f"[{time.time()-t0:.3f}s] kernel32 sigs OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] kernel32 sigs FAIL: {e}", flush=True)

try:
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    print(f"[{time.time()-t0:.3f}s] INVALID_HANDLE_VALUE OK", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] INVALID_HANDLE_VALUE FAIL: {e}", flush=True)

print(f"\n[{time.time()-t0:.3f}s] SUCCESS - all module-level code executed", flush=True)
