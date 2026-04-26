#!/bin/bash
# =============================================================
# aicamera Project Setup Script
# PWD Vision Works — Edge AI Camera System
# Run this on your Mac to initialize the project
# =============================================================

set -e

REPO_URL="https://github.com/popwandee/aicamera.git"
PROJECT_DIR="$HOME/Documents/Claude/Projects/AICAMERA"
GIT_EMAIL="admin@pwdvisionworks.com"
GIT_NAME="PWD Vision Works"

echo "=============================================="
echo "  aicamera Project Initializer"
echo "  PWD Vision Works — Edge AI Camera System"
echo "=============================================="

# --- 1. Git identity ---
echo ""
echo "[1/5] Configuring git identity..."
git config --global user.email "$GIT_EMAIL"
git config --global user.name "$GIT_NAME"
echo "    ✓ git user: $GIT_NAME <$GIT_EMAIL>"

# --- 2. Clone or update repo ---
echo ""
echo "[2/5] Setting up repository at $PROJECT_DIR..."

if [ -d "$PROJECT_DIR/.git" ]; then
    echo "    Repository already initialized — pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "    (no remote commits yet)"
else
    # Already in the folder — init and set remote
    cd "$PROJECT_DIR"
    if [ -z "$(ls -A . | grep -v scripts | grep -v .vscode)" ]; then
        echo "    Cloning fresh..."
        git clone "$REPO_URL" tmp_clone
        cp -r tmp_clone/. .
        rm -rf tmp_clone
    fi
    git init 2>/dev/null || true
    git remote remove origin 2>/dev/null || true
    git remote add origin "$REPO_URL"
    echo "    ✓ Remote origin set to $REPO_URL"
    git fetch origin 2>/dev/null && git checkout main 2>/dev/null || git checkout master 2>/dev/null || echo "    (will commit first push)"
fi

echo "    ✓ Repository ready"

# --- 3. SSH config ---
echo ""
echo "[3/5] Setting up SSH config for Edge AI cameras..."

SSH_CONFIG="$HOME/.ssh/config"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

# Add aicamera SSH entries if not already there
if ! grep -q "aicamera2" "$SSH_CONFIG" 2>/dev/null; then
cat >> "$SSH_CONFIG" << 'SSHCONF'

# ============ PWD Vision Works — Edge AI Cameras ============
Host aicamera2
    HostName aicamera2.tail605477.ts.net
    User camuser
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
    ServerAliveInterval 30
    ServerAliveCountMax 3

Host aicamera3
    HostName aicamera3.tail605477.ts.net
    User camuser
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
    ServerAliveInterval 30
    ServerAliveCountMax 3

Host lprserver
    HostName lprserver.tail605477.ts.net
    User lpruser
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
    ServerAliveInterval 30
    ServerAliveCountMax 3
# ============================================================
SSHCONF
    echo "    ✓ SSH entries added to $SSH_CONFIG"
else
    echo "    ✓ SSH config already contains aicamera entries"
fi

chmod 600 "$SSH_CONFIG"

# --- 4. Test Tailscale SSH connectivity ---
echo ""
echo "[4/5] Testing SSH connectivity (requires Tailscale to be active)..."

for HOST in aicamera2 lprserver; do
    echo -n "    Testing $HOST ... "
    if ssh -o ConnectTimeout=6 -o BatchMode=yes -o StrictHostKeyChecking=no "$HOST" "echo ok" 2>/dev/null; then
        echo "✓ Online"
    else
        echo "✗ Unreachable (check Tailscale or device is online)"
    fi
done

# --- 5. Python virtualenv ---
echo ""
echo "[5/5] Setting up Python environment..."

cd "$PROJECT_DIR"
if [ -f "requirements.txt" ]; then
    if ! command -v python3 &>/dev/null; then
        echo "    ✗ python3 not found — install via homebrew: brew install python"
    else
        python3 -m venv .venv 2>/dev/null || true
        source .venv/bin/activate 2>/dev/null || true
        pip install -r requirements.txt -q && echo "    ✓ Python dependencies installed"
    fi
else
    echo "    (No requirements.txt found yet — skipping)"
fi

echo ""
echo "=============================================="
echo "  Setup complete! Next steps:"
echo "  1. cd $PROJECT_DIR"
echo "  2. source .venv/bin/activate   (if Python project)"
echo "  3. ssh aicamera2               (test remote camera)"
echo "  4. ssh lprserver               (test LPR server)"
echo "=============================================="
