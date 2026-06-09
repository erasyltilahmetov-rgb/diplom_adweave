#!/bin/bash
set -e

PROJ="/mnt/d/Дипломка/Дипломная"
cd "$PROJ"

echo ""
echo "  AdWeave — запуск"
echo "  ================"
echo ""

# --build пересобирает образ (нужно после изменений кода)
if [ "${1}" = "--build" ]; then
    echo "[0] Сборка образа..."
    docker compose build
    echo ""
fi

echo "[1] Запускаем контейнеры..."
docker compose up -d

echo ""
echo "  Локально:  http://localhost:8000"
echo ""
echo "  Публичный URL (ждём туннель ~20 сек)..."
URL=""
for i in $(seq 1 20); do
    URL=$(docker logs adweave_tunnel 2>&1 | grep -oP 'https://\S+\.trycloudflare\.com' | head -1)
    if [ -n "$URL" ]; then
        break
    fi
    sleep 1
done

if [ -n "$URL" ]; then
    echo ""
    echo "  Публичный: $URL"
else
    echo "  (туннель стартует, проверь: docker logs adweave_tunnel)"
fi

echo ""
echo "  Остановить: docker compose down"
echo "  Логи:       docker compose logs -f web"
echo ""
