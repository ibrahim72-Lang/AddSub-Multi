"""Quick test to verify VideoCard is created correctly"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('dark-blue')

root = ctk.CTk()
root.geometry('400x300')

container = ctk.CTkScrollableFrame(root)
container.pack(fill='both', expand=True)

# Execute up to VideoCard class from the main file
with open('AddSub-Multi-GUI.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Split at VideoCard class
pre_start = content.index('class VideoCard(')
pre_end = content.index('class WaitingDialog', pre_start)
main_start = content.index('if __name__ == "__main__"')
preamble = content[:pre_start]
card_code = content[pre_start:pre_end]

exec(preamble, globals())
exec(card_code, globals())

try:
    card = VideoCard(container, 'C:/test/movie.mp4')
    card.pack(fill='x', pady=2)
    root.update_idletasks()
    print('CARD_HEIGHT:', card.winfo_reqheight())
    print('CARD_WIDTH:', card.winfo_reqwidth())
    print('CARD_MAPPED:', card.winfo_ismapped())
    print('SUCCESS')
except Exception as e:
    print('ERROR:', e)
    traceback.print_exc()

root.destroy()
