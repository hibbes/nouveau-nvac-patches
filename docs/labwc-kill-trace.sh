#!/bin/bash
# Klaert die seit 2026-08-06 offene Frage: WER beendet labwc, wenn ein
# nouveau-Kanal getoetet wird, der labwc gar nicht gehoert?
#
# Aufbau: ftrace auf signal:signal_generate (nennt Sender UND Ziel) plus
# sched:sched_process_exit (nennt den Exit-Code). Opfer ist ein surfaceless
# fbo-stress mit EIGENEM DRM-Client, also ausdruecklich nicht Xwayland.
#
# Alles abgekoppelt und ausserhalb von /tmp, damit der Sitzungsabriss weder
# den Lauf noch das Ergebnis mitnimmt.
set -u
T=/sys/kernel/tracing
TS=$(date +%Y%m%dT%H%M%S)
D=/home/neo/nvac-v2-qa/labwc-kill-$TS
mkdir -p "$D"
LOG="$D/run.log"

say() { echo "$(date '+%T.%3N') $*" | tee -a "$LOG"; }
w()   { echo "$2" | sudo -n tee "$T/$1" >/dev/null; }

say "=== labwc-Kill-Trace $TS, Kernel $(uname -r) ==="
LB=$(pgrep -x labwc | head -1)
XW=$(pgrep -x Xwayland | head -1)
say "labwc=$LB  Xwayland=${XW:-keiner}  greetd=$(pgrep -x greetd | tr '\n' ',')"
say "labwc PPID=$(ps -o ppid= -p "$LB" | tr -d ' ') ($(ps -o comm= -p "$(ps -o ppid= -p "$LB" | tr -d ' ')"))"

# ---------- Tracer schaerfen ----------
w tracing_on 0
sudo -n sh -c ": > $T/trace"
w 'events/signal/signal_generate/filter' 'comm == "labwc" || comm == "Xwayland" || comm == "fbo-stress"'
w 'events/signal/signal_generate/enable' 1
w 'events/signal/signal_deliver/filter'  'comm == "labwc" || comm == "Xwayland"'
w 'events/signal/signal_deliver/enable'  1
if [ -d "$T/events/sched/sched_process_exit" ]; then
  w 'events/sched/sched_process_exit/filter' 'comm == "labwc" || comm == "Xwayland" || comm == "fbo-stress"'
  w 'events/sched/sched_process_exit/enable' 1
fi
w tracing_on 1
say "Tracer scharf: $(sudo -n cat $T/events/signal/signal_generate/enable) / Filter gesetzt"

# ---------- Leser abkoppeln, damit er den Abriss ueberlebt ----------
sudo -n setsid sh -c "cat $T/trace_pipe > $D/trace.txt 2>&1" </dev/null >/dev/null 2>&1 &
sleep 2
say "trace_pipe-Leser laeuft (PID-Gruppe abgekoppelt)"

# ---------- Opfer starten: surfaceless, eigener DRM-Client ----------
cd /home/neo/nvac-v2-qa || exit 1
env -u DISPLAY -u WAYLAND_DISPLAY EGL_PLATFORM=surfaceless setsid ./fbo-stress \
    > "$D/fbo.log" 2>&1 &
sleep 6
FB=$(pgrep -x fbo-stress | head -1)
if [ -z "${FB:-}" ]; then
  say "ABBRUCH: fbo-stress laeuft nicht"; head -3 "$D/fbo.log" | tee -a "$LOG"; exit 1
fi
say "fbo-stress surfaceless PID $FB (eigener DRM-Client, NICHT ueber Xwayland)"

# ---------- Opferkanal zweistufig und mit Plausibilitaetsprobe ----------
echo 1 | sudo -n tee /sys/module/nouveau/parameters/fifo_inject_list >/dev/null
sleep 2
sudo -n dmesg -T | grep 'fifo: inject:   ch' | tail -8 | sed 's/^/           /' >> "$LOG"
CH=$(sudo -n dmesg | grep -oE "inject:   ch +[0-9]+ \[fbo-stress\[$FB\]\]" | tail -1 \
     | grep -oE 'ch +[0-9]+' | grep -oE '[0-9]+')
if [ -z "${CH:-}" ]; then say "ABBRUCH: kein Kanal fuer PID $FB"; kill "$FB" 2>/dev/null; exit 1; fi
case "$CH" in 1|2|3) say "ABBRUCH: ch $CH gehoert nicht dem Opfer"; kill "$FB" 2>/dev/null; exit 1;; esac
[ "$CH" -lt 128 ] 2>/dev/null || { say "ABBRUCH: $CH keine plausible chid"; kill "$FB" 2>/dev/null; exit 1; }
say "Opferkanal $CH gehoert PID $FB"

# ---------- Injektion ----------
say ">>> INJEKTION 3x auf ch $CH"
for i in 1 2 3; do echo "$CH" | sudo -n tee /sys/module/nouveau/parameters/fifo_inject_chid >/dev/null; sleep 1; done

# ---------- Nachbeobachtung ----------
prev=0
for t in 3 8 15 30 45 60; do
  sleep $((t - prev)); prev=$t
  say "+${t}s labwc=$(pgrep -x labwc | tr '\n' ',') Xwayland=$(pgrep -x Xwayland | tr '\n' ',') fbo=$(pgrep -x fbo-stress | tr '\n' ',')"
done

say "--- Kernel-Seite ---"
sudo -n dmesg -T | grep -E "ch $CH fault|errored - disabling|channel $CH killed|segfault" | tail -6 | sed 's/^/           /' >> "$LOG"

# ---------- Tracer abruesten ----------
w tracing_on 0
sleep 1
sudo -n pkill -f "cat $T/trace_pipe" 2>/dev/null
w 'events/signal/signal_generate/enable' 0
w 'events/signal/signal_deliver/enable'  0
[ -d "$T/events/sched/sched_process_exit" ] && w 'events/sched/sched_process_exit/enable' 0
sudo -n chown -R neo:neo "$D" 2>/dev/null

say "=== FERTIG. Ergebnisse in $D ==="
say "Trace-Zeilen: $(wc -l < "$D/trace.txt" 2>/dev/null || echo 0)"
