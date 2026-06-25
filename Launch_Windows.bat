@echo off
:: Istanbul Route Optimizer — Windows Launcher
:: Double-click this file to start the server and open the browser automatically.

title Istanbul Route Optimizer

echo =============================================
echo    Istanbul Route Optimizer -- Starting...
echo =============================================
echo.

:: Move to the script's own directory
cd /d "%~dp0"

:: ── Python kontrolü ──────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python bulunamadi!
    echo Python 3.10+ adresinden kurun: https://www.python.org
    echo.
    pause
    exit /b 1
)

:: ── .venv yoksa setup_env.py ile otomatik kur ────────────
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Sanal ortam (.venv) bulunamadi.
    echo Otomatik kurulum baslatiliyor (setup_env.py)...
    echo Bu islem internet baglantisina gore 5-20 dakika surebilir.
    echo.
    python setup_env.py
    if errorlevel 1 (
        echo.
        echo ERROR: Otomatik kurulum basarisiz. Hata mesajlarini inceleyin.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: 2. Check data files and download/generate if missing
if not exist "models\checkpoints\best_heuristic_net.pt" goto run_setup
if not exist "data\processed\full_hierarchy.graphml" goto run_setup
goto start_server

:run_setup
echo Data files not found. Running setup_data.py...
echo (This may take 5-15 minutes on first run)
echo.
python setup_data.py
if errorlevel 1 (
    echo.
    echo ERROR: setup_data.py failed. Check the error messages above.
    pause
    exit /b 1
)

:start_server
:: 3. Open browser automatically after 2 seconds (in background)
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5001"

:: 4. Start Flask web server
echo.
echo Server starting at: http://127.0.0.1:5001
echo Press Ctrl+C to stop.
echo.
python app.py

pause
