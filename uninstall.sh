#!/bin/bash
set -e

INSTALL_DIR="/opt/mini-bot"
CONFIG_DIR="/etc/mini-bot"
SERVICE_FILE="/etc/systemd/system/mini-bot.service"

echo "🗑️  Uninstalling mini-bot..."

if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root"
   exit 1
fi

# Stop and disable service
echo "🛑 Stopping service..."
systemctl stop mini-bot 2>/dev/null || true
systemctl disable mini-bot 2>/dev/null || true

# Remove service file
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

# Reload systemd
systemctl daemon-reload

echo "✅ Uninstallation complete!"
echo "ℹ️  Config directory ($CONFIG_DIR) was kept for backup"
