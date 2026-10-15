@echo off
REM Start the Doctor Visiting Card Extraction web app on Windows.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run setup.ps1 first, or create it manually:
    echo     py -3.12 -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting Streamlit... open http://localhost:8501 in your browser.
".venv\Scripts\python.exe" -m streamlit run app.py
endlocal
