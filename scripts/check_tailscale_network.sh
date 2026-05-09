#!/usr/bin/env bash
# check_tailscale_network.sh — Tailscale network topology checker
#
# Tests connectivity: Mac ↔ lprserver ↔ aicamera1 ↔ aicamera2
# Reports: online status, direct vs DERP relay, latency, SSH reachability
# Advises on specific fixes for degraded connections
#
# Usage (from Mac):
#   bash scripts/check_tailscale_network.sh            # full check (ping + tailscale + SSH + services)
#   bash scripts/check_tailscale_network.sh --quick    # ping + tailscale only, no SSH
#   bash scripts/check_tailscale_network.sh --ssh      # also test cross-node connectivity

# bash 3.2 compatible (macOS default shell)
set -uo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

ok()   { printf "  ${GREEN}✓${NC}  %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${NC}  %s\n" "$*"; }
fail() { printf "  ${RED}✗${NC}  %s\n" "$*"; }
info() { printf "  ${DIM}→${NC}  %s\n" "$*"; }
hdr()  { printf "\n${BOLD}${CYAN}══ %s ══${NC}\n" "$*"; }

# ── Node config (bash 3.2 compatible — no associative arrays) ─────────────────
NODES="lprserver aicamera1 aicamera2"

node_ip() {
  case "$1" in
    lprserver) echo "100.95.46.128"  ;;
    aicamera1) echo "100.126.178.74" ;;
    aicamera2) echo "100.110.20.53"  ;;
  esac
}
node_user() {
  case "$1" in
    lprserver) echo "lpruser" ;;
    aicamera1|aicamera2) echo "camuser" ;;
  esac
}
node_hostname() {
  case "$1" in
    lprserver) echo "lprserver.tail605477.ts.net" ;;
    aicamera1) echo "aicamera1.tail605477.ts.net" ;;
    aicamera2) echo "aicamera2.tail605477.ts.net" ;;
  esac
}
node_role() {
  case "$1" in
    lprserver) echo "Backend DB + API"          ;;
    aicamera1) echo "Edge camera (IMX708)"       ;;
    aicamera2) echo "Edge camera (IMX708 NoIR)"  ;;
  esac
}

SSH_PASS="admin88366"
PING_COUNT=3
SSH_TIMEOUT=5
TS_PING_TIMEOUT=5

# ── Parse args ────────────────────────────────────────────────────────────────
QUICK=false; CROSS_SSH=false
for arg in "${@:-}"; do
  [[ "$arg" == "--quick" ]] && QUICK=true
  [[ "$arg" == "--ssh"   ]] && CROSS_SSH=true
done

# ── Results (plain strings, space-separated list) ─────────────────────────────
ISSUES=""
ADVICES=""
ISSUE_COUNT=0

issue()  { ISSUES="${ISSUES}ISSUE: $*\n"; ISSUE_COUNT=$((ISSUE_COUNT+1)); }
advice() { ADVICES="${ADVICES}ADVICE: $*\n"; }

# ── Helpers ───────────────────────────────────────────────────────────────────
find_tailscale() {
  for p in \
    /usr/local/bin/tailscale \
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale" \
    "$(command -v tailscale 2>/dev/null || true)"; do
    [[ -n "$p" && -x "$p" ]] && { echo "$p"; return 0; }
  done
  return 1
}

# Test SSH: returns "key" | "password" | "port_open" | "unreachable"
ssh_test() {
  local user="$1" host="$2"
  ssh -o BatchMode=yes \
      -o ConnectTimeout=$SSH_TIMEOUT \
      -o StrictHostKeyChecking=no \
      -o LogLevel=ERROR \
      "$user@$host" "echo ok" 2>/dev/null | grep -q ok && { echo "key"; return; }
  if command -v sshpass &>/dev/null; then
    sshpass -p "$SSH_PASS" \
      ssh -o ConnectTimeout=$SSH_TIMEOUT \
          -o StrictHostKeyChecking=no \
          -o LogLevel=ERROR \
          "$user@$host" "echo ok" 2>/dev/null | grep -q ok && { echo "password"; return; }
  fi
  nc -z -w $SSH_TIMEOUT "$host" 22 2>/dev/null && { echo "port_open"; return; }
  echo "unreachable"
}

ssh_cmd() {
  local user="$1" host="$2"; shift 2
  if command -v sshpass &>/dev/null; then
    sshpass -p "$SSH_PASS" \
      ssh -o ConnectTimeout=$SSH_TIMEOUT \
          -o StrictHostKeyChecking=no \
          -o LogLevel=ERROR \
          "$user@$host" "$@" 2>/dev/null
  else
    ssh -o BatchMode=yes \
        -o ConnectTimeout=$SSH_TIMEOUT \
        -o StrictHostKeyChecking=no \
        -o LogLevel=ERROR \
        "$user@$host" "$@" 2>/dev/null
  fi
}

# ── Banner ────────────────────────────────────────────────────────────────────
printf "\n${BOLD}╔══════════════════════════════════════════════════════╗${NC}\n"
printf   "${BOLD}║   Tailscale Network Check — PWD Vision Works         ║${NC}\n"
printf   "${BOLD}╚══════════════════════════════════════════════════════╝${NC}\n"
printf   "  ${DIM}%s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S %Z')"

# ── Phase 1: Local Tailscale ──────────────────────────────────────────────────
hdr "1. Local Tailscale"

TS_BIN="$(find_tailscale || true)"
TS_AVAILABLE=false; TS_RUNNING=false

if [[ -z "$TS_BIN" ]]; then
  fail "tailscale CLI not found"
  issue "tailscale not installed on this machine"
  advice "Install: brew install tailscale  OR  https://tailscale.com/download"
else
  ok "binary: $TS_BIN"
  TS_AVAILABLE=true

  TS_STATUS="$("$TS_BIN" status 2>&1 || true)"
  if echo "$TS_STATUS" | grep -qiE "not running|stopped|NeedsLogin|error"; then
    fail "Tailscale daemon is NOT running / not logged in"
    issue "Tailscale daemon stopped or not authenticated on local machine"
    advice "Start: open Tailscale menu bar app  OR  sudo tailscale up"
  else
    MY_IP="$("$TS_BIN" ip 2>/dev/null | head -1 || true)"
    ok "running — local Tailscale IP: ${MY_IP:-unknown}"
    TS_RUNNING=true
  fi
fi

# ── Phase 2: Per-node connectivity ───────────────────────────────────────────
hdr "2. Peer Connectivity"
printf "  %-12s %-18s %-6s %-14s %-9s %s\n" \
       "Node" "IP" "Ping" "Mode" "Latency" "SSH"
printf "  %s\n" "$(printf '%0.s─' {1..70})"

# Store per-node results for topology section
R_PING_lprserver=""; R_PING_aicamera1=""; R_PING_aicamera2=""
R_MODE_lprserver=""; R_MODE_aicamera1=""; R_MODE_aicamera2=""
R_LAT_lprserver="";  R_LAT_aicamera1="";  R_LAT_aicamera2=""
R_SSH_lprserver="";  R_SSH_aicamera1="";  R_SSH_aicamera2=""

for node in $NODES; do
  ip="$(node_ip $node)"
  user="$(node_user $node)"
  host="$(node_hostname $node)"

  # ── ICMP ping ──
  ping_ok=false; ping_ms="?"
  if ping -c $PING_COUNT -W 2 -q "$ip" &>/dev/null; then
    ping_ms=$(ping -c $PING_COUNT -W 2 "$ip" 2>/dev/null \
              | awk -F'/' '/avg/{printf "%.0f", $5}' || echo "?")
    ping_ok=true
    eval "R_PING_${node}=ok:${ping_ms}ms"
    ping_str="${GREEN}UP${NC}   "
  else
    eval "R_PING_${node}=fail"
    ping_str="${RED}DOWN${NC} "
    issue "$node ($ip): unreachable via ICMP"
    advice "$node: verify device is powered on and Tailscale is active  →  ssh $(node_user $node)@$host"
  fi

  # ── tailscale ping ──
  ts_mode="unknown"; ts_lat="?"
  if $TS_AVAILABLE && $TS_RUNNING; then
    ts_out="$("$TS_BIN" ping --timeout="${TS_PING_TIMEOUT}s" "$ip" 2>&1 | head -4 || true)"

    if echo "$ts_out" | grep -qi "via DERP"; then
      derp="$(echo "$ts_out" | grep -oi 'DERP([^)]*)' | head -1 || true)"
      ts_lat="$(echo "$ts_out" | grep -oE '[0-9]+ms' | head -1 || echo '?')"
      ts_mode="relay"
      eval "R_MODE_${node}=\"relay:${derp}\""
      eval "R_LAT_${node}=\"${ts_lat}\""
      mode_str="${YELLOW}DERP${NC} ${DIM}${derp}${NC}"
      issue "$node: using DERP relay (${derp}) — performance degraded"
      advice "$node → direct conn: ensure UDP 41641 is open outbound on both devices.  Check: $TS_BIN ping $ip"

    elif echo "$ts_out" | grep -qiE "pong|via [0-9]"; then
      ts_lat="$(echo "$ts_out" | grep -oE '[0-9]+ms' | head -1 || echo '?')"
      ts_mode="direct"
      eval "R_MODE_${node}=\"direct\""
      eval "R_LAT_${node}=\"${ts_lat}\""
      mode_str="${GREEN}direct${NC}       "

    elif echo "$ts_out" | grep -qi "timeout\|error\|not found"; then
      ts_mode="timeout"
      eval "R_MODE_${node}=timeout"
      mode_str="${RED}timeout${NC}      "
      issue "$node: tailscale ping timed out — node may be offline or peer not in tailnet"
    else
      eval "R_MODE_${node}=unknown"
      mode_str="${DIM}unknown${NC}      "
    fi
  else
    mode_str="${DIM}N/A (ts off)${NC} "
  fi

  # ── SSH test ──
  ssh_res="skip"; ssh_str="${DIM}skip${NC}"
  if ! $QUICK; then
    ssh_res="$(ssh_test "$user" "$host" 2>/dev/null || echo "unreachable")"
    eval "R_SSH_${node}=${ssh_res}"
    case "$ssh_res" in
      key)         ssh_str="${GREEN}key${NC}" ;;
      password)    ssh_str="${GREEN}pw${NC}" ;;
      port_open)   ssh_str="${YELLOW}port✓${NC}"
                   warn "$node: SSH port open but authentication failed — set up SSH key or install sshpass" ;;
      unreachable) ssh_str="${RED}FAIL${NC}"
                   issue "$node: SSH port 22 unreachable"
                   advice "$node: check sshd → ssh $user@$host 'sudo systemctl status ssh'" ;;
    esac
  fi

  printf "  %-12s %-18s ${ping_str}%-5s ${mode_str}%-4s ${ssh_str}\n" \
    "$node" "$ip" "" "" ""

done

# ── Phase 3: Raw tailscale status ────────────────────────────────────────────
if $TS_AVAILABLE && $TS_RUNNING; then
  hdr "3. tailscale status (all peers)"
  "$TS_BIN" status 2>/dev/null \
    | grep -v "^#" \
    | while IFS= read -r line; do
        for chk_ip in "100.95.46.128" "100.126.178.74" "100.110.20.53"; do
          if echo "$line" | grep -q "$chk_ip"; then
            if echo "$line" | grep -qiE "idle|active|direct"; then
              printf "  ${GREEN}●${NC} %s\n" "$line"
            else
              printf "  ${RED}○${NC} %s\n" "$line"
            fi
            continue 2
          fi
        done
        printf "  ${DIM}  %s${NC}\n" "$line"
      done
fi

# ── Phase 4: Service status via SSH ──────────────────────────────────────────
if ! $QUICK; then
  hdr "4. Remote Service Status"

  for node in $NODES; do
    user="$(node_user $node)"
    host="$(node_hostname $node)"
    eval "ssh_res=\${R_SSH_${node}:-skip}"

    printf "\n  ${BOLD}%s${NC}  —  %s\n" "$node" "$(node_role $node)"

    if [[ "$ssh_res" == "unreachable" || "$ssh_res" == "skip" ]]; then
      warn "SSH unavailable — skipping service checks"
      continue
    fi

    # Tailscale on remote
    ts_remote="$(ssh_cmd "$user" "$host" "tailscale status 2>/dev/null | head -2" || true)"
    if [[ -n "$ts_remote" ]]; then
      ok "Tailscale on $node:"
      echo "$ts_remote" | while IFS= read -r l; do info "$l"; done
    else
      warn "Cannot query Tailscale on $node"
      issue "$node: remote tailscale status unavailable"
      advice "$node: sudo systemctl status tailscaled"
    fi

    # aicamera services
    if [[ "$node" == aicamera* ]]; then
      for svc in aicamera.service; do
        state="$(ssh_cmd "$user" "$host" "systemctl is-active $svc 2>/dev/null || echo not-found" || true)"
        case "${state:-?}" in
          active)    ok "$svc: active" ;;
          inactive)  warn "$svc: inactive (stopped)"
                     issue "$node: $svc stopped"
                     advice "$node: sudo systemctl start $svc" ;;
          failed)    fail "$svc: FAILED"
                     issue "$node: $svc is in FAILED state"
                     advice "$node: sudo journalctl -u $svc -n 50 --no-pager" ;;
          not-found) info "$svc: not installed" ;;
          *)         info "$svc: ${state:-unknown}" ;;
        esac
      done

      # Hailo-8
      hailo="$(ssh_cmd "$user" "$host" \
        "hailortcli fw-control identify 2>/dev/null | grep -iE 'board|version|serial' | head -2 || echo NOT_FOUND" || true)"
      if echo "${hailo:-NOT_FOUND}" | grep -q "NOT_FOUND"; then
        warn "Hailo-8 not detected"
        issue "$node: Hailo-8 NPU not responding"
        advice "$node: hailortcli scan  OR  lspci | grep -i hailo"
      else
        ok "Hailo-8 detected:"
        echo "$hailo" | while IFS= read -r l; do info "$l"; done
      fi
    fi

    # lprserver services
    if [[ "$node" == "lprserver" ]]; then
      for svc in lprserver nginx postgresql; do
        state="$(ssh_cmd "$user" "$host" "systemctl is-active ${svc}.service 2>/dev/null || echo not-found" || true)"
        case "${state:-?}" in
          active)    ok "${svc}.service: active" ;;
          inactive)  warn "${svc}.service: inactive"
                     issue "lprserver: ${svc} stopped"
                     advice "lprserver: sudo systemctl start ${svc}" ;;
          failed)    fail "${svc}.service: FAILED"
                     issue "lprserver: ${svc} FAILED"
                     advice "lprserver: sudo systemctl restart ${svc}  then  journalctl -u ${svc} -n 50" ;;
          not-found) info "${svc}.service: not installed" ;;
          *)         info "${svc}.service: ${state:-unknown}" ;;
        esac
      done
    fi
  done
fi

# ── Phase 5: Cross-node reachability ─────────────────────────────────────────
if $CROSS_SSH && ! $QUICK; then
  hdr "5. Cross-Node Reachability (edge → server)"
  lpr_ip="$(node_ip lprserver)"

  for src in aicamera1 aicamera2; do
    eval "ssh_res=\${R_SSH_${src}:-skip}"
    src_user="$(node_user $src)"
    src_host="$(node_hostname $src)"

    if [[ "$ssh_res" == "unreachable" || "$ssh_res" == "skip" ]]; then
      warn "$src → lprserver: cannot test (no SSH to $src)"
      continue
    fi

    result="$(ssh_cmd "$src_user" "$src_host" \
      "ping -c 2 -W 2 $lpr_ip >/dev/null 2>&1 && echo ok || echo fail" || echo "fail")"
    if [[ "${result:-fail}" == "ok" ]]; then
      ok "$src → lprserver ($lpr_ip): reachable"
    else
      fail "$src → lprserver ($lpr_ip): UNREACHABLE"
      issue "$src cannot reach lprserver — Tailscale ACL may be blocking"
      advice "Check ACL policy: https://login.tailscale.com/admin/acls  — ensure aicamera* tag can reach lprserver tag"
    fi
  done
fi

# ── Phase 6: Topology diagram ─────────────────────────────────────────────────
hdr "6. Network Topology"

my_ip="$($TS_BIN ip 2>/dev/null | head -1 || echo 'N/A')"
get_mode_icon() {
  eval "m=\${R_MODE_${1}:-unknown}"
  case "$m" in
    direct)    echo "${GREEN}direct${NC}" ;;
    relay*)    echo "${YELLOW}DERP${NC}" ;;
    timeout)   echo "${RED}timeout${NC}" ;;
    *)         eval "p=\${R_PING_${1}:-?}"
               [[ "$p" == fail ]] && echo "${RED}offline${NC}" || echo "${DIM}?${NC}" ;;
  esac
}

printf "
  ${BOLD}[This Mac]${NC} %s
      │
      │  tail605477.ts.net
      │
      ├── $(get_mode_icon lprserver) ── ${BOLD}lprserver${NC} 100.95.46.128
      │                  Backend + DB
      │
      ├── $(get_mode_icon aicamera1) ── ${BOLD}aicamera1${NC} 100.126.178.74
      │                  RPi5 + Hailo-8 (IMX708)
      │
      └── $(get_mode_icon aicamera2) ── ${BOLD}aicamera2${NC} 100.110.20.53
                         RPi5 + Hailo-8 (IMX708 NoIR)

" "$my_ip"

printf "  %-12s %-18s %-12s %-10s %-10s\n" "Node" "IP" "Connection" "Latency" "SSH"
printf "  %s\n" "$(printf '%0.s─' {1..60})"
for node in $NODES; do
  eval "mode=\${R_MODE_${node}:-?}"
  eval "lat=\${R_LAT_${node}:-?}"
  eval "ssh_r=\${R_SSH_${node}:-skip}"
  eval "ping_r=\${R_PING_${node}:-?}"

  [[ "$mode" == "direct" ]]  && mf="${GREEN}direct${NC}"  || true
  [[ "$mode" == relay* ]]    && mf="${YELLOW}DERP relay${NC}"  || true
  [[ "$mode" == "timeout" ]] && mf="${RED}timeout${NC}"   || true
  [[ "$ping_r" == "fail" ]]  && mf="${RED}offline${NC}"   || true
  [[ -z "${mf:-}" ]]         && mf="${DIM}${mode}${NC}"

  [[ "$ssh_r" == "key" || "$ssh_r" == "password" ]] && sf="${GREEN}${ssh_r}${NC}" || sf="${RED}${ssh_r}${NC}"
  [[ "$ssh_r" == "port_open" ]] && sf="${YELLOW}port✓${NC}"
  [[ "$ssh_r" == "skip" ]]      && sf="${DIM}skip${NC}"

  printf "  %-12s %-18s ${mf}%-4s  %-10s ${sf}\n" \
    "$node" "$(node_ip $node)" "" "${lat}"
done

# ── Phase 7: Summary + Advice ─────────────────────────────────────────────────
hdr "7. Summary & Advice"

if [[ $ISSUE_COUNT -eq 0 ]]; then
  printf "\n  ${GREEN}${BOLD}✅  All checks passed — network is healthy${NC}\n"
else
  printf "\n  ${RED}${BOLD}⚠   %d issue(s) found:${NC}\n\n" "$ISSUE_COUNT"
  idx=1
  printf "%b" "$ISSUES" | grep "^ISSUE:" | while IFS= read -r line; do
    printf "  ${RED}[%d]${NC} %s\n" "$idx" "${line#ISSUE: }"
    idx=$((idx+1))
  done

  printf "\n  ${YELLOW}${BOLD}Recommended fixes:${NC}\n\n"
  idx=1
  printf "%b" "$ADVICES" | grep "^ADVICE:" | while IFS= read -r line; do
    printf "  ${YELLOW}[%d]${NC} %s\n" "$idx" "${line#ADVICE: }"
    idx=$((idx+1))
  done
fi

printf "\n  ${DIM}Quick reference:${NC}\n"
cat <<'QUICKREF'
  ──────────────────────────────────────────────────────────────────
  Check Tailscale daemon     sudo systemctl status tailscaled
  Re-authenticate node       sudo tailscale up --force-reauth
  Check direct vs relay      tailscale ping <ip>
  List all peers             tailscale status
  Fix DERP (open UDP port)   ensure UDP 41641 is not blocked by firewall
  Review ACLs                https://login.tailscale.com/admin/acls
  Check aicamera service     sudo journalctl -u aicamera.service -n 50 --no-pager
  ──────────────────────────────────────────────────────────────────
QUICKREF

printf "\n"
[[ $ISSUE_COUNT -eq 0 ]] && exit 0 || exit 1
