#!/bin/bash
# =============================================================
# Deploy project files to Edge AI Cameras via rsync over SSH
# PWD Vision Works — aicamera project
# =============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_PATH="/home/camuser/aicamera"

CAMERAS=("aicamera2")   # aicamera1 and aicamera3 are offline
LPR_SERVER="lprserver"
LPR_PATH="/home/lpruser/aicamera"

EXCLUDE="--exclude=.git --exclude=.venv --exclude=__pycache__ \
         --exclude=*.pyc --exclude=.DS_Store --exclude=.vscode"

echo "================================================"
echo "  aicamera Deploy Script — PWD Vision Works"
echo "================================================"
echo "  Source: $PROJECT_DIR"
echo ""

# Deploy to AI cameras
for CAM in "${CAMERAS[@]}"; do
    echo -n "  Deploying to $CAM ... "
    if rsync -avz $EXCLUDE -e "ssh -o ConnectTimeout=8" \
        "$PROJECT_DIR/" "$CAM:$REMOTE_PATH/" 2>/dev/null; then
        echo "✓ Done"
    else
        echo "✗ Failed (is $CAM reachable on Tailscale?)"
    fi
done

# Deploy to LPR server
echo -n "  Deploying to lprserver ... "
if rsync -avz $EXCLUDE -e "ssh -o ConnectTimeout=8" \
    "$PROJECT_DIR/" "$LPR_SERVER:$LPR_PATH/" 2>/dev/null; then
    echo "✓ Done"
else
    echo "✗ Failed (is lprserver reachable on Tailscale?)"
fi

echo ""
echo "  Deploy complete."
