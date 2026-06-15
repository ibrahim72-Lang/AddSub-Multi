"""Test: create VideoCard instances in a scrollable frame to verify display."""
import sys, os, time
import tkinter as tk
import customtkinter as ctk

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

print("Creating root...", flush=True)
root = tk.Tk()
root.geometry("800x600")

left_panel = ctk.CTkFrame(root)
left_panel.pack(side="left", fill="both", expand=True, padx=10, pady=10)

file_container = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
file_container.pack(fill="both", expand=True)

import importlib.util
spec = importlib.util.spec_from_file_location('AddSub_Multi_GUI', os.path.join(script_dir, 'AddSub-Multi-GUI.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def noop_icon(ext):
    return None

test_files = [
    r"C:\Users\ibrah\Videos\Movie1.mp4",
    r"C:\Users\ibrah\Videos\Movie2.mkv",
    r"C:\Users\ibrah\Videos\Movie3.avi",
]

cards = []
for fp in test_files:
    card = module.VideoCard(file_container, fp, icon_getter=noop_icon)
    card.pack(fill="x", pady=2)
    cards.append(card)

print("Cards created. Updating...", flush=True)
root.update_idletasks()
root.update()

for i, card in enumerate(cards):
    print(f"Card {i}: width={card.winfo_width()}, height={card.winfo_height()}, "
          f"reqwidth={card.winfo_reqwidth()}, reqheight={card.winfo_reqheight()}", flush=True)
    for c in card.winfo_children():
        print(f"  Child: {c.winfo_class()} w={c.winfo_width()} h={c.winfo_height()} "
              f"visible={c.winfo_viewable()}", flush=True)

print(f"file_container: width={file_container.winfo_width()}, height={file_container.winfo_height()}", flush=True)
print("SUCCESS - window will close in 3 seconds", flush=True)

root.after(3000, root.destroy)
root.mainloop()
print("Done.", flush=True)
