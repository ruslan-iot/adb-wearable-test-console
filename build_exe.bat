@echo off
setlocal
cd /d "%~dp0"

REM Try Python launcher (3.11, 3.10, any 3.x), then python.exe on PATH
set "RUN="
py -3.11 -c "import sys" 2>nul && set RUN=py -3.11
if not defined RUN py -3.10 -c "import sys" 2>nul && set RUN=py -3.10
if not defined RUN py -3 -c "import sys" 2>nul && set RUN=py -3
if not defined RUN python -c "import sys" 2>nul && set RUN=python

if not defined RUN (
  echo ERROR: No Python 3 found. Install Python 3.10+ and use "py" or "python" on PATH.
  exit /b 1
)

echo Using: %RUN%
echo Installing dependencies...
%RUN% -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Building executable with PyInstaller...
%RUN% -m PyInstaller --noconfirm adb_wearable_console.spec
if errorlevel 1 exit /b 1

echo.
echo ========================================
echo BUILD OK
echo Run: dist\ADBWearableConsole\ADBWearableConsole.exe
echo Distribute: ZIP the entire folder dist\ADBWearableConsole
echo See DISTRIBUTING.md for details.
echo ========================================
endlocal
