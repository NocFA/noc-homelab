@echo off
REM Wrapper for library-update.ps1 called by Zurg on_library_update hook
powershell -ExecutionPolicy Bypass -File "C:\Users\noc\homelab-win\scripts\library-update.ps1" %*
