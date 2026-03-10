#!/bin/bash
set -e

echo "=== Grid Bot Backtester — Deploy ==="

# Install system deps if needed
if ! command -v python3 &>/dev/null; then
    echo "Installing Python3..."
    apt-get update && apt-get install -y python3 python3-pip python3-venv
fi

# Clone or update repo
REPO_DIR="/opt/grid-backtest"
if [ -d "$REPO_DIR" ]; then
    echo "Updating repo..."
    cd "$REPO_DIR" && git pull
else
    echo "Cloning repo..."
    git clone https://github.com/arozenfelds-hash/grid-backtest.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# Create venv and install deps
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create systemd service
echo "Setting up systemd service..."
cat > /etc/systemd/system/grid-backtest.service << 'UNIT'
[Unit]
Description=Grid Bot Backtester (Streamlit)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/grid-backtest
ExecStart=/opt/grid-backtest/venv/bin/streamlit run app.py --server.port 8503 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable grid-backtest
systemctl restart grid-backtest

echo ""
echo "=== Deployed! ==="
echo "App running on http://$(hostname -I | awk '{print $1}'):8503"
echo "Manage: systemctl {start|stop|restart|status} grid-backtest"
echo "Logs:   journalctl -u grid-backtest -f"
