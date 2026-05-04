#!/bin/bash
set -e

echo "==> Запуск миграций..."
python manage.py migrate --noinput

echo "==> Создание суперпользователя (если не существует)..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@adweave.local', 'admin123')
    print('Создан admin / admin123')
else:
    print('Admin уже существует')
"

echo "==> Запуск сервера..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --log-level info
