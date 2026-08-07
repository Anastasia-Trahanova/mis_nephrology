@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ============================================================
echo MIS Nephrology - Pilot Installer Build
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 goto NO_PYTHON

echo Python:
python -c "import sys; print(sys.executable); print(sys.version)"
if errorlevel 1 goto FAILED
echo.

python "%~dp0build_installer.py" %*
set "RC=%ERRORLEVEL%"
goto FINISH

:NO_PYTHON
echo ERROR: Python was not found in PATH.
echo Activate the project venv and run this file again.
set "RC=1"
goto FINISH

:FAILED
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" set "RC=1"

:FINISH
echo.
if "%RC%"=="0" (
  echo BUILD COMPLETED.
  echo Output: installer\output\MIS_Nephrology_Pilot_Setup.exe
) else (
  echo BUILD FAILED. Exit code: %RC%
)
echo.
pause
exit /b %RC%
