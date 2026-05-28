#!/bin/bash
set -e

INSTALL_DIR="/opt/mini-bot"
CONFIG_DIR="/etc/mini-bot"
SERVICE_FILE="/etc/systemd/system/mini-bot.service"
VENV_DIR="$INSTALL_DIR/venv"

echo "🚀 Installing mini-bot VPS Monitor..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root"
   exit 1
fi

# Create installation directory
echo "📁 Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Copy project files
echo "📋 Copying project files..."
cp bot.py agent.py config.py utils.py requirements.txt "$INSTALL_DIR/"

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r "$INSTALL_DIR/requirements.txt"

# Create config file if it doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "⚙️ Creating config file..."
    cat > "$CONFIG_DIR/config.yaml" << EOF
# mini-bot configuration
telegram_token: YOUR_BOT_TOKEN_HERE
admin_chat_ids: YOUR_CHAT_IDS_HERE

# Example:
# telegram_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
# admin_chat_ids: 12345678,87654321
EOF
    echo "⚠️  Please edit $CONFIG_DIR/config.yaml with your bot token and admin chat IDs"
fi

# Create systemd service file
echo "🔧 Creating systemd service..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=mini-bot VPS Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chmod 644 "$SERVICE_FILE"
chmod +x "$INSTALL_DIR/bot.py"

# Reload systemd and enable service
echo "🔄 Enabling service..."
systemctl daemon-reload
systemctl enable mini-bot

echo ""
echo "✅ Installation complete!"
echo ""
echo "📌 Next steps:"
echo "1. Edit $CONFIG_DIR/config.yaml with your Telegram bot token and admin chat IDs"
echo "2. Run: systemctl start mini-bot"
echo "3. Check status: systemctl status mini-bot"
echo ""
