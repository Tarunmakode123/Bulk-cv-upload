# Running the app quickly

Instead of pasting the long python command each time, use one of the helper scripts included in this folder.

- PowerShell (recommended):

  Open PowerShell in the project root and run:

  ```powershell
  # if you get an ExecutionPolicy error, run this once to allow running the script in the current session
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  .\run.ps1
  ```

- Windows double-click / Command Prompt:

  - Double-click `run.bat` from Explorer or run `run.bat` from cmd.exe.

Notes:
- Both scripts prefer the virtual environment python at `.venv\Scripts\python.exe`. Ensure your virtualenv is created and the required packages are installed (Flask, PyMuPDF, python-dotenv, etc.).
- If you prefer using an IDE, you can create a VS Code Task or debug configuration that runs `run.ps1` or `main.py` directly.
