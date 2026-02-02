@echo off
rem Bilibili Video Summary Tool - CLI Launcher
rem Run this from command line: cli.bat <URL> [args...]

rem Set current directory to script location
cd /d "%~dp0"

echo ==================================================
echo      Bilibili Video Summary Tool (CLI)
echo ==================================================
echo.

rem ==================================================
rem METHOD 1: Try the 'py' launcher (Recommended for Windows)
rem ==================================================
where py >nul 2>&1
if %errorlevel% equ 0 (
    set RUN_CMD=py
    goto :FOUND
)

rem ==================================================
rem METHOD 2: Try 'python' command
rem ==================================================
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
echo Using command: %RUN_CMD%
echo.

rem Pass all arguments (%*) to main.py
%RUN_CMD% main.py %*

if %errorlevel% neq 0 (
    echo.
    echo Program exited with error level: %errorlevel%
)
exit /b %errorlevel%

:PYTHON_MISSING
echo.
echo ==================================================
echo Error: Working Python installation not found!
echo ==================================================
echo.
echo Please force install python or fix your PATH.
echo.
exit /b 1
