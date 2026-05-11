@echo off
REM ────────────────────────────────────────────────
REM  TrimOS Build Script
REM  Packages TrimOS into a distributable .exe
REM ────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════╗
echo  ║       TrimOS Build Script            ║
echo  ╚══════════════════════════════════════╝
echo.

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

REM Install/upgrade build dependencies
echo [1/3] Installing dependencies...
pip install pyinstaller --quiet --upgrade
pip install -r requirements.txt --quiet

REM Clean previous build
echo [2/3] Cleaning previous builds...
if exist build rmdir /s /q build
if exist "dist\TrimOS" rmdir /s /q "dist\TrimOS"

REM Build with PyInstaller
echo [3/3] Building TrimOS.exe ...
echo.
pyinstaller trimos.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed! Check the output above for details.
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       Build Complete!                ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Output:  dist\TrimOS\TrimOS.exe
echo.
echo  To run:  cd dist\TrimOS ^& TrimOS.exe
echo.
echo  To distribute: zip the entire dist\TrimOS folder.
echo.
pause
