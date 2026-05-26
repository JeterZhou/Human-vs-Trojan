@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "APP_DIR=%~dp0"
set "APP_PY=%APP_DIR%HVT_LAN.py"
set "LOGIC_PY=%APP_DIR%HVT_final.py"
set "REQ_FILE=%APP_DIR%requirements_hvt.txt"
set "VENV_DIR=%APP_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "BASE_PY="
set "RUN_PY="
set "PY_VER="

if not exist "%APP_PY%" (
    echo [ERROR] HVT_LAN.py not found.
    echo Expected: "%APP_PY%"
    pause
    exit /b 1
)

if not exist "%LOGIC_PY%" (
    echo [ERROR] HVT_final.py not found.
    echo Expected: "%LOGIC_PY%"
    pause
    exit /b 1
)

if exist "%VENV_PY%" set "BASE_PY=%VENV_PY%"
if not defined BASE_PY for %%V in (3.13 3.12 3.11 3.10 3.14) do (
    py -%%V -c "import sys;print(sys.executable)" > "%TEMP%\hvt_py_path.txt" 2>nul
    if not errorlevel 1 (
        set /p BASE_PY=<"%TEMP%\hvt_py_path.txt"
        goto :py_found
    )
)
if not defined BASE_PY for %%I in (python.exe) do set "BASE_PY=%%~$PATH:I"
:py_found

if not defined BASE_PY (
    echo [ERROR] Python was not found.
    echo Install Python 3 and run this launcher again.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%V in (`"%BASE_PY%" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"`) do set "PY_VER=%%V"
echo [INFO] Python found: "%BASE_PY%"
echo [INFO] Python version: %PY_VER%

if not exist "%REQ_FILE%" (
    > "%REQ_FILE%" echo networkx
    >> "%REQ_FILE%" echo matplotlib
)

if not exist "%VENV_PY%" (
    echo [INFO] Creating virtual environment...
    "%BASE_PY%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
)

set "RUN_PY=%VENV_PY%"
if not exist "%RUN_PY%" set "RUN_PY=%BASE_PY%"

echo [INFO] Upgrading pip, setuptools, wheel...
"%RUN_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [WARN] pip bootstrap upgrade failed. Continuing...
)

echo [INFO] Installing required packages: networkx, matplotlib
"%RUN_PY%" -m pip install --default-timeout 120 networkx matplotlib
if errorlevel 1 (
    echo [ERROR] Failed to install required packages.
    pause
    exit /b 1
)

"%RUN_PY%" -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [WARN] tkinter is not available in this Python environment.
    echo [WARN] Reinstall Python with Tk support if the GUI cannot open.
)

echo [INFO] Skipping pygame installation.
echo [INFO] This launcher is intended for the LAN/Tk workflow.

echo.
echo [INFO] Using Python: "%RUN_PY%"
echo [INFO] Starting HVT...
echo [INFO] In the GUI you can choose host/join and attacker/defender.
echo.
"%RUN_PY%" "%APP_PY%" --logic "%LOGIC_PY%"
set "EXITCODE=%ERRORLEVEL%"

echo.
echo [INFO] Program exited with code: %EXITCODE%
pause
exit /b %EXITCODE%
