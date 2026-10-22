@echo off
TITLE Tracker Telegram Notifier Setup
echo ========================================================
echo   Starting Tracker Telegram Notifier Environment...
echo ========================================================

IF NOT EXIST .venv (
    echo Creating Python Virtual Environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Upgrading Pip...
python -m pip install --upgrade pip

echo Installing/Updating Dependencies...
pip install -r requirements.txt

echo.
echo Starting Server at http://localhost:8080 ...
python -m uvicorn app.main:app --reload --port 8080
pause