#!/bin/bash
# setup_logrotate.sh — Deploy logrotate + journald config to edge cameras
# Run on each camera with: bash edge/scripts/setup_logrotate.sh
# Requires: sudo access (camuser has NOPASSWD sudo)

set -e

LOGS_DIR="/home/camuser/aicamera/edge/logs"

echo "[1/3] Installing logrotate config for gunicorn and hailort logs..."
sudo tee /etc/logrotate.d/aicamera > /dev/null << 'EOF'
/home/camuser/aicamera/edge/logs/gunicorn_access.log
/home/camuser/aicamera/edge/logs/gunicorn_error.log {
    daily
    maxsize 50M
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl kill -s USR1 aicamera_lpr.service 2>/dev/null || true
    endscript
}

/home/camuser/aicamera/edge/logs/hailort.log
/home/camuser/aicamera/edge/logs/hailort.1.log {
    weekly
    missingok
    rotate 2
    compress
    notifempty
    copytruncate
}
EOF
echo "   -> /etc/logrotate.d/aicamera written"

echo "[2/3] Setting systemd journal size limit (SystemMaxUse=200M)..."
sudo mkdir -p /etc/systemd/journald.conf.d/
sudo tee /etc/systemd/journald.conf.d/aicamera-size.conf > /dev/null << 'EOF'
[Journal]
SystemMaxUse=200M
RuntimeMaxUse=50M
EOF
sudo systemctl kill --kill-who=main -s SIGUSR2 systemd-journald 2>/dev/null || sudo systemctl restart systemd-journald
echo "   -> journald reloaded"

echo "[3/3] Installing cron jobs (daily chromium cleanup + weekly hailort backup cleanup)..."
sudo tee /etc/cron.d/aicamera-cleanup > /dev/null << 'EOF'
# Chromium kiosk stores BrowserMetrics in /tmp — not auto-cleaned, fills disk over weeks
0 3 * * * root find /tmp/chromium-kiosk/BrowserMetrics/ -type f -mtime +1 -delete 2>/dev/null; find /tmp/chromium-kiosk/BrowserMetrics/ -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null
# Keep only 3 most-recent hailort backup logs
30 3 * * 0 camuser ls -t /home/camuser/aicamera/edge/logs/hailort_backup_*.log 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null
EOF
echo "   -> /etc/cron.d/aicamera-cleanup written"

echo ""
echo "Done. Verify with:"
echo "  sudo logrotate --debug /etc/logrotate.d/aicamera"
echo "  journalctl --disk-usage"
echo "  df -h /"
