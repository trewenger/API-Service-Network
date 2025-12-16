@echo off
echo Starting VariousInternalServices Web Interface...
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist "..\..\..\venv\Scripts\activate.bat" (
    call ..\..\..\venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Using system Python.
    echo.
)

REM Start production server
python prod_server.py

pause
