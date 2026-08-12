#!/bin/bash
# KONTROLLVERSUCH zu labwc-kill-trace.sh.
#
# Frage: ueberlebt der Compositor einen nouveau-Kanal-Kill, wenn der eigene
# Waechter nouveau-chankill-watch NICHT dazwischenfunkt? Wenn ja, ist die
# nv04-FIFO-Serie vom Vorwurf entlastet, sie nehme den Compositor mit.
#
# Unterschied zum ersten Lauf:
#   * /etc/nouveau-chankill-watch.dryrun wird gesetzt (Waechter protokolliert nur)
#   * Lebendigkeit wird per wlopm geprueft, nicht nur per pgrep: ein Zombie-labwc
#     stuende sonst in der Prozessliste und saehe wie ein Erfolg aus
#   * D-State- und Fence-Wait-Zaehler, weil der alte Freeze sich so zeigte
#
# Der Trockenlauf-Schalter wird am Ende IMMER wieder entfernt (trap).
set -u
T=/sys/kernel/tracing
DRY=/etc/nouveau-chankill-watch.dryrun
TS=$(date +%Y%m%dT%H%M%S)
D=/home/neo/nvac-v2-qa/labwc-control-$TS
mkdir -p "$D"
LOG="$D/run.log"

say() { echo "$(date '+%T.%3N') $*" | tee -a "$LOG"; }
w()   { echo "$2" | sudo -n tee "$T/$1" >/dev/null; }

cleanup() {
  sudo -n rm -f "$DRY" 2>/dev/null
  say "AUFRAEUMEN: Trockenlauf-Schalter entfernt, Waechter wieder scharf: $([ -e "$DRY" ] && echo NEIN || echo ja)"
}
trap cleanup EXIT

export XDG_RUNTIME_DIR=/run/user/1000
export WAYLAND_DISPLAY=$(ls /run/user/1000/ 2>/dev/null | grep -E '^wayland-[0-9]+$' | head -1)

# Lebendigkeit: antwortet der Compositor noch auf dem Wayland-Socket?
alive() {
  if timeout 5 wlopm >/dev/null 2>&1; then echo "ANTWORTET"; else echo "keine Antwort"; fi
}
state() {
  say "$1  labwc=$(pgrep -x labwc | tr '\n' ',') Xwayland=$(pgrep -x Xwayland | tr '\n' ',') fbo=$(pgrep -x fbo-stress | tr '\n' ',')"
  say "     wlopm=$(alive)  D-State=$(ps -eo stat | awk '$1 ~ /^D/' | wc -l)  fence_wait=$(ps -eo comm,wchan:40 | grep -c dma_fence_default_wait)"
}

say "=== KONTROLLVERSUCH $TS, Kernel $(uname -r) ==="
say "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"

# ---------- Waechter entschaerfen ----------
sudo -n touch "$DRY"
say "Trockenlauf-Schalter gesetzt: $([ -e "$DRY" ] && echo ja || echo NEIN)"
say "Waechter-PID: $(pgrep -f nouveau-chankill-watch.py | tr '\n' ',')  (kein Neustart noetig, er prueft die Datei beim Zuschlagen)"

state "VORHER"

# ---------- Tracer ----------
w tracing_on 0
sudo -n sh -c ": > $T/trace"
w 'events/signal/signal_generate/filter' 'comm == "labwc" || comm == "Xwayland" || comm == "fbo-stress"'
w 'events/signal/signal_generate/enable' 1
w tracing_on 1
sudo -n setsid sh -c "cat $T/trace_pipe > $D/trace.txt 2>&1" </dev/null >/dev/null 2>&1 &
sleep 2
say "Tracer scharf, Leser abgekoppelt"

# ---------- Opfer ----------
cd /home/neo/nvac-v2-qa || exit 1
env -u DISPLAY -u WAYLAND_DISPLAY EGL_PLATFORM=surfaceless setsid ./fbo-stress > "$D/fbo.log" 2>&1 &
sleep 6
FB=$(pgrep -x fbo-stress | head -1)
[ -z "${FB:-}" ] && { say "ABBRUCH: fbo-stress laeuft nicht"; head -3 "$D/fbo.log" >> "$LOG"; exit 1; }
say "fbo-stress surfaceless PID $FB (eigener DRM-Client)"

echo 1 | sudo -n tee /sys/module/nouveau/parameters/fifo_inject_list >/dev/null
sleep 2
CH=$(sudo -n dmesg | grep -oE "inject:   ch +[0-9]+ \[fbo-stress\[$FB\]\]" | tail -1 \
     | grep -oE 'ch +[0-9]+' | grep -oE '[0-9]+')
[ -z "${CH:-}" ] && { say "ABBRUCH: kein Kanal fuer PID $FB"; kill "$FB" 2>/dev/null; exit 1; }
case "$CH" in 1|2|3) say "ABBRUCH: ch $CH gehoert nicht dem Opfer"; kill "$FB" 2>/dev/null; exit 1;; esac
[ "$CH" -lt 128 ] 2>/dev/null || { say "ABBRUCH: $CH keine plausible chid"; kill "$FB" 2>/dev/null; exit 1; }
say "Opferkanal $CH gehoert PID $FB"

# ---------- Injektion ----------
say ">>> INJEKTION 3x auf ch $CH"
for i in 1 2 3; do echo "$CH" | sudo -n tee /sys/module/nouveau/parameters/fifo_inject_chid >/dev/null; sleep 1; done

prev=0
for t in 5 10 20 40 70 100; do
  sleep $((t - prev)); prev=$t
  state "+${t}s"
done

say "--- Kernel-Seite ---"
sudo -n dmesg -T | grep -E "ch $CH fault|errored - disabling|channel $CH killed|segfault" | tail -6 | sed 's/^/           /' >> "$LOG"
say "--- Waechter-Log (muss DRYRUN zeigen) ---"
sudo -n tail -4 /var/log/nouveau-chankill-watch.log | sed 's/^/           /' >> "$LOG"

w tracing_on 0
sleep 1
sudo -n pkill -f "cat $T/trace_pipe" 2>/dev/null
w 'events/signal/signal_generate/enable' 0
sudo -n chown -R neo:neo "$D" 2>/dev/null
say "Signale an labwc/Xwayland waehrend des Laufs: $(grep -c 'comm=labwc\|comm=Xwayland' "$D/trace.txt" 2>/dev/null || echo 0)"
say "=== FERTIG. Ergebnisse in $D ==="
