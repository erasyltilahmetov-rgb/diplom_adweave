FROM python:3.12-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright (для сбора трендов)
RUN playwright install chromium --with-deps

# Копируем проект
COPY . .

# Статика
RUN python manage.py collectstatic --noinput || true

# Порт
EXPOSE 8000

# Стартовый скрипт
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
