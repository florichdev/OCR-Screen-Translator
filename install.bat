@echo off
echo ========================================
echo   Screen Translator - Installation
echo   Flet + EasyOCR + Google Translate
echo ========================================
echo.
echo Creating virtual environment...
python -m venv venv
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.
echo Installing Flet and dependencies...
pip install -r requirements.txt
echo.
echo ========================================
echo Installation complete!
echo.
echo Features installed:
echo - Flet GUI with Material Design
echo - EasyOCR for text recognition
echo - Google Translate API
echo - Screen area selection
echo - Clipboard support
echo.
echo To run the application:
echo   run.bat
echo ========================================
pause