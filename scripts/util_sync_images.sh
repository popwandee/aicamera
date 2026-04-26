#!/bin/bash

# Image sync utility: pulls image files from an edge host to the server storage
# Primary method: rsync over SSH; Fallback: SFTP (sftp/ssh) batch

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_ok()   { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_err()  { echo -e "${RED}❌ $1${NC}"; }

show_help() {
    cat << EOF
Usage: $0 [options]

Options:
  --edge-host HOST           Edge SSH/SFTP host (default: localhost)
  --edge-port PORT           SSH/SFTP port (default: 22)
  --edge-user USER           SSH/SFTP username (default: aicamera)
  --edge-pass PASS           Password for SFTP fallback (optional)
  --edge-path PATH           Remote images dir on edge (default: /home/aicamera/captured_images)
  --dest PATH                Local destination dir (default: /server/storage)
  --ssh-key PATH             SSH private key for rsync/ssh (default: ~/.ssh/id_rsa)
  --delete                   Mirror deletion (rsync --delete)
  --dry-run                  Show what would be done
  -v, --verbose              Verbose rsync/ssh output
  -h, --help                 Show this help

Environment variables (fallbacks for flags):
  EDGE_HOST, EDGE_PORT, EDGE_USER, EDGE_PASS, EDGE_PATH, SYNC_DEST, SSH_KEY
EOF
}

# Defaults
EDGE_HOST=${EDGE_HOST:-localhost}
EDGE_PORT=${EDGE_PORT:-22}
EDGE_USER=${EDGE_USER:-aicamera}
EDGE_PASS=${EDGE_PASS:-}
EDGE_PATH=${EDGE_PATH:-/home/aicamera/captured_images}
SYNC_DEST=${SYNC_DEST:-/server/storage}
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_rsa}
RSYNC_DELETE=""
DRY_RUN=""
VERBOSE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --edge-host) EDGE_HOST="$2"; shift 2;;
    --edge-port) EDGE_PORT="$2"; shift 2;;
    --edge-user) EDGE_USER="$2"; shift 2;;
    --edge-pass) EDGE_PASS="$2"; shift 2;;
    --edge-path) EDGE_PATH="$2"; shift 2;;
    --dest)      SYNC_DEST="$2"; shift 2;;
    --ssh-key)   SSH_KEY="$2"; shift 2;;
    --delete)    RSYNC_DELETE="--delete"; shift;;
    --dry-run)   DRY_RUN="--dry-run"; shift;;
    -v|--verbose) VERBOSE="-vv"; shift;;
    -h|--help)   show_help; exit 0;;
    *) log_err "Unknown option: $1"; show_help; exit 1;;
  esac
done

# Ensure destination exists
if [[ ! -d "$SYNC_DEST" ]]; then
  log_info "Creating destination directory: $SYNC_DEST"
  sudo mkdir -p "$SYNC_DEST" || mkdir -p "$SYNC_DEST"
fi

# Prefer rsync over SSH
run_rsync() {
  if ! command -v rsync >/dev/null 2>&1; then
    return 1
  fi

  local ssh_cmd="ssh -p $EDGE_PORT -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
  if [[ -f "$SSH_KEY" ]]; then
    ssh_cmd+=" -i $SSH_KEY"
  fi

  log_info "Syncing via rsync from $EDGE_USER@$EDGE_HOST:$EDGE_PATH to $SYNC_DEST"
  rsync $VERBOSE -a --partial --inplace --chmod=Du=rwx,Dg=rx,Do=rx,Fu=rw,Fg=r,Fo=r $RSYNC_DELETE $DRY_RUN \
    -e "$ssh_cmd" \
    --include='*/' --include='*.{jpg,jpeg,png,bmp,gif,tif,tiff,mp4,mov,avi}' --exclude='*' \
    "$EDGE_USER@$EDGE_HOST:$EDGE_PATH/" "$SYNC_DEST/"
}

# Fallback SFTP batch download (password-based or key-based)
run_sftp_batch() {
  if ! command -v sftp >/dev/null 2>&1; then
    return 1
  fi

  local tmp_batch
  tmp_batch=$(mktemp)

  # sftp lacks rsync's delta sync; we mirror files using mget -r
  {
    echo "cd $EDGE_PATH"
    echo "lcd $SYNC_DEST"
    echo "mget -r *"
    # no delete by default for safety
  } > "$tmp_batch"

  log_info "Syncing via SFTP from $EDGE_USER@$EDGE_HOST:$EDGE_PATH to $SYNC_DEST"

  local sftp_cmd=(sftp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P "$EDGE_PORT")
  if [[ -f "$SSH_KEY" ]]; then
    sftp_cmd+=(-i "$SSH_KEY")
  fi

  if [[ -n "$EDGE_PASS" ]] && command -v sshpass >/dev/null 2>&1; then
    SSHPASS="$EDGE_PASS" sshpass -e "${sftp_cmd[@]}" "$EDGE_USER@$EDGE_HOST" < "$tmp_batch"
  else
    "${sftp_cmd[@]}" "$EDGE_USER@$EDGE_HOST" < "$tmp_batch"
  fi

  rm -f "$tmp_batch"
}

main() {
  # Try rsync first
  if run_rsync; then
    log_ok "Rsync transfer completed"
    exit 0
  else
    log_warn "Rsync not available or failed. Falling back to SFTP."
  fi

  if run_sftp_batch; then
    log_ok "SFTP transfer completed"
    exit 0
  else
    log_err "Both rsync and SFTP methods failed"
    exit 2
  fi
}

main "$@"


