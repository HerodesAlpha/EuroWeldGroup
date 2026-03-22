@echo off
cd /d "%~dp0"
echo Starting GitHub login (browser will open)...
"%ProgramFiles%\GitHub CLI\gh.exe" auth login --web --hostname github.com --git-protocol https
if errorlevel 1 pause
exit /b %errorlevel%
