Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\noc\homelab\services\zurg"
WshShell.Run "cmd /c zurg.exe > ""C:\Users\noc\homelab\logs\zurg.log"" 2>&1", 0, False
