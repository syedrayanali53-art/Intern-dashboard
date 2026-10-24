@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 scripts\monitor.py
  if not errorlevel 1 py -3 scripts\publish.py
) else (
  python scripts\monitor.py
  if not errorlevel 1 python scripts\publish.py
)
if errorlevel 1 (
  echo The check had a problem. Review the messages above and source coverage on the board.
) else (
  echo Done. Open _site\intern-hunt.html.
)
pause
