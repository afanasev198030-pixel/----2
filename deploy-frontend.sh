#!/bin/bash
# Запускать НА СЕРВЕРЕ (82.148.28.122), где крутится сайт.
# Сначала довези новый код на сервер: git pull или rsync.

set -e
cd "$(dirname "$0")"
echo "[deploy] Rebuilding frontend image..."
docker-compose -f docker-compose.prod.yml build frontend --no-cache
echo "[deploy] Restarting frontend container..."
docker-compose -f docker-compose.prod.yml up -d frontend
echo "[deploy] Done. Open http://82.148.28.122/ and do Ctrl+F5."
