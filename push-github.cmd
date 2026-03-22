@echo off
setlocal
cd /d "%~dp0"

"%ProgramFiles%\GitHub CLI\gh.exe" auth status >nul 2>&1
if errorlevel 1 (
  echo You are not logged in to GitHub.
  echo Run login-github.cmd first, then run this script again.
  exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo No remote yet. Creating GitHub repo EuroWeldGroup and pushing...
  "%ProgramFiles%\GitHub CLI\gh.exe" repo create EuroWeldGroup --public --source=. --remote=origin --push
  if errorlevel 1 (
    echo.
    echo If the name is taken, create an empty repo on github.com, then:
    echo   git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
    echo   git push -u origin main
    exit /b 1
  )
) else (
  echo Pushing to existing origin...
  git push -u origin main
)

echo Done.
exit /b 0
