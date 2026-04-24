@echo off
setlocal

:: Install uv if not already installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing uv...
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    :: Add uv to PATH for the rest of this script
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
) else (
    for /f "tokens=*" %%i in ('uv --version') do echo uv already installed: %%i
)

:: Create virtual environment with Python 3.11
echo Creating Python 3.11 virtual environment...
uv venv --python 3.11

:: Install dependencies
echo Installing dependencies...
uv pip install -r requirements.txt

echo.
echo Setup complete! Activate the environment with:
echo   .venv\Scripts\activate
