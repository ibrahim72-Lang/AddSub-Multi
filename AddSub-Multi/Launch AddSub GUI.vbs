' Launch AddSub-Multi GUI without any console window
' This VBScript eliminates the command prompt flash

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Build the command to run pythonw with the GUI script
command = "pythonw """ & scriptDir & "\AddSub-Multi-GUI.py"""

' Run the command with hidden window (0 = hidden, False = don't wait)
objShell.Run command, 0, False

' Clean up
Set objShell = Nothing
Set objFSO = Nothing
