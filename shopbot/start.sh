#!/bin/bash

echo "Запуск сервера Django..."
python manage.py runserver &  # Запускаем сервер Django в фоновом режиме

echo "Запуск Telegram бота..."
python manage.py start_telegram_bot &  # Запускаем Telegram бота в фоновом режиме

# Ждём завершения всех фоновых процессов
wait