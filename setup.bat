@echo off
echo ======================================================================
echo   Installing Dependencies for MARK 2.0 AI Visual Assistant...
echo ======================================================================
pip install -r requirements.txt
echo.
echo ======================================================================
echo   Setup Complete! Launching MARK 2.0...
echo ======================================================================
python main.py
