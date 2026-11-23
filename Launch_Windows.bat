@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 shift_corpus_gui.py
  goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python shift_corpus_gui.py
  goto end
)
echo Python not found. Install Python 3.10+ from python.org and enable the Python launcher.
:end
if errorlevel 1 pause
