"""Core test: import the GUI module and check if VideoCard is usable."""
import sys, os, time

t0 = time.time()
os.chdir(r'C:\Users\ibrah\SynologyDrive\Programming Projects\Openhands Workspace\AddSub-Multi')
sys.path.insert(0, os.getcwd())

print(f"[{time.time()-t0:.3f}s] Setup done", flush=True)

import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
print(f"[{time.time()-t0:.3f}s] ctk setup done", flush=True)

# Now try importing the GUI module
import importlib.util
spec = importlib.util.spec_from_file_location('AddSub_Multi_GUI', 'AddSub-Multi-GUI.py')
print(f"[{time.time()-t0:.3f}s] spec created", flush=True)

module = importlib.util.module_from_spec(spec)
print(f"[{time.time()-t0:.3f}s] module created", flush=True)

print(f"[{time.time()-t0:.3f}s] Running exec_module...", flush=True)
try:
    spec.loader.exec_module(module)
    print(f"[{time.time()-t0:.3f}s] exec_module DONE!", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:.3f}s] exec_module FAILED: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
