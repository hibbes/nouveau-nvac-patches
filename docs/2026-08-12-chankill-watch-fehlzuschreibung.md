# Der Compositor-Abschuss kam vom eigenen Wächter, nicht von der Patchserie

**Datum:** 2026-08-12
**Folge:** der Sperrgrund für die nv04-FIFO-v3-Serie ist hinfällig
**Kurzfassung:** Vier Injektionsläufe schienen zu belegen, dass ein Kanal-Kill den
Wayland-Compositor mitnimmt, sogar wenn der getötete Kanal einem unbeteiligten
Prozess gehört. Das war **falsch zugeschrieben**. Ein lokaler Wächter hat labwc
abgeschossen, nicht der Kernel.

## Wie es dazu kam, chronologisch

| Datum | Ereignis |
|---|---|
| 2026-06-02, 2026-07-22 | v1-Verhalten (Kill beim ersten Fault) tötet zweimal **wirklich** den Compositor, weil der PFIFO-Puller den falschen Kanal benennt. Echt, und der Grund für die Eskalationsleiter in v2. |
| **2026-07-25** | `nouveau-chankill-watch` wird installiert. Zweck laut eigenem Kommentar: nach einem Kanal-Kill kann labwc wegen fehlender GL-Robustness in Mesa-nv50 zum **Zombie** werden, deshalb labwc beenden und greetd übernehmen lassen. Er matcht auf **jede** `channel N killed!`-Zeile, ohne den Besitzer zu prüfen. |
| 2026-08-06 | Vier Injektionsläufe. In allen vier stirbt der Compositor. Läufe 3 und 4 haben ein **surfaceless** Opfer mit eigenem DRM-Client, also ausdrücklich nicht Xwayland, und trotzdem reißt es die Sitzung mit. Schlussfolgerung damals: die Serie hat einen viel größeren Wirkungsradius als gedacht. **v3 wird zurückgehalten.** |
| 2026-08-12 | ftrace auf `signal:signal_generate` nennt den Sender. Es ist der Wächter. |

## Der Beweis

```
fbo-stress-76295  4563.643489: signal_generate: sig=11 code=1 comm=fbo-stress pid=76295
python3-5378      4563.682828: signal_generate: sig=15 code=0 comm=labwc      pid=4141 grp=1
```

39 ms nach dem SIGSEGV des Opfers geht ein SIGTERM an labwc. `code=0` ist `SI_USER`,
also ein bewusster `kill(2)` aus dem Userspace, **nicht** der Kernel. PID 5378 war
`/usr/local/sbin/nouveau-chankill-watch.py`.

Sein eigenes Log zeigt alle sechs Auslösungen, darunter genau die vier vom 06.08.:

```
2026-07-25 21:28:40  Xwayland[4931]:     channel 5 killed!
2026-08-06 13:22:43  Xwayland[5660]:     channel 5 killed!
2026-08-06 13:29:00  Xwayland[63924]:    channel 5 killed!
2026-08-06 14:38:37  fbo-stress[143959]: channel 4 killed!
2026-08-06 14:59:48  fbo-stress[17135]:  channel 5 killed!
2026-08-12 13:49:41  fbo-stress[76295]:  channel 5 killed!
```

## Die Kontrollmessung

Wächter in den Trockenlauf (`/etc/nouveau-chankill-watch.dryrun`), dieselbe
Injektion, Opfer wieder surfaceless mit eigenem DRM-Client. Der Kill fand
nachweislich statt:

```
13:55:42  fifo:000000:0004:0004:[fbo-stress[82575]] errored - disabling channel
13:55:42  fbo-stress[82575]: channel 4 killed!
13:55:42  [DRYRUN] wuerde labwc beenden (Kanal-Kill erkannt)
```

Ergebnis über 100 Sekunden:

| Messgröße | Wert |
|---|---|
| labwc-PID | 76849 vorher, 76849 nachher, unverändert |
| Ansprechbarkeit (`wlopm`) | **antwortet** bei jedem Messpunkt bis +100 s |
| Prozesse in D-State | 0 |
| Worker in `dma_fence_default_wait` | 0 |
| Signale an labwc oder Xwayland | **0** (Trace enthält nur den SIGSEGV des Opfers) |

Rohdaten: `~/nvac-v2-qa/labwc-kill-20260812T134929/` (mit Wächter) und
`~/nvac-v2-qa/labwc-control-20260812T135529/` (ohne). Versuchsskripte:
`labwc-kill-trace.sh`, `labwc-kill-control.sh`.

## Was daraus folgt

1. **Die Serie begrenzt den Schaden auf den verursachenden Client.** Genau das,
   was sie verspricht. Der Cover-Letter sagt das jetzt mit Messdaten statt mit
   einer Fehlzuschreibung.
2. **Der Wächter wurde treffsicher gemacht** statt abgeschaltet. Er greift nur
   noch, wenn der getötete Kanal `labwc` oder `Xwayland` gehörte, denn nur dann
   ist die Sitzung wirklich in Gefahr. Fremde Kanäle werden protokolliert und
   ignoriert. Unparsbare Zeilen führen zu einer Warnung, nicht zu blindem
   Handeln. Alte Semantik zurückholen: `/etc/nouveau-chankill-watch.any`
   anlegen. Sicherung: `/root/nouveau-chankill-watch.py.bak-20260812-pre-selective`.
3. **Der ursprüngliche Zweck bleibt ungetestet.** Widerlegt ist nur der Fremdfall.
   Ob labwc zum Zombie wird, wenn sein **eigener** Kanal stirbt, hat niemand
   gemessen. Deshalb wurde der Wächter nicht entfernt.

## Die Lehre, in einem Satz

Bevor man einen beobachteten Kollateralschaden dem gerade untersuchten Code
anlastet, prüfen, ob eine eigene, früher gebaute Umgehung mit im Raum steht.
Auf dieser Maschine laufen mehrere solche Wächter (`nvac-s3-unwedge`,
`gpu-wedge-warner`, `nv-watchdog`, `nouveau-chankill-watch`, `wedge-watcher`,
`base-wedge-capture`), und jeder von ihnen kann in eine Messung hineinregieren.

Das passende Werkzeug ist billig und lag die ganze Zeit bereit: `CONFIG_FTRACE=y`
ist gesetzt, tracefs muss nur eingehängt werden. bpftrace, perf und auditctl gibt
es auf dieser Maschine nicht.

```
sudo mount -t tracefs nodev /sys/kernel/tracing
echo 'comm == "labwc"' > /sys/kernel/tracing/events/signal/signal_generate/filter
echo 1 > /sys/kernel/tracing/events/signal/signal_generate/enable
cat /sys/kernel/tracing/trace_pipe
```

Sender steht links vor dem Zeitstempel, Ziel in `comm=`/`pid=`.
