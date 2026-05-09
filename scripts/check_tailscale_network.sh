#!/usr/bin/env bash
# check_tailscale_network.sh — Tailscale network topology + config analyser
#
# Physical topology:
#   aicamera1 ── [lab wifi / p102 router] ──┐
#   aicamera2 ── [p103 router]              ├── internet ── Tailscale
#   lprserver ── [direct ISP]               │
#   Mac       ── [local network]   ──────────┘
#
# p102 (100.101.102.1) = router aicamera1 connects to in PRODUCTION
# p103 (100.101.103.1) = router aicamera2 connects to (currently active)
# aicamera1 currently on lab wifi (temporary) — will move to p102
#
# Reports: Tailscale peer status, NAT type, routing path per camera,
#          direct vs DERP analysis, configuration recommendations
#
# Usage (from Mac):
#   bash scripts/check_tailscale_network.sh            # full analysis
#   bash scripts/check_tailscale_network.sh --quick    # topology only, no SSH
#   bash scripts/check_tailscale_network.sh --ssh      # + cross-node tests

set -uo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
MAGENTA='\033[0;35m'

ok()   { printf "  ${GREEN}✓${NC}  %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${NC}  %s\n" "$*"; }
fail() { printf "  ${RED}✗${NC}  %s\n" "$*"; }
info() { printf "  ${DIM}→${NC}  %s\n" "$*"; }
note() { printf "  ${BLUE}ℹ${NC}  %s\n" "$*"; }
hdr()  { printf "\n${BOLD}${CYAN}══ %s ══${NC}\n" "$*"; }

# ── Node definitions ──────────────────────────────────────────────────────────
# Camera nodes
CAM_NODES="aicamera1 aicamera2"
ALL_NODES="lprserver aicamera1 aicamera2"
ROUTER_NODES="p102 p103"

node_ip() {
  case "$1" in
    lprserver) echo "100.95.46.128"   ;;
    aicamera1) echo "100.126.178.74"  ;;
    aicamera2) echo "100.110.20.53"   ;;
    p102)      echo "100.101.102.1"   ;;
    p103)      echo "100.101.103.1"   ;;
  esac
}
node_user() {
  case "$1" in
    lprserver)        echo "lpruser"  ;;
    aicamera1|aicamera2) echo "camuser" ;;
    p102|p103)        echo "admin"    ;;
  esac
}
node_hostname() {
  case "$1" in
    lprserver) echo "lprserver.tail605477.ts.net" ;;
    aicamera1) echo "aicamera1.tail605477.ts.net" ;;
    aicamera2) echo "aicamera2.tail605477.ts.net" ;;
    p102)      echo "p102.tail605477.ts.net"      ;;
    p103)      echo "p103.tail605477.ts.net"      ;;
  esac
}
node_role() {
  case "$1" in
    lprserver) echo "Backend DB + API"                         ;;
    aicamera1) echo "Edge camera (IMX708)       [RPi5+Hailo8]" ;;
    aicamera2) echo "Edge camera (IMX708 NoIR)  [RPi5+Hailo8]" ;;
    p102)      echo "Production router for aicamera1"          ;;
    p103)      echo "Production router for aicamera2"          ;;
  esac
}
# Which router each camera connects through in production
cam_router() {
  case "$1" in
    aicamera1) echo "p102" ;;
    aicamera2) echo "p103" ;;
  esac
}
cam_router_ip() {
  case "$1" in
    aicamera1) echo "100.101.102.1" ;;
    aicamera2) echo "100.101.103.1" ;;
  esac
}

SSH_PASS="admin88366"
PING_COUNT=3
SSH_TIMEOUT=5
TS_PING_TIMEOUT=6

# ── Args ──────────────────────────────────────────────────────────────────────
QUICK=false; CROSS_SSH=false
for arg in "${@:-}"; do
  [[ "$arg" == "--quick" ]] && QUICK=true
  [[ "$arg" == "--ssh"   ]] && CROSS_SSH=true
done

# ── Issue accumulator ─────────────────────────────────────────────────────────
ISSUE_COUNT=0; ADVICE_LINES=""
issue()  { ISSUE_COUNT=$((ISSUE_COUNT+1))
           printf "  ${RED}[%d]${NC} %s\n" "$ISSUE_COUNT" "$*"; }
advice() { ADVICE_LINES="${ADVICE_LINES}${*}\n"; }

# ── SSH helpers ───────────────────────────────────────────────────────────────
# Returns: key | password | port_open | unreachable
ssh_probe() {
  local user="$1" host="$2"
  ssh -o BatchMode=yes -o ConnectTimeout=$SSH_TIMEOUT \
      -o StrictHostKeyChecking=no -o LogLevel=ERROR \
      "$user@$host" "echo ok" 2>/dev/null | grep -q ok && { echo "key"; return; }
  if command -v sshpass &>/dev/null; then
    sshpass -p "$SSH_PASS" \
      ssh -o ConnectTimeout=$SSH_TIMEOUT -o StrictHostKeyChecking=no \
          -o LogLevel=ERROR "$user@$host" "echo ok" 2>/dev/null \
      | grep -q ok && { echo "password"; return; }
  fi
  nc -z -w $SSH_TIMEOUT "$host" 22 2>/dev/null && { echo "port_open"; return; }
  echo "unreachable"
}

ssh_run() {
  local user="$1" host="$2"; shift 2
  if command -v sshpass &>/dev/null; then
    sshpass -p "$SSH_PASS" \
      ssh -o ConnectTimeout=$SSH_TIMEOUT -o StrictHostKeyChecking=no \
          -o LogLevel=ERROR "$user@$host" "$@" 2>/dev/null
  else
    ssh -o BatchMode=yes -o ConnectTimeout=$SSH_TIMEOUT \
        -o StrictHostKeyChecking=no -o LogLevel=ERROR \
        "$user@$host" "$@" 2>/dev/null
  fi
}

find_tailscale() {
  for p in /usr/local/bin/tailscale \
            "/Applications/Tailscale.app/Contents/MacOS/Tailscale" \
            "$(command -v tailscale 2>/dev/null || true)"; do
    [[ -n "$p" && -x "$p" ]] && { echo "$p"; return 0; }
  done
  return 1
}

# ── Banner ────────────────────────────────────────────────────────────────────
printf "\n${BOLD}╔══════════════════════════════════════════════════════════╗${NC}\n"
printf   "${BOLD}║  Tailscale Network Topology Analyser — PWD Vision Works  ║${NC}\n"
printf   "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}\n"
printf   "  ${DIM}%s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S %Z')"

# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Local Tailscale
# ─────────────────────────────────────────────────────────────────────────────
hdr "1. Local Tailscale"

TS_BIN="$(find_tailscale || true)"; TS_AVAILABLE=false; TS_RUNNING=false
MY_IP=""

if [[ -z "$TS_BIN" ]]; then
  fail "tailscale CLI not found"
  issue "tailscale not installed locally"
  advice "brew install tailscale"
else
  ok "binary: $TS_BIN"
  TS_AVAILABLE=true
  TS_STATUS_OUT="$("$TS_BIN" status 2>&1 || true)"
  if echo "$TS_STATUS_OUT" | grep -qiE "not running|NeedsLogin|stopped"; then
    fail "Tailscale not running / not logged in"
    issue "Tailscale daemon stopped on this Mac"
    advice "sudo tailscale up   OR   open Tailscale menu-bar app"
  else
    MY_IP="$("$TS_BIN" ip 2>/dev/null | head -1 || true)"
    MY_NAME="$("$TS_BIN" status --json 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); \
                    print(d.get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null || true)"
    ok "running — IP: ${MY_IP:-?}  name: ${MY_NAME:-?}"
    TS_RUNNING=true
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Physical + Tailscale topology diagram (static)
# ─────────────────────────────────────────────────────────────────────────────
hdr "2. Network Topology (physical + Tailscale)"

cat <<TOPO

  ${BOLD}Physical layer:${NC}

    [aicamera1] ─── lab wifi (CURRENT / temp) ──┐
    [aicamera1] ─── [p102 router] ──────────────┼── ISP ── internet
    [aicamera2] ─── [p103 router] ──────────────┘
    [lprserver] ─── dedicated ISP ──────────────── internet
    [This Mac]  ─── local network ──────────────── internet

  ${BOLD}Tailscale overlay (tail605477.ts.net):${NC}

    This Mac  (${MY_IP:-100.121.29.101})
      ├── lprserver  100.95.46.128   (direct ISP — expected: direct)
      ├── aicamera1  100.126.178.74  (lab wifi now  → p102 in prod)
      │     └── p102 router  100.101.102.1  (production path)
      └── aicamera2  100.110.20.53   (p103 router)
            └── p103 router  100.101.103.1  (offers exit node)

  ${YELLOW}⚠  aicamera1 is on temporary lab wifi.${NC}
  ${YELLOW}   In production it will route through p102 — same DERP risk applies.${NC}

TOPO

# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Tailscale peer status (all relevant nodes)
# ─────────────────────────────────────────────────────────────────────────────
hdr "3. Tailscale Peer Status"

if ! $TS_AVAILABLE || ! $TS_RUNNING; then
  warn "Tailscale not available — skipping peer status"
else
  # Parse tailscale status JSON for richer data
  TS_JSON="$("$TS_BIN" status --json 2>/dev/null || echo '{}')"

  printf "\n  %-12s %-18s %-10s %-12s %-35s\n" \
         "Name" "IP" "Status" "Mode" "Details"
  printf "  %s\n" "$(printf '%0.s─' {1..85})"

  for node in lprserver aicamera1 aicamera2 p102 p103; do
    ip="$(node_ip $node)"
    role="$(node_role $node)"

    # Extract from tailscale status output
    raw="$(echo "$TS_STATUS_OUT" | grep "$ip" | head -1 || true)"

    if [[ -z "$raw" ]]; then
      status_str="${DIM}not in tailnet${NC}"
      mode_str="${DIM}N/A${NC}"
      detail=""
    elif echo "$raw" | grep -qi "offline"; then
      status_str="${RED}offline${NC}"
      last_seen="$(echo "$raw" | grep -oE 'last seen [^,]+' | head -1 || true)"
      mode_str="${DIM}N/A${NC}"
      detail="${DIM}${last_seen}${NC}"
    elif echo "$raw" | grep -qi "active.*direct"; then
      status_str="${GREEN}active${NC}"
      mode_str="${GREEN}direct${NC}"
      detail="$(echo "$raw" | grep -oE 'direct [^,]+' | head -1 || true)"
    elif echo "$raw" | grep -qi 'relay\|DERP\|"sin"\|"tok"\|"hkg"'; then
      status_str="${GREEN}active${NC}"
      relay_name="$(echo "$raw" | grep -oE '"[a-z]+"' | head -1 | tr -d '"' || true)"
      mode_str="${YELLOW}DERP:${relay_name}${NC}"
      detail="$(echo "$raw" | grep -oE 'tx [0-9]+ rx [0-9]+' | head -1 || true)"
    elif echo "$raw" | grep -qi "idle"; then
      status_str="${YELLOW}idle${NC}"
      mode_str="${DIM}idle${NC}"
      detail="$(echo "$raw" | sed 's/.*idle/idle/' | cut -c1-35 || true)"
    else
      status_str="${DIM}unknown${NC}"
      mode_str="${DIM}?${NC}"
      detail="$(echo "$raw" | cut -c1-35)"
    fi

    printf "  %-12s %-18s ${status_str}%-4s  ${mode_str}%-6s  ${detail}%-0s\n" \
      "$node" "$ip" "" "" ""

    # Per-node additional info
    case "$node" in
      p103)
        if echo "${raw:-}" | grep -qi "exit node\|offers exit"; then
          note "p103 offers exit node — can route traffic for aicamera2"
        fi ;;
      p102)
        if echo "${raw:-}" | grep -qi "^-$\|^$"; then
          note "p102 shows no status — may not be online or in tailnet"
        fi ;;
    esac
  done
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Connectivity test (ping + tailscale ping per node)
# ─────────────────────────────────────────────────────────────────────────────
hdr "4. Connectivity Tests"

printf "\n  %-12s %-18s %-8s %-16s %-8s %s\n" \
       "Node" "IP" "ICMP" "TS Mode" "Latency" "SSH"
printf "  %s\n" "$(printf '%0.s─' {1..70})"

# Storage variables for later phases
R_PING_lprserver=""; R_PING_aicamera1=""; R_PING_aicamera2=""
R_PING_p102=""; R_PING_p103=""
R_MODE_lprserver=""; R_MODE_aicamera1=""; R_MODE_aicamera2=""
R_MODE_p102=""; R_MODE_p103=""
R_LAT_lprserver="";  R_LAT_aicamera1="";  R_LAT_aicamera2=""
R_LAT_p102=""; R_LAT_p103=""
R_SSH_lprserver="";  R_SSH_aicamera1="";  R_SSH_aicamera2=""

for node in lprserver aicamera1 aicamera2 p102 p103; do
  ip="$(node_ip $node)"
  host="$(node_hostname $node)"
  user="$(node_user $node)"

  # ICMP
  if ping -c $PING_COUNT -W 2 -q "$ip" &>/dev/null; then
    ping_ms=$(ping -c $PING_COUNT -W 2 "$ip" 2>/dev/null \
              | awk -F'/' '/avg/{printf "%.0fms", $5}' || echo "?ms")
    eval "R_PING_${node}=\"ok:${ping_ms}\""
    ping_col="${GREEN}UP${NC}"
  else
    eval "R_PING_${node}=\"fail\""
    ping_col="${RED}DOWN${NC}"
    issue "$node ($ip): unreachable via ICMP"
    case "$node" in
      p102) advice "p102: verify router is powered on and Tailscale client is running on it" ;;
      p103) advice "p103: verify router is powered on and Tailscale client is running on it" ;;
      *)    advice "$node: check device is on and Tailscale is active" ;;
    esac
  fi

  # Tailscale ping
  ts_mode="?"; ts_lat="?"
  if $TS_AVAILABLE && $TS_RUNNING; then
    ts_out="$("$TS_BIN" ping --timeout="${TS_PING_TIMEOUT}s" "$ip" 2>&1 | head -4 || true)"
    if echo "$ts_out" | grep -qi "via DERP"; then
      derp="$(echo "$ts_out" | grep -oi 'DERP([^)]*)' | head -1 || true)"
      ts_lat="$(echo "$ts_out" | grep -oE '[0-9]+ms' | head -1 || echo '?')"
      ts_mode="DERP"
      eval "R_MODE_${node}=\"relay:${derp}\""
      eval "R_LAT_${node}=\"${ts_lat}\""
      mode_col="${YELLOW}DERP ${derp}${NC}"
      issue "$node: DERP relay (${derp}) — direct P2P failed"
      case "$node" in
        aicamera2)
          advice "aicamera2/p103: configure UDP 41641 port-forward on p103 → aicamera2 IP"
          advice "aicamera2: OR run 'sudo tailscale up --accept-routes' on aicamera2 to use p103 as subnet router" ;;
        aicamera1)
          advice "aicamera1/p102: same NAT issue — configure UDP 41641 forwarding on p102 before switching from lab wifi" ;;
        p103)
          advice "p103 itself is behind DERP — check if it is behind double-NAT (carrier-grade)" ;;
      esac
    elif echo "$ts_out" | grep -qiE "pong|via [0-9]"; then
      ts_lat="$(echo "$ts_out" | grep -oE '[0-9]+ms' | head -1 || echo '?')"
      ts_mode="direct"
      eval "R_MODE_${node}=\"direct\""
      eval "R_LAT_${node}=\"${ts_lat}\""
      mode_col="${GREEN}direct${NC}"
    elif echo "$ts_out" | grep -qiE "timeout|error"; then
      eval "R_MODE_${node}=\"timeout\""
      mode_col="${RED}timeout${NC}"
      ts_lat="-"
    else
      eval "R_MODE_${node}=\"offline\""
      mode_col="${DIM}offline${NC}"
      ts_lat="-"
    fi
  else
    mode_col="${DIM}N/A${NC}"
  fi

  # SSH (skip for routers unless asked)
  ssh_col="${DIM}skip${NC}"
  if ! $QUICK && [[ "$node" != p102 && "$node" != p103 ]]; then
    ssh_res="$(ssh_probe "$user" "$host" 2>/dev/null || echo "unreachable")"
    eval "R_SSH_${node}=\"${ssh_res}\""
    case "$ssh_res" in
      key)         ssh_col="${GREEN}key${NC}" ;;
      password)    ssh_col="${GREEN}pw${NC}" ;;
      port_open)   ssh_col="${YELLOW}port✓${NC}" ;;
      unreachable) ssh_col="${RED}FAIL${NC}"
                   issue "$node: SSH port 22 unreachable"
                   advice "$node: sudo systemctl status ssh" ;;
    esac
  fi

  printf "  %-12s %-18s ${ping_col}%-4s  ${mode_col}%-8s  %-8s ${ssh_col}\n" \
    "$node" "$ip" "" "" "$ts_lat"

done

# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Camera network path analysis (via SSH)
# ─────────────────────────────────────────────────────────────────────────────
if ! $QUICK; then
  hdr "5. Camera Network Path Analysis"

  for cam in aicamera1 aicamera2; do
    router="$(cam_router $cam)"
    router_ip="$(cam_router_ip $cam)"
    cam_host="$(node_hostname $cam)"
    cam_user="$(node_user $cam)"
    eval "ssh_res=\${R_SSH_${cam}:-unreachable}"

    printf "\n  ${BOLD}%s${NC} — production router: %s (%s)\n" \
      "$cam" "$router" "$router_ip"

    if [[ "$ssh_res" == "unreachable" || "$ssh_res" == "skip" ]]; then
      warn "SSH unavailable — skipping path analysis"
      continue
    fi

    # Current default gateway
    gw="$(ssh_run "$cam_user" "$cam_host" \
      "ip route show default 2>/dev/null | awk '/default/{print \$3}' | head -1" || true)"
    if [[ -n "$gw" ]]; then
      ok "Current gateway: $gw"
      if [[ "$cam" == "aicamera1" ]]; then
        # aicamera1: check if it's on lab wifi or production router
        gw_prefix="${gw%.*}"
        router_prefix="${router_ip%.*}"  # 100.101.102 (Tailscale)
        info "Note: gateway is LAN IP (lab wifi). Production gateway via p102 LAN will differ."
      fi
    else
      warn "Could not determine default gateway"
    fi

    # Current network interfaces
    ifaces="$(ssh_run "$cam_user" "$cam_host" \
      "ip -br addr show 2>/dev/null | grep -v '^lo' | grep -v 'tailscale'" || true)"
    if [[ -n "$ifaces" ]]; then
      ok "Network interfaces:"
      echo "$ifaces" | while IFS= read -r l; do info "$l"; done
    fi

    # Tailscale status on camera
    ts_local="$(ssh_run "$cam_user" "$cam_host" \
      "tailscale status 2>/dev/null | head -3" || true)"
    if [[ -n "$ts_local" ]]; then
      ok "Tailscale on $cam:"
      echo "$ts_local" | while IFS= read -r l; do info "$l"; done
    fi

    # Tailscale IP on camera
    ts_cam_ip="$(ssh_run "$cam_user" "$cam_host" \
      "tailscale ip 2>/dev/null | head -1" || true)"
    [[ -n "$ts_cam_ip" ]] && info "Camera Tailscale IP: $ts_cam_ip"

    # Check if camera can reach its production router via Tailscale
    ts_router_reach="$(ssh_run "$cam_user" "$cam_host" \
      "ping -c 2 -W 2 $router_ip >/dev/null 2>&1 && echo ok || echo fail" || true)"
    if [[ "${ts_router_reach:-fail}" == "ok" ]]; then
      ok "Can reach production router $router ($router_ip) via Tailscale"
    else
      warn "Cannot reach production router $router ($router_ip)"
      issue "$cam: cannot reach $router ($router_ip) — Tailscale ACL or router offline"
      advice "Check $router is online: tailscale ping $router_ip"
    fi

    # Check Tailscale DERP/direct status from camera's perspective
    ts_derp_check="$(ssh_run "$cam_user" "$cam_host" \
      "tailscale debug derp 2>/dev/null | head -5 || tailscale netcheck 2>/dev/null | head -10" || true)"
    if [[ -n "$ts_derp_check" ]]; then
      ok "Tailscale netcheck on $cam:"
      echo "$ts_derp_check" | while IFS= read -r l; do info "$l"; done
    fi

    # Check UDP 41641 outbound from camera
    udp_test="$(ssh_run "$cam_user" "$cam_host" \
      "timeout 3 bash -c 'echo > /dev/udp/derp.tailscale.com/41641' 2>/dev/null && echo ok || echo blocked" || echo "blocked")"
    if [[ "${udp_test:-blocked}" == "ok" ]]; then
      ok "UDP 41641 outbound: open (P2P direct should be possible)"
    else
      warn "UDP 41641 outbound: blocked or unreachable from $cam"
      issue "$cam: UDP 41641 blocked — prevents direct Tailscale connections"
      advice "$cam/$router: ensure router does not block outbound UDP 41641"
    fi

    # aicamera service
    svc="$(ssh_run "$cam_user" "$cam_host" \
      "systemctl is-active aicamera.service 2>/dev/null || echo not-found" || true)"
    case "${svc:-?}" in
      active)    ok "aicamera.service: active" ;;
      inactive)  warn "aicamera.service: stopped"
                 issue "$cam: aicamera.service is stopped"
                 advice "$cam: sudo systemctl start aicamera.service" ;;
      failed)    fail "aicamera.service: FAILED"
                 issue "$cam: aicamera.service FAILED"
                 advice "$cam: sudo journalctl -u aicamera.service -n 50 --no-pager" ;;
      not-found) info "aicamera.service: not installed" ;;
    esac
  done
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Router analysis (p102/p103)
# ─────────────────────────────────────────────────────────────────────────────
hdr "6. Router Analysis (p102 / p103)"

for router in p102 p103; do
  rip="$(node_ip $router)"
  cam="$([ "$router" = "p102" ] && echo "aicamera1" || echo "aicamera2")"
  cam_ip="$(node_ip $cam)"
  eval "r_ping=\${R_PING_${router}:-fail}"
  eval "r_mode=\${R_MODE_${router}:-?}"

  printf "\n  ${BOLD}%s${NC}  IP: %s  → serves %s (%s)\n" \
    "$router" "$rip" "$cam" "$cam_ip"

  # Online status
  case "$r_ping" in
    ok:*) ok "Reachable via ICMP: ${r_ping#ok:}" ;;
    fail) fail "Unreachable (offline or no Tailscale)"
           if [[ "$router" == "p102" ]]; then
             warn "p102 offline — aicamera1 is currently on lab wifi (OK for now)"
           else
             warn "p103 offline — aicamera2 may be connecting through different path"
           fi ;;
  esac

  # Tailscale connection mode
  case "$r_mode" in
    direct)     ok "Tailscale: direct P2P connection" ;;
    relay:*)    derp="${r_mode#relay:}"
                warn "Tailscale: DERP relay ${derp} — router itself is behind NAT"
                issue "$router: using DERP relay — double-NAT suspected"
                advice "$router: check if the router is behind carrier-grade NAT (CGNAT)"
                advice "$router: run 'tailscale netcheck' on $router for NAT type info" ;;
    timeout)    warn "Tailscale ping timed out" ;;
    offline)    warn "Node appears offline in Tailscale" ;;
    *)          info "Tailscale mode: $r_mode" ;;
  esac

  # SSH into router if possible (for config check)
  rhost="$(node_hostname $router)"
  ruser="$(node_user $router)"
  r_ssh="$(ssh_probe "$ruser" "$rhost" 2>/dev/null || echo "unreachable")"

  if [[ "$r_ssh" != "unreachable" ]]; then
    ok "SSH accessible ($r_ssh)"

    # Check for port forwarding rule
    fwd="$(ssh_run "$ruser" "$rhost" \
      "iptables -t nat -L PREROUTING -n 2>/dev/null | grep '41641\|tailscale' | head -5 \
       || firewall-cmd --list-all 2>/dev/null | grep '41641' | head -3 \
       || echo 'cannot check firewall'" 2>/dev/null || echo "cannot check firewall")"
    if echo "$fwd" | grep -q "41641"; then
      ok "UDP 41641 port-forward rule exists:"
      echo "$fwd" | while IFS= read -r l; do info "$l"; done
    else
      warn "No UDP 41641 port-forward rule found on $router"
      issue "$router: missing UDP 41641 → $cam_ip port forward"
      advice "$router: add iptables rule: iptables -t nat -A PREROUTING -p udp --dport 41641 -j DNAT --to-destination ${cam_ip}:41641"
      advice "$router: also: iptables -A FORWARD -p udp -d $cam_ip --dport 41641 -j ACCEPT"
    fi

    # Check Tailscale on router
    ts_rtr="$(ssh_run "$ruser" "$rhost" \
      "tailscale status 2>/dev/null | head -2" || true)"
    if [[ -n "$ts_rtr" ]]; then
      ok "Tailscale on $router:"
      echo "$ts_rtr" | while IFS= read -r l; do info "$l"; done
    fi

    # NAT type from router's perspective
    netcheck="$(ssh_run "$ruser" "$rhost" \
      "tailscale netcheck 2>/dev/null | grep -E 'NAT|UDP|DERP|Pref' | head -6" || true)"
    if [[ -n "$netcheck" ]]; then
      ok "Tailscale netcheck on $router:"
      echo "$netcheck" | while IFS= read -r l; do info "$l"; done
    fi
  else
    warn "SSH not accessible on $router ($rhost)"
    note "Cannot inspect router NAT/firewall config directly"
    note "Manual check needed: log into $router admin panel and verify:"
    note "  • UDP 41641 forwarded to ${cam_ip}"
    note "  • No firewall blocking outbound UDP 41641"
    note "  • Not behind carrier-grade NAT (check WAN IP vs public IP)"
  fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Cross-node reachability
# ─────────────────────────────────────────────────────────────────────────────
if $CROSS_SSH && ! $QUICK; then
  hdr "7. Cross-Node Reachability (cameras → lprserver)"
  lpr_ip="$(node_ip lprserver)"

  for cam in aicamera1 aicamera2; do
    eval "ssh_res=\${R_SSH_${cam}:-unreachable}"
    cam_user="$(node_user $cam)"
    cam_host="$(node_hostname $cam)"
    [[ "$ssh_res" == "unreachable" || "$ssh_res" == "skip" ]] && {
      warn "$cam → lprserver: cannot test (no SSH)"
      continue
    }
    result="$(ssh_run "$cam_user" "$cam_host" \
      "ping -c 2 -W 2 $lpr_ip >/dev/null 2>&1 && echo ok || echo fail" || echo "fail")"
    if [[ "${result:-fail}" == "ok" ]]; then
      ok "$cam → lprserver ($lpr_ip): reachable"
    else
      fail "$cam → lprserver ($lpr_ip): UNREACHABLE"
      issue "$cam cannot reach lprserver — check Tailscale ACLs"
      advice "Review ACL: https://login.tailscale.com/admin/acls"
    fi
  done
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 8: Full topology with connection status
# ─────────────────────────────────────────────────────────────────────────────
hdr "8. Live Topology Map"

get_icon() {
  eval "m=\${R_MODE_${1}:-?}"
  eval "p=\${R_PING_${1}:-fail}"
  case "$m" in
    direct)   echo "${GREEN}direct${NC}" ;;
    relay:*)  d="${m#relay:}"; echo "${YELLOW}DERP ${d}${NC}" ;;
    timeout)  echo "${RED}timeout${NC}" ;;
    offline)  echo "${RED}offline${NC}" ;;
    *)        [[ "$p" == fail ]] && echo "${RED}offline${NC}" || echo "${DIM}?${NC}" ;;
  esac
}

printf "\n"
printf "  ${BOLD}[Mac]${NC} ${MY_IP}  (tail605477.ts.net)\n"
printf "    │\n"
printf "    ├── $(get_icon lprserver)  ${BOLD}lprserver${NC}  100.95.46.128\n"
printf "    │     └── Backend DB + API\n"
printf "    │\n"
printf "    ├── $(get_icon aicamera1)  ${BOLD}aicamera1${NC}  100.126.178.74\n"
printf "    │     ├── ${YELLOW}NOW:${NC} lab wifi (temporary)\n"

eval "p102_status=\${R_PING_p102:-fail}"
eval "p102_mode=\${R_MODE_p102:-?}"
[[ "$p102_status" == fail ]] && p102_icon="${RED}offline${NC}" || p102_icon="$(get_icon p102)"
printf "    │     └── ${BOLD}PROD:${NC} p102 router 100.101.102.1  [${p102_icon}]\n"
printf "    │\n"
printf "    └── $(get_icon aicamera2)  ${BOLD}aicamera2${NC}  100.110.20.53\n"
printf "          └── p103 router 100.101.103.1  [$(get_icon p103)]\n"

printf "\n"
printf "  %-12s %-18s %-14s %-8s %-10s\n" \
       "Node" "IP" "Connection" "Latency" "Role"
printf "  %s\n" "$(printf '%0.s─' {1..65})"
for node in lprserver aicamera1 aicamera2 p102 p103; do
  eval "mode=\${R_MODE_${node}:-?}"
  eval "lat=\${R_LAT_${node}:-?}"
  eval "ping_r=\${R_PING_${node}:-?}"

  case "$mode" in
    direct)    mf="${GREEN}direct${NC}" ;;
    relay:*)   mf="${YELLOW}DERP relay${NC}" ;;
    timeout)   mf="${RED}timeout${NC}" ;;
    offline)   mf="${RED}offline${NC}" ;;
    *)         [[ "$ping_r" == "fail" ]] && mf="${RED}offline${NC}" || mf="${DIM}${mode}${NC}" ;;
  esac

  role_short=""
  case "$node" in
    lprserver) role_short="Backend" ;;
    aicamera1) role_short="Camera1 [lab wifi now]" ;;
    aicamera2) role_short="Camera2 [via p103]" ;;
    p102)      role_short="Router→aicamera1" ;;
    p103)      role_short="Router→aicamera2" ;;
  esac

  printf "  %-12s %-18s ${mf}%-4s  %-8s %s\n" \
    "$node" "$(node_ip $node)" "" "$lat" "$role_short"
done

# ─────────────────────────────────────────────────────────────────────────────
# Phase 9: Configuration planning
# ─────────────────────────────────────────────────────────────────────────────
hdr "9. Configuration Planning"

cat <<'PLAN'

  ── Current state ────────────────────────────────────────────────────────────
  aicamera1  lab wifi   → direct Tailscale ✅ (temporary — will break in prod)
  aicamera2  via p103   → DERP relay ⚠️  (NAT traversal failing)
  p103       idle/exit  → offers exit node (underutilised)
  p102       offline/─  → production router for aicamera1 (not yet tested)

  ── Option A: Port Forwarding on each router (recommended) ───────────────────
  Configure UDP 41641 port forward on p102 (for aicamera1) and p103 (for aicamera2).
  This enables Tailscale hole-punch → direct P2P connection.

  On p103 (for aicamera2):
    iptables -t nat -A PREROUTING -i <WAN_IF> -p udp --dport 41641 \
      -j DNAT --to-destination 192.168.x.x:41641   # replace with aicamera2 LAN IP
    iptables -A FORWARD -p udp -d 192.168.x.x --dport 41641 -j ACCEPT
    # Save: iptables-save > /etc/iptables/rules.v4

  On p102 (for aicamera1 in production):
    Same as above with aicamera1 LAN IP.

  ── Option B: Subnet Router (use p103 as Tailscale subnet router) ────────────
  p103 already "offers exit node" — can also advertise camera subnet.

  On p103:
    tailscale up --advertise-routes=192.168.x.0/24 --accept-routes
  On aicamera2:
    tailscale up --accept-routes
  In Tailscale admin: approve subnet route for p103.

  ── Option C: CGNAT workaround (if port forwarding impossible) ───────────────
  If p103 is behind carrier-grade NAT (WAN IP is RFC1918), port forwarding
  won't work. Check:
    On p103: curl ifconfig.me   vs   ip route show default
  If WAN IP ≠ public IP → CGNAT confirmed.
  Fix: request static IP from ISP, OR use Tailscale relay (accept DERP, ~120ms).

  ── Immediate next step ──────────────────────────────────────────────────────
  1. SSH into p103 and run: tailscale netcheck
     → look for "NAT type: Symmetric" or "UPnP: available"
  2. Check p103 WAN IP vs public IP to confirm/rule out CGNAT
  3. Configure port forward OR accept relay for now
  4. Before switching aicamera1 to p102 — test p102 first with same checklist

PLAN

# ─────────────────────────────────────────────────────────────────────────────
# Phase 10: Summary
# ─────────────────────────────────────────────────────────────────────────────
hdr "10. Summary"

if [[ $ISSUE_COUNT -eq 0 ]]; then
  printf "\n  ${GREEN}${BOLD}✅  No issues found — network is healthy${NC}\n"
else
  printf "\n  ${RED}${BOLD}%d issue(s) found:${NC}\n" "$ISSUE_COUNT"
fi

printf "\n  ${YELLOW}${BOLD}Fix advice:${NC}\n\n"
printf "%b" "${ADVICE_LINES}" | while IFS= read -r line; do
  [[ -n "$line" ]] && printf "  ${YELLOW}→${NC}  %s\n" "$line"
done

printf "\n  ${DIM}Useful commands:${NC}\n"
cat <<'CMDS'
  ─────────────────────────────────────────────────────────────────────────────
  Check NAT type on router    ssh <router>  tailscale netcheck
  Check public IP             curl -s ifconfig.me
  Check Tailscale peers       tailscale status
  Test direct connection      tailscale ping <ip>   (watch for DERP vs direct)
  Router port forward test    nc -u -z <public-ip> 41641
  Approve subnet route        https://login.tailscale.com/admin/machines
  Tailscale ACL editor        https://login.tailscale.com/admin/acls
  Force re-authentication     sudo tailscale up --force-reauth
  ─────────────────────────────────────────────────────────────────────────────
CMDS

printf "\n"
[[ $ISSUE_COUNT -eq 0 ]] && exit 0 || exit 1
