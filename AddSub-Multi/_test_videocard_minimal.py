"""Minimal test: does VideoCard create correctly and report valid size?"""
import sys, os, time, ctypes
from ctypes import wintypes

# Need to set up the GUI before importing our module
import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Manually import and exec the module source
import importlib.util
sys.path.insert(0, r'C:\Users\ibrah\SynologyDrive\Programming Projects\Openhands Workspace\AddSub-Multi')
spec = importlib.util.spec_from_file_location(
    'gui', r'C:\Users\ibrah\SynologyDrive\Programming Projects\Openhands Workspace\AddSub-Multi\AddSub-Multi-GUI.py')
gui = importlib.util.module_from_spec(spec)

# We need to stub tkinter since we can't create a display
# Instead, just verify the module-level code loads properly

print("Module spec loaded OK", flush=True)
print("Module object created OK", flush=True)

# The hang happens in exec_module. Let's try to narrow down the issue
# by running the module's code directly
with open(r'C:\Users\ibrah\SynologyDrive\Programming Projects\Openhands Workspace\AddSub-Multi\AddSub-Multi-GUI.py', 'r') as f:
    source = f.read()

print(f"Source: {len(source)} bytes", flush=True)
print(f"Lines: {source.count(chr(10))}", flush=True)

# Check for syntax errors
try:
    compile(source, 'AddSub-Multi-GUI.py', 'exec')
    print("Syntax check: OK", flush=True)
except SyntaxError as e:
    print(f"Syntax check: FAILED - {e}", flush=True)
