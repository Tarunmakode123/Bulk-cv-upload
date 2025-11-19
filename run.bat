@echo off
REM Simple helper batch file to run the Flask app using the venv python
SET SCRIPT_DIR=%~dp0
SET VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe
IF EXIST "%VENV_PY%" (
  echo Using venv python at %VENV_PY%
  "%VENV_PY%" "%SCRIPT_DIR%Resume_Analyser_Using_Python\main.py"
) ELSE (
  echo Venv python not found, falling back to system python
  python "%SCRIPT_DIR%Resume_Analyser_Using_Python\main.py"
)
PAUSE
