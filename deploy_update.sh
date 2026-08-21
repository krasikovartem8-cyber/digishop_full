#!/bin/bash
# deploy_update.sh — деплой обновлений бота и API

set -e
echo "→ Останавливаю сервисы..."
systemctl stop digishop-bot 2>/dev/null || true
systemctl stop digishop-api 2>/dev/null || true

echo "→ Копирую файлы..."
cp -f delivery_fields.py /opt/digishop/
cp -f handlers/order_fsm.py /opt/digishop/handlers/
cp -rf suppliers/ /opt/digishop/
cp -rf api/ /opt/digishop/

echo "→ Устанавливаю зависимости API..."
/opt/digishop/venv/bin/pip install fastapi uvicorn[standard] -q

echo "→ Создаю systemd для API..."
cat > /etc/systemd/system/digishop-api.service << 'EOF'
[Unit]
Description=DigiShop Web API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/digishop
EnvironmentFile=/opt/digishop/.env
ExecStart=/opt/digishop/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable digishop-api
systemctl start digishop-api
systemctl start digishop-bot

sleep 3
echo ""
echo "=== Статус бота ==="
systemctl status digishop-bot --no-pager | head -8
echo ""
echo "=== Статус API ==="
systemctl status digishop-api --no-pager | head -8
echo ""
echo "✅ Готово! API доступен на http://localhost:8000"
echo "   Документация: http://localhost:8000/docs"
