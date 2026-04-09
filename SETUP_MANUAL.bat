@echo off
chcp 65001 >nul
title Manual Setup - Smartsheet Agent

echo ==========================================
echo   Manual Setup Helper
echo   Run this if START.bat had pip errors
echo ==========================================
echo.

:: Try all python variants
echo Step 1: Finding Python...
where python >nul 2>&1 && python --version && goto :pip_install
where python3 >nul 2>&1 && python3 --version && set PYTHON_CMD=python3 && goto :pip_install  
where py >nul 2>&1 && py --version && set PYTHON_CMD=py && goto :pip_install

echo Python not in PATH. Searching common locations...
if exist "C:\Python312\python.exe" ( set PYTHON_CMD=C:\Python312\python.exe & goto :pip_install )
if exist "C:\Python311\python.exe" ( set PYTHON_CMD=C:\Python311\python.exe & goto :pip_install )
if exist "C:\Python310\python.exe" ( set PYTHON_CMD=C:\Python310\python.exe & goto :pip_install )
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" ( set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe & goto :pip_install )
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" ( set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe & goto :pip_install )
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" ( set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe & goto :pip_install )

echo.
echo [ERROR] Python not found anywhere.
echo Please install from https://python.org
echo Make sure to CHECK "Add Python to PATH"
pause & exit /b 1

:pip_install
if not defined PYTHON_CMD set PYTHON_CMD=python
echo [OK] Using: %PYTHON_CMD%
echo.

echo Step 2: Installing backend dependencies...
cd /d "%~dp0backend"
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. Trying with --user flag...
    %PYTHON_CMD% -m pip install -r requirements.txt --user
)
echo.
echo [OK] Dependencies installed.
echo.

echo Step 3: Starting backend server...
echo Open http://localhost:8000/health in browser to verify
echo.
%PYTHON_CMD% main.py

pause
