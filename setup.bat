@echo off
REM Quick Setup Script for DeepWiki MCP Server (Windows)
REM This script helps you get started quickly

echo ==================================================
echo DeepWiki MCP Server - Quick Setup (Windows)
echo ==================================================
echo.

REM Check Python version
echo Checking Python version...
python --version 2>nul
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from python.org
    pause
    exit /b 1
)
echo Python found
echo.

REM Create virtual environment
echo Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment
    pause
    exit /b 1
)
echo Virtual environment activated
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --quiet --upgrade pip
echo pip upgraded
echo.

REM Install the package
echo Installing DeepWiki MCP Server...
pip install --quiet -e .
echo Package installed
echo.

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo .env file created
    echo You can customize settings in .env
) else (
    echo .env file already exists
)
echo.

REM Test installation
echo Testing installation...
where deepwiki-mcp >nul 2>&1
if %errorlevel% equ 0 (
    echo deepwiki-mcp command is available
) else (
    echo deepwiki-mcp command not found in PATH
    echo You can still run: python -m deepwiki_mcp.server
)
echo.

echo ==================================================
echo Setup Complete! 🎉
echo ==================================================
echo.
echo Next steps:
echo 1. (Optional) Edit .env to customize settings
echo 2. Run the server:
echo    -^> deepwiki-mcp
echo    or
echo    -^> python -m deepwiki_mcp.server
echo.
echo 3. Configure Claude Desktop:
echo    See INSTALL.md for integration instructions
echo.
echo For more information:
echo   - README.md - Full documentation
echo   - QUICKSTART.md - Getting started guide
echo   - INSTALL.md - Installation options
echo   - ARCHITECTURE.md - Technical details
echo.

pause
