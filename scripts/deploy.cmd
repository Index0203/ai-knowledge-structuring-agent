@echo off
REM Windows shortcut: runs the deployment script without execution-policy prompts.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
