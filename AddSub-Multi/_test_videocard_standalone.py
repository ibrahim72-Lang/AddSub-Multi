"""Test VideoCard creation - standalone with minimal tkinter setup."""
import sys
sys.path.insert(0, r'C:\Users\ibrah\SynologyDrive\Programming Projects\Openhands Workspace\AddSub-Multi')

import tkinter as tk
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

def noop_getter(ext):
    return None

def test_videocard():
    root = tk.Tk()
    root.geometry("500x400")
    root.withdraw()
    
    # Create a mock scrollable frame (parent)
    parent = ctk.CTkScrollableFrame(root, width=400, height=300, fg_color="transparent")
    parent.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Manually create a VideoCard (must import class)
    from AddSub_Multi_GUI import VideoCard
    card = VideoCard(parent, r"C:\Users\ibrah\Videos\test.mp4", icon_getter=noop_getter)
    card.pack(fill="x", pady=2)
    
    root.update_idletasks()
    root.update()
    
    print(f"Card reqwidth={card.winfo_reqwidth()} reqheight={card.winfo_reqheight()}")
    print(f"Card winfo_width={card.winfo_width()} winfo_height={card.winfo_height()}")
    print(f"Card children: {[c.winfo_class() for c in card.winfo_children()]}")
    
    # Check parent container
    print(f"Parent winfo_height={parent.winfo_height()}")
    
    root.destroy()
    print("Test completed")

if __name__ == "__main__":
    test_videocard()
