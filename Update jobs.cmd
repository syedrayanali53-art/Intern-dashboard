@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 scripts\monitor.py
) else (
  python scripts\monitor.py
)
if errorlevel 1 (
  echo The check had a problem. Review the messages above and source coverage on the board.
) else (
  echo Done. Open intern-hunt.html or reload its results.
)
pause
