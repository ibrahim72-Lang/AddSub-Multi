@echo off
:: Launch AddSub-Multi GUI
:: Simple launcher for the graphical interface

cd /d "%~dp0"

:: Use pythonw.exe to launch without console window
start "" pythonw AddSub-Multi-GUI.py

:: Exit immediately (no window stays open)
exit
