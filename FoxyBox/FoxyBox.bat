@echo off
chcp 65001 >nul
rem Подвійний клік по цьому файлу запускає FoxyBox і відкриває його у браузері (Windows).
cd /d "%~dp0"
echo Запускаю FoxyBox...
echo.

rem Пробуємо різні способи виклику Python, який є в системі.
where py >nul 2>nul
if %errorlevel%==0 (
    py foxybox.py
    goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python foxybox.py
    goto end
)
echo.
echo Python не знайдено. Встановіть його з https://www.python.org/downloads/
echo (під час встановлення поставте галочку "Add Python to PATH").

:end
echo.
echo Вікно можна закрити. Якщо була помилка - вона вище.
pause
