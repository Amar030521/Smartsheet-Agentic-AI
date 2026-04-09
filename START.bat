@echo off
chcp 65001 >nul
title Smartsheet AI Agent

echo.
echo ==========================================
echo   Smartsheet AI Agent
echo   Production Startup
echo ==========================================
echo.

:: Store the folder where START.bat lives
set "ROOT=%~dp0"
set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"

echo Root folder: %ROOT%
echo.

:: Find Python
set PYTHON_CMD=
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python & goto :found_python )
python3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python3 & goto :found_python )
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py & goto :found_python )

echo [ERROR] Python not found. Install from https://python.org
echo Check "Add Python to PATH" during install.
pause & exit /b 1

:found_python
echo [OK] Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: pip via python -m pip (always works even without Scripts in PATH)
set "PIP_CMD=%PYTHON_CMD% -m pip"
echo [OK] pip ready

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    pause & exit /b 1
)
echo [OK] Node.js:
node --version

:: Create .env if missing
if not exist "%BACKEND%\.env" (
    echo.
    echo [SETUP] Creating .env from template...
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    echo Opening .env - add your API keys then save and close...
    notepad "%BACKEND%\.env"
    timeout /t 3 /nobreak >nul
)

echo.
echo [1/2] Starting Backend on port 8000...
start "Smartsheet Backend" cmd /k "cd /d "%BACKEND%" && %PIP_CMD% install -r requirements.txt -q && echo [OK] Packages installed && %PYTHON_CMD% main.py"

echo Waiting for backend...
timeout /t 8 /nobreak >nul

echo [2/2] Starting Frontend on port 3000...
start "Smartsheet Frontend" cmd /k "cd /d "%FRONTEND%" && npm install && npm start"

echo.
echo ==========================================
echo  Chat UI  -> http://localhost:3000
echo  API Docs -> http://localhost:8000/docs
echo  Health   -> http://localhost:8000/health
echo ==========================================
echo.
pause