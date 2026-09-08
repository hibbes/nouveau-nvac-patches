#!/bin/bash
# nvac-boot-s3: ein prophylaktischer deep-S3-Zyklus nach dem Boot (Experiment 07.09.2026).
#
# Der EVO-Fetch-Park auf NVAC/MCP79 trifft nur den ersten vollstaendigen Display-Zyklus
# nach kaltem nouveau-Init; nach einer S3-Heilung gab es in 17/17 Faellen keinen
# Zweitwedge im selben Boot. Dieses Skript faehrt den S3 deshalb einmal kurz nach dem
# Boot, bevor jemand am Rechner sitzt. Ablauf spiegelt recover() aus
# /usr/local/bin/nvac-s3-unwedge-watchdog.py, plus Stop/Start des S3-Watchdogs drumherum.
# Spec: nouveau-nvac-patches/docs/specs/2026-09-07-nvac-boot-s3-design.md
#
# Abschalten: touch /etc/nvac-boot-s3.disabled   oder   rc-update del nvac-boot-s3 default
# Handlauf:   NBS_FORCE=1 nvac-boot-s3.sh   (uebergeht Marker, S3-Zaehler, Frischboot-Regel)
# Log: /var/log/nvac-boot-s3.log, Historie: /var/lib/nvac-boot-s3/history.log
# Alle NBS_*-Variablen dienen dem Selbsttest (tools/nvac-boot-s3/nvac-boot-s3-selftest.sh).
set -u
PATH="${NBS_PATH_PREFIX:+$NBS_PATH_PREFIX:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/sbin:/usr/bin:/bin"

MIN_UPTIME=${NBS_MIN_UPTIME:-75}        # s: labwc laeuft ab ~30 s, Plymouth geht bei ~45-60 s
DEADLINE=${NBS_DEADLINE:-240}           # s: ohne labwc bis dahin -> skip
FRESH_MAX=${NBS_FRESH_MAX:-600}         # s: spaeterer Dienststart ist kein frischer Boot
RTCWAKE_S=${NBS_RTCWAKE_S:-30}          # s: gesunder Suspend-Eintritt 1-3 s, geparkter 9-11 s
POLL=${NBS_POLL:-2}
SETTLE=${NBS_SETTLE:-10}                # s Ruhe nach dem Resume vor der Nachpruefung
NIC_GRACE=${NBS_NIC_GRACE:-5}
UPTIME_FILE=${NBS_UPTIME_FILE:-/proc/uptime}
SUCCESS_FILE=${NBS_SUSPEND_SUCCESS_FILE:-/sys/power/suspend_stats/success}
RUN_DIR=${NBS_RUN_DIR:-/run/nvac-boot-s3}
STATE_DIR=${NBS_STATE_DIR:-/var/lib/nvac-boot-s3}
LOG=${NBS_LOG:-/var/log/nvac-boot-s3.log}
DISABLE_FILE=${NBS_DISABLE_FILE:-/etc/nvac-boot-s3.disabled}
IFACE=${NBS_IFACE:-enp0s10}
GW=${NBS_GW:-192.168.1.1}
FORCE=${NBS_FORCE:-0}

log() { printf '%s %s\n' "$(date +%Y-%m-%dT%H:%M:%S)" "$*" >> "$LOG"; echo "$*"; }
uptime_s() { cut -d' ' -f1 "$UPTIME_FILE" | cut -d. -f1; }
alert() { log "alert: $*"; klaus-send --plain "nvac-boot-s3: $*" >/dev/null 2>&1 || true; }
EVO_RE='base-[0-9]: timeout|core notifier timeout'
nic_ok() { ping -c 2 -W 2 -I "$IFACE" "$GW" >/dev/null 2>&1; }

mkdir -p "$RUN_DIR" "$STATE_DIR" 2>/dev/null || true
exec 9>"$RUN_DIR/lock"
if ! flock -n 9; then
    log "skip: another instance holds $RUN_DIR/lock"
    exit 2
fi

UP=$(uptime_s)
log "start uptime=${UP}s kernel=$(uname -r) forced=$FORCE"
if [ -e "$DISABLE_FILE" ]; then
    log "skip: disabled ($DISABLE_FILE)"
    exit 0
fi
if [ "$FORCE" != 1 ]; then
    if [ -e "$RUN_DIR/done" ]; then
        log "skip: already ran this boot"
        exit 0
    fi
    S=$(cat "$SUCCESS_FILE" 2>/dev/null || echo 0)
    case "$S" in ''|*[!0-9]*) S=0 ;; esac
    if [ "$S" -gt 0 ]; then
        log "skip: S3 already happened this boot (suspend success=$S)"
        exit 0
    fi
    if [ "$UP" -gt "$FRESH_MAX" ]; then
        log "skip: not a fresh boot (uptime ${UP}s > ${FRESH_MAX}s)"
        exit 0
    fi
fi

# Warten: labwc laeuft UND Mindest-Uptime erreicht; ohne labwc bis zur Deadline -> skip.
PID=""
while :; do
    UP=$(uptime_s)
    PID=$(pgrep -x labwc 2>/dev/null | head -n1)
    if [ -n "$PID" ] && [ "$UP" -ge "$MIN_UPTIME" ]; then
        break
    fi
    if [ -z "$PID" ] && [ "$UP" -ge "$DEADLINE" ]; then
        log "skip: no compositor within ${DEADLINE}s"
        exit 0
    fi
    sleep "$POLL"
done
log "armed: labwc pid=$PID uptime=${UP}s"

# Marker VOR dem S3: ein haengender Resume darf nichts wiederholen.
touch "$RUN_DIR/done"
BASE_LINES=$(dmesg 2>/dev/null | wc -l)

RESTARTED=0
restart_watchdogs() {
    [ "$RESTARTED" = 1 ] && return 0
    RESTARTED=1
    rc-service nv-watchdog start >/dev/null 2>&1; r1=$?
    rc-service nvac-s3-unwedge start >/dev/null 2>&1; r2=$?
    log "watchdogs restarted (nv-watchdog rc=$r1, nvac-s3-unwedge rc=$r2)"
}
trap restart_watchdogs EXIT
trap 'restart_watchdogs; exit 143' TERM INT

log "S3: nvac-s3-unwedge stop -> nv-watchdog stop -> rtcwake -m mem -s $RTCWAKE_S"
rc-service nvac-s3-unwedge stop >/dev/null 2>&1
rc-service nv-watchdog stop >/dev/null 2>&1      # TCO entwaffnen, darf nicht mitten im Suspend feuern
T0=$(date +%s.%N)
timeout $((RTCWAKE_S + 120)) rtcwake -m mem -s "$RTCWAKE_S" >/dev/null 2>&1; RC=$?
DT=$(awk -v a="$T0" -v b="$(date +%s.%N)" 'BEGIN{printf "%.1f", b-a}')
log "rtcwake rc=$RC dt=${DT}s"
restart_watchdogs

# Nachpruefung: EVO-Timeouts seit der Baseline, getrennt nach VOR und NACH "PM: suspend exit".
# Ein Timeout beim Suspend-Eintritt heisst: der erste Display-Zyklus dieses Boots hat im
# Teardown des Boot-S3 geparkt, und derselbe S3 hat es geheilt (das Experiment greift).
# Nur Timeouts NACH dem Resume sind eine Anomalie.
sleep "$SETTLE"
NOW_LINES=$(dmesg 2>/dev/null | wc -l)
if [ "$NOW_LINES" -ge "$BASE_LINES" ]; then
    DELTA=$(dmesg 2>/dev/null | tail -n +$((BASE_LINES + 1)))
else
    DELTA=$(dmesg 2>/dev/null)     # Ring wurde geleert -> alles nehmen
fi
ENTRY=$(printf '%s\n' "$DELTA" | awk '/PM: suspend exit/{exit} {print}' | grep -c -E "$EVO_RE")   # Zeilen VOR dem Resume
TOTAL=$(printf '%s\n' "$DELTA" | grep -c -E "$EVO_RE")
POST=$((TOTAL - ENTRY)); [ "$POST" -lt 0 ] && POST=0
[ "$ENTRY" -gt 0 ] && log "park: consumed during suspend entry ($ENTRY timeouts before PM: suspend exit), healed by this S3"
NIC=ok
if ! nic_ok; then
    sleep "$NIC_GRACE"
    if ! nic_ok; then
        log "nic: bounce $IFACE (gateway $GW unreachable, forcedeth-S3-Falle)"
        ip link set "$IFACE" down; sleep 1; ip link set "$IFACE" up
        sleep $((NIC_GRACE * 2))
        if nic_ok; then NIC=bounced; log "nic: ok after bounce"; else NIC=fail; log "nic: FAIL after bounce"; fi
    fi
fi

log "RESULT rc=$RC dt=${DT}s evo_timeouts_entry=$ENTRY evo_timeouts_post=$POST nic=$NIC"
BOOT=$(date -d "@$(( $(date +%s) - $(uptime_s) ))" +%Y-%m-%dT%H:%M:%S 2>/dev/null || echo "?")
printf '%s boot=%s kernel=%s rc=%s dt=%ss park=%s post=%s nic=%s forced=%s\n' \
    "$(date +%Y-%m-%dT%H:%M:%S)" "$BOOT" "$(uname -r)" "$RC" "$DT" "$ENTRY" "$POST" "$NIC" "$FORCE" >> "$STATE_DIR/history.log"
[ "$RC" != 0 ] && alert "rtcwake rc=$RC dt=${DT}s, S3-Zyklus fehlgeschlagen, Waechter neu gestartet"
[ "$POST" -gt 0 ] && alert "$POST EVO-Timeouts NACH dem Resume des Boot-S3 (rc=$RC), bitte /var/log/nvac-boot-s3.log pruefen"
[ "$NIC" != ok ] && alert "NIC $IFACE nach Boot-S3: $NIC"
[ "$RC" != 0 ] && exit 1
exit 0
