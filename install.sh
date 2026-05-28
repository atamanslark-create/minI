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

# Install system dependencies
echo "📦 Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    echo "   Using apt-get..."
    apt-get update -qq
    apt-get install -y python3-venv python3-dev python3-pip git
elif command -v yum &> /dev/null; then
    echo "   Using yum..."
    yum install -y python3-devel python3-pip git
else
    echo "❌ Cannot detect package manager (apt-get or yum)"
    exit 1
fi

# Clean up old installation if it exists
if [ -d "$INSTALL_DIR" ]; then
    echo "🧹 Cleaning up old installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create installation directory
echo "📁 Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Copy project files
echo "📋 Copying project files..."
cp bot.py agent.py config.py utils.py alerts.py alerts_extended.py metrics.py report.py network_checks.py glados_client.py requirements.txt "$INSTALL_DIR/"

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv "$VENV_DIR" || {
    echo "❌ Failed to create virtual environment"
    echo "   Trying alternative method..."
    python3 -m pip install --upgrade pip
    python3 -m venv "$VENV_DIR"
}

# Source virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r "$INSTALL_DIR/requirements.txt"

# Install additional optional packages
echo "📦 Installing optional packages..."
pip install speedtest-cli requests -q 2>/dev/null || true

# Create config file if it doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "⚙️ Creating config file..."

    # Prompt for mini-bot configuration
    read -p "📌 Enter mini-bot Telegram token: " BOT_TOKEN
    read -p "📌 Enter admin chat IDs (comma-separated): " ADMIN_IDS

    # Prompt for GLaDoS integration (optional)
    read -p "🤖 Enter GLaDoS bot token (optional, press Enter to skip): " GLADOS_TOKEN
    read -p "🤖 Enter GLaDoS owner ID (optional, press Enter to skip): " GLADOS_OWNER_ID

    # Create config with provided values
    cat > "$CONFIG_DIR/config.yaml" << EOF
# mini-bot configuration
telegram_token: $BOT_TOKEN
admin_chat_ids: $ADMIN_IDS

# ==================== GLaDoS Integration (Optional) ====================
# Connect mini-bot to GLaDoS master bot for centralized control
EOF

    if [ ! -z "$GLADOS_TOKEN" ] && [ ! -z "$GLADOS_OWNER_ID" ]; then
        cat >> "$CONFIG_DIR/config.yaml" << EOF

glados_token: $GLADOS_TOKEN
glados_owner_id: $GLADOS_OWNER_ID
EOF
        echo "✅ GLaDoS integration configured"
    else
        echo "⏭️ GLaDoS integration skipped (can be added later)"
    fi

    echo "✅ Config file created at $CONFIG_DIR/config.yaml"
else
    echo "⚠️  Config file already exists at $CONFIG_DIR/config.yaml"
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
echo "1. systemctl start mini-bot"
echo "2. Check status: systemctl status mini-bot"
echo "3. Verify logs: journalctl -u mini-bot -n 20"
echo ""

# Start the service
echo "🚀 Starting mini-bot service..."
systemctl start mini-bot
sleep 3

# Check if service started successfully
if systemctl is-active --quiet mini-bot; then
    echo "✅ Service started successfully"

    # Check for GLaDoS integration
    if journalctl -u mini-bot -n 10 | grep -q "GLaDoS client initialized"; then
        echo "✅ GLaDoS integration is ACTIVE"
        echo "   - Hourly reports will be sent to GLaDoS"
        echo "   - Remote command execution is enabled"
        echo "   - Critical alerts will be sent to GLaDoS"
    else
        echo "⚠️  GLaDoS integration is NOT configured"
        echo "   - To enable, add glados_token and glados_owner_id to $CONFIG_DIR/config.yaml"
        echo "   - Then restart: systemctl restart mini-bot"
    fi
else
    echo "❌ Failed to start service"
    echo "   Check logs: journalctl -u mini-bot -n 50"
    exit 1
fi

echo ""

# Print summary
echo "════════════════════════════════════════════════════════════════"
echo "📊 INSTALLATION SUMMARY"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📁 Installation Directory: $INSTALL_DIR"
echo "⚙️  Config Directory:      $CONFIG_DIR"
echo "🐍 Python Virtual Env:    $VENV_DIR"
echo "🔧 Service File:          $SERVICE_FILE"
echo ""
echo "📦 Features:"
echo "   ✅ VPS Monitoring (CPU, RAM, Disk)"
echo "   ✅ Service Management (SSH, Nginx, MySQL, PostgreSQL, Redis, Docker)"
echo "   ✅ Network Monitoring (Ping, Ports, Speedtest, WireGuard)"
echo "   ✅ Smart Alert System (with cooldown filtering)"
if [ ! -z "$GLADOS_TOKEN" ]; then
    echo "   ✅ GLaDoS Integration (hourly reports, remote commands)"
fi
echo ""
echo "📌 Useful Commands:"
echo "   systemctl status mini-bot          - Check service status"
echo "   systemctl stop mini-bot            - Stop service"
echo "   systemctl restart mini-bot         - Restart service"
echo "   journalctl -u mini-bot -f          - View live logs"
echo "   nano $CONFIG_DIR/config.yaml       - Edit configuration"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
