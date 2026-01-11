@echo off
echo ========================================
echo      Screen Translator
echo      Powered by Flet + EasyOCR
echo ========================================
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.
echo Starting Flet application...
set PYTHONWARNINGS=ignore
python screen_translator.py
echo.
echo Application closed.
echo Temporary files cleaned up automatically.
pause