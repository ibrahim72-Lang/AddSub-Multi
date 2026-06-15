"""Quick smoke test for activity panel components."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Test 1: Temp dir and Run_* folders ---
temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Temp')
print(f'Temp dir exists: {os.path.isdir(temp_dir)}')
runs = [d for d in os.listdir(temp_dir) if d.startswith('Run_') and os.path.isdir(os.path.join(temp_dir, d))]
print(f'Run folders found: {len(runs)}')
if runs:
    runs.sort(key=lambda d: os.path.getctime(os.path.join(temp_dir, d)), reverse=True)
    newest = runs[0]
    print(f'Newest: {newest}')
    newest_path = os.path.join(temp_dir, newest)
    files = [f for f in os.listdir(newest_path) if os.path.isfile(os.path.join(newest_path, f))]
    print(f'Files in newest: {len(files)}')
    for f in files[:5]:
        fp = os.path.join(newest_path, f)
        st = os.stat(fp)
        from datetime import datetime
        print(f'  {f}    {st.st_size} bytes    {datetime.fromtimestamp(st.st_mtime).strftime("%H:%M:%S")}')

# --- Test 2: Icon extraction ---
print('\nTesting icon extraction...')
import win32gui, win32con, win32api, win32ui
from PIL import Image

from win32comext.shell import shell, shellcon
flags = shellcon.SHGFI_SMALLICON | shellcon.SHGFI_ICON | shellcon.SHGFI_USEFILEATTRIBUTES
for ext in ['srt', 'mp4', 'mkv', 'bat', 'txt', 'py', 'log', '']:
    try:
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
            print(f'  .{ext or "no ext"} -> icon {img.size} mode={img.mode} OK')
            win32gui.DestroyIcon(hicon)
            hdc_mem.DeleteDC()
            hdc.DeleteDC()
            win32gui.ReleaseDC(0, hdc.GetHandleOutput())
        else:
            print(f'  .{ext or "no ext"} -> no icon handle')
    except Exception as e:
        print(f'  .{ext or "no ext"} -> ERROR: {e}')

print('\nAll tests completed.')
