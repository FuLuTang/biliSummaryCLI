@echo off
rem Bilibili Video Summary Tool - Windows Launcher
rem Double click this file to start

rem Set current directory to script location
cd /d "%~dp0"

echo ==================================================
echo      Bilibili Video Summary Tool
echo ==================================================
echo.

rem ==================================================
rem METHOD 1: Try the 'py' launcher (Recommended for Windows)
rem ==================================================
echo Checking for 'py' launcher...
py --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('py --version') do set PYTHON_VERSION=%%i
    set RUN_CMD=py
    goto :FOUND
)

rem ==================================================
rem METHOD 2: Try 'python' command
rem ==================================================
echo 'py' not found, checking for 'python'...
where python >nul 2>&1
if %errorlevel% neq 0 (
    goto :PYTHON_MISSING
)

rem Check if 'python' is actually working (ignoring the Windows Store shim)
set PYTHON_VERSION=
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i

if "%PYTHON_VERSION%"=="" (
    echo.
    echo ! Warning: 'python' command exists but produced no output.
    echo ! This usually means it's the Windows Store alias/shim.
    goto :PYTHON_MISSING
)

set RUN_CMD=python
goto :FOUND


:FOUND
echo.
echo %PYTHON_VERSION% found.
echo Using command: %RUN_CMD%
echo.
echo Starting program...
echo.

%RUN_CMD% main.py --ui

if %errorlevel% neq 0 (
    echo.
    echo ==================================================
    echo Program exited with error. Please check above.
    echo ==================================================
    pause
)
exit /b 0

:PYTHON_MISSING
echo.
echo ==================================================
echo Error: Working Python installation not found!
echo ==================================================
echo.
echo 1. If you just installed Python, try restarting usage.
echo 2. Python might be installed but not in your PATH.
echo.
echo Please try installing Python again from https://www.python.org/downloads/
echo IMPORTANT: Check "Add Python to PATH" during installation.
echo.
pause
exit /b 1
