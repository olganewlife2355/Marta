#!/bin/bash
# Подвійний клік по цьому файлу запускає FoxyBox і відкриває його у браузері.
cd "$(dirname "$0")"
echo "Запускаю FoxyBox..."
exec python3 foxybox.py
