#!/bin/bash
# Selbsttest fuer nvac-boot-s3.sh: faehrt die Entscheidungslogik gegen gefaelschte
# Kommandos (Shims in einem Tempverzeichnis). Kein root noetig, kein echtes S3.
# Aufruf: bash nvac-boot-s3-selftest.sh [pfad/zu/nvac-boot-s3.sh]
set -u
SCRIPT="${1:-$(dirname "$0")/nvac-boot-s3.sh}"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }

if [ ! -f "$SCRIPT" ]; then
  echo "FAIL: Skript $SCRIPT fehlt"; echo "RESULT: 0 pass, 1 fail"; exit 1
fi

mk_env() {
  # $1 = uptime, $2 = suspend success count
  T=$(mktemp -d); export T
  mkdir -p "$T/bin" "$T/run" "$T/state"
  echo "$1 0" > "$T/uptime"
  echo "$2" > "$T/success"
  : > "$T/calls.log"
  echo 0 > "$T/ping.fails"
  echo 0 > "$T/dmesg.calls"
  export FAKE_LABWC=1 FAKE_BUMP=0 FAKE_RTCWAKE_RC=0 FAKE_DMESG_TIMEOUTS_AFTER=0 FAKE_DMESG_TIMEOUTS_ENTRY=0
  cat > "$T/bin/pgrep" <<'S'
#!/bin/bash
echo "pgrep $*" >> "$T/calls.log"
if [ "$FAKE_BUMP" != "0" ]; then u=$(cut -d' ' -f1 "$T/uptime"); echo "$((u+FAKE_BUMP)) 0" > "$T/uptime"; fi
[ "$FAKE_LABWC" = "1" ] && { echo 4482; exit 0; }
exit 1
S
  cat > "$T/bin/rc-service" <<'S'
#!/bin/bash
echo "rc-service $*" >> "$T/calls.log"; exit 0
S
  cat > "$T/bin/rtcwake" <<'S'
#!/bin/bash
m=no; [ -e "$T/run/done" ] && m=yes
echo "rtcwake $* marker=$m" >> "$T/calls.log"; exit "$FAKE_RTCWAKE_RC"
S
  cat > "$T/bin/dmesg" <<'S'
#!/bin/bash
n=$(cat "$T/dmesg.calls"); n=$((n+1)); echo "$n" > "$T/dmesg.calls"
echo "dmesg call=$n" >> "$T/calls.log"
echo "[  1.000000] nouveau 0000:02:00.0: NVIDIA MCP79/MCP7A (0ac080b1)"
if [ "$n" -ge 2 ]; then
  for i in $(seq 1 "${FAKE_DMESG_TIMEOUTS_ENTRY:-0}"); do echo "[ 79.$i] nouveau 0000:02:00.0: drm: core notifier timeout"; done
  echo "[ 86.6] PM: suspend exit"
  for i in $(seq 1 "$FAKE_DMESG_TIMEOUTS_AFTER"); do echo "[ 90.$i] nouveau 0000:02:00.0: drm: base-1: timeout"; done
fi
exit 0
S
  cat > "$T/bin/ping" <<'S'
#!/bin/bash
echo "ping $*" >> "$T/calls.log"
f=$(cat "$T/ping.fails"); if [ "$f" -gt 0 ]; then echo $((f-1)) > "$T/ping.fails"; exit 1; fi; exit 0
S
  cat > "$T/bin/ip" <<'S'
#!/bin/bash
echo "ip $*" >> "$T/calls.log"; exit 0
S
  cat > "$T/bin/klaus-send" <<'S'
#!/bin/bash
echo "klaus-send $*" >> "$T/calls.log"; exit 0
S
  chmod +x "$T"/bin/*
  export NBS_PATH_PREFIX="$T/bin" NBS_UPTIME_FILE="$T/uptime" NBS_SUSPEND_SUCCESS_FILE="$T/success"
  export NBS_RUN_DIR="$T/run" NBS_STATE_DIR="$T/state" NBS_LOG="$T/log" NBS_DISABLE_FILE="$T/disabled"
  export NBS_POLL=0.01 NBS_SETTLE=0 NBS_NIC_GRACE=0 NBS_MIN_UPTIME=75 NBS_DEADLINE=240 NBS_FRESH_MAX=600 NBS_RTCWAKE_S=30
  export NBS_IFACE=enp0s10 NBS_GW=192.168.1.1
  unset NBS_FORCE
}
run() { timeout 20 bash "$SCRIPT" >/dev/null 2>&1; RC=$?; [ "$RC" = 124 ] && echo "  (timeout: Skript hing 20 s)"; }
calls() { grep -v -E '^(pgrep|dmesg)' "$T/calls.log"; }
has_log() { grep -q -- "$1" "$T/log"; }

echo "== nvac-boot-s3 selftest gegen $SCRIPT"

# 1 Sperrdatei
mk_env 80 0; touch "$T/disabled"; run
has_log "skip: disabled" && [ -z "$(calls)" ] && ok "disabled_file_skips" || fail "disabled_file_skips"
rm -rf "$T"

# 2 Marker
mk_env 80 0; touch "$T/run/done"; run
has_log "skip: already ran" && [ -z "$(calls)" ] && ok "done_marker_skips" || fail "done_marker_skips"
rm -rf "$T"

# 3 frueheres S3 in diesem Boot
mk_env 80 1; run
has_log "skip: S3 already happened" && [ -z "$(calls)" ] && ok "prior_s3_skips" || fail "prior_s3_skips"
rm -rf "$T"

# 4 kein frischer Boot
mk_env 900 0; run
has_log "skip: not a fresh boot" && [ -z "$(calls)" ] && ok "stale_boot_skips" || fail "stale_boot_skips"
rm -rf "$T"

# 5 kein Compositor bis Deadline
mk_env 300 0; export FAKE_LABWC=0; run
has_log "skip: no compositor" && ! grep -q rtcwake "$T/calls.log" && ok "no_compositor_skips" || fail "no_compositor_skips"
rm -rf "$T"

# 6 Happy Path: exakte Reihenfolge, RESULT, Marker, Historie, kein Telegram
mk_env 80 0; run
EXP="rc-service nvac-s3-unwedge stop
rc-service nv-watchdog stop
rtcwake -m mem -s 30 marker=yes
rc-service nv-watchdog start
rc-service nvac-s3-unwedge start
ping -c 2 -W 2 -I enp0s10 192.168.1.1"
[ "$(calls)" = "$EXP" ] && ok "happy_path_sequence" || { fail "happy_path_sequence"; echo "--- got:"; calls; }
[ "$RC" = 0 ] && has_log "RESULT rc=0 " && has_log "evo_timeouts_entry=0 evo_timeouts_post=0" && has_log "nic=ok" && ok "happy_path_result_line" || fail "happy_path_result_line"
[ -e "$T/run/done" ] && ok "happy_path_marker_exists" || fail "happy_path_marker_exists"
[ "$(wc -l < "$T/state/history.log")" = 1 ] && grep -q "rc=0 .*park=0 post=0" "$T/state/history.log" && ok "happy_path_history_line" || fail "happy_path_history_line"
! grep -q klaus-send "$T/calls.log" && ok "happy_path_no_telegram" || fail "happy_path_no_telegram"
rm -rf "$T"

# 7 wartet auf Mindest-Uptime (pgrep-Shim laesst die Uptime je Poll um 30 s wachsen)
mk_env 40 0; export FAKE_BUMP=30; run
grep -q rtcwake "$T/calls.log" && grep -q -E "armed:.*uptime=(7[5-9]|[89][0-9]|1[0-9][0-9])" "$T/log" && ok "waits_for_min_uptime" || { fail "waits_for_min_uptime"; cat "$T/log"; }
rm -rf "$T"

# 8 rtcwake-Fehler: Waechter trotzdem wieder starten, Alarm, Exit 1
mk_env 80 0; export FAKE_RTCWAKE_RC=1; run
c=$(calls)
echo "$c" | grep -q "rc-service nv-watchdog start" && echo "$c" | grep -q "rc-service nvac-s3-unwedge start" && ok "rtcwake_failure_restarts_watchdogs" || fail "rtcwake_failure_restarts_watchdogs"
has_log "RESULT rc=1 " && grep -q "klaus-send" "$T/calls.log" && [ "$RC" = 1 ] && ok "rtcwake_failure_alerts_and_exit1" || fail "rtcwake_failure_alerts_and_exit1"
rm -rf "$T"

# 9 NIC-Ausfall: zweimal Fehl-Ping, dann Bounce, dann ok
mk_env 80 0; echo 2 > "$T/ping.fails"; run
c=$(calls)
echo "$c" | grep -q "ip link set enp0s10 down" && echo "$c" | grep -q "ip link set enp0s10 up" && has_log "nic: bounce" && has_log "nic=bounced" && grep -q klaus-send "$T/calls.log" && ok "nic_failure_bounces_link" || { fail "nic_failure_bounces_link"; calls; cat "$T/log"; }
rm -rf "$T"

# 10 EVO-Timeouts nach dem Resume: zaehlen + Alarm
mk_env 80 0; export FAKE_DMESG_TIMEOUTS_AFTER=2; run
has_log "evo_timeouts_post=2" && grep -q klaus-send "$T/calls.log" && ok "evo_timeouts_after_resume_alert" || { fail "evo_timeouts_after_resume_alert"; cat "$T/log"; }
rm -rf "$T"

# 10b Park beim Suspend-Eintritt (vor PM: suspend exit) = konsumiert, kein Alarm
mk_env 80 0; export FAKE_DMESG_TIMEOUTS_ENTRY=1; run
has_log "park: consumed during suspend entry" && has_log "evo_timeouts_entry=1 evo_timeouts_post=0" && grep -q "park=1 post=0" "$T/state/history.log" && ! grep -q klaus-send "$T/calls.log" && [ "$RC" = 0 ] && ok "park_consumed_at_entry_no_alert" || { fail "park_consumed_at_entry_no_alert"; cat "$T/log"; }
rm -rf "$T"

# 11 FORCE uebergeht Frischboot, S3-Zaehler und Marker, nicht die Sperrdatei
mk_env 900 1; touch "$T/run/done"; NBS_FORCE=1 run
grep -q rtcwake "$T/calls.log" && has_log "forced=1" && ok "force_bypasses_guards" || { fail "force_bypasses_guards"; cat "$T/log"; }
rm -rf "$T"
mk_env 80 0; touch "$T/disabled"; NBS_FORCE=1 run
has_log "skip: disabled" && ! grep -q rtcwake "$T/calls.log" && ok "force_respects_disable_file" || fail "force_respects_disable_file"
rm -rf "$T"

# 12 Lock: zweite Instanz beendet sich mit Exit 2
mk_env 80 0
( flock -x 9; sleep 1 ) 9>"$T/run/lock" &
sleep 0.2; run
[ "$RC" = 2 ] && has_log "skip: another instance" && ok "lock_prevents_double_run" || { fail "lock_prevents_double_run (rc=$RC)"; cat "$T/log"; }
wait; rm -rf "$T"

echo "RESULT: $PASS pass, $FAIL fail"
[ "$FAIL" = 0 ]
