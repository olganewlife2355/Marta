@echo off
chcp 65001 >nul
rem Подвійний клік по цьому файлу запускає FoxyBox і відкриває його у браузері (Windows).
rem При першому запуску сам готує середовище (.venv у цій папці) і ставить Telethon + tzdata.
cd /d "%~dp0"
echo Запускаю FoxyBox...

set "VPY=.venv\Scripts\python.exe"
if exist "%VPY%" goto deps

rem Шукаємо Python: спершу лаунчер py, потім python
rem (where python не годиться: знаходить заглушку Microsoft Store).
set "SYSPY="
py -3 --version >nul 2>nul && set "SYSPY=py -3"
if not defined SYSPY (python --version >nul 2>nul && set "SYSPY=python")
if not defined SYSPY goto nopython

echo Перший запуск: готую середовище (до 1-2 хвилин)...
%SYSPY% -m venv .venv
if errorlevel 1 goto novenv

:deps
"%VPY%" -c "import telethon, tzdata" >nul 2>nul
if not errorlevel 1 goto run
echo Встановлюю Telethon (потрібен інтернет)...
"%VPY%" -m pip install --disable-pip-version-check -q telethon tzdata
if errorlevel 1 goto nopip

:run
"%VPY%" foxybox.py %*
goto end

:nopython
echo.
echo Python не знайдено. Встановіть його з https://www.python.org/downloads/
echo (на першому екрані інсталятора поставте галочку "Add Python to PATH").
goto end

:novenv
echo.
echo Не вдалося створити середовище. Перевстановіть Python з python.org і спробуйте ще раз.
goto end

:nopip
echo.
echo Не вдалося встановити Telethon. Перевірте інтернет і запустіть FoxyBox ще раз.

:end
echo.
echo Вікно можна закрити. Якщо була помилка - вона вище.
pause
