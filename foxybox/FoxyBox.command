#!/bin/bash
# Подвійний клік по цьому файлу запускає FoxyBox і відкриває його у браузері (macOS).
# При першому запуску сам готує середовище (.venv у цій папці) і ставить Telethon.
cd "$(dirname "$0")" || exit 1

fail() {
  echo
  echo "$1"
  echo
  read -r -p "Натисніть Enter, щоб закрити вікно..." _
  exit 1
}

echo "Запускаю FoxyBox..."

# python3 є? (на чистому Mac це «заглушка», яка без Xcode tools не працює)
if ! python3 --version >/dev/null 2>&1; then
  fail "Python не знайдено. Встановіть його з https://www.python.org/downloads/ і запустіть FoxyBox знову."
fi

VENV=".venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "Перший запуск: готую середовище (до 1-2 хвилин)..."
  python3 -m venv "$VENV" || fail "Не вдалося створити середовище. Перевстановіть Python з python.org і спробуйте ще раз."
fi

if ! "$PY" -c "import telethon" >/dev/null 2>&1; then
  echo "Встановлюю Telethon (потрібен інтернет)..."
  "$PY" -m pip install --disable-pip-version-check -q telethon \
    || fail "Не вдалося встановити Telethon. Перевірте інтернет і запустіть FoxyBox ще раз."
fi

"$PY" foxybox.py "$@"
echo
read -r -p "FoxyBox зупинено. Натисніть Enter, щоб закрити вікно..." _
