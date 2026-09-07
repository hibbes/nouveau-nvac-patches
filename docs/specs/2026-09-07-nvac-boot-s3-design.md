# nvac-boot-s3: prophylaktischer S3-Zyklus nach jedem Boot (Design, 07.09.2026)

## Zweck

Der EVO-Fetch-Park auf NVAC/MCP79 trifft ausschliesslich den ersten vollstaendigen
Display-Zyklus nach kaltem nouveau-Init (Boot-Modeset bis erstes Wiedereinschalten),
bei rund 70 Prozent der Boots, danach in demselben Boot nie wieder. Nach jeder der
17 S3-Heilungen des Watchdogs `nvac-s3-unwedge` (29.06. bis 07.09.2026) gab es keinen
Zweitwedge im selben Boot. Ein Resume-Modeset hat nie gewedget.

Hypothese: ein S3-Zyklus kurz nach dem Boot, bevor jemand am Rechner sitzt, konsumiert
das Risikofenster deterministisch. Preis: rund 35 s schwarzer Schirm je Boot, etwa
80 bis 110 s nach dem Einschalten. Das ist ein Experiment; die Auswertung steht unten.

Nicht identisch mit der am 25.07.2026 verworfenen "Impfung per Blank/Wake-Paar"
(0019-design F4/KF9). Dort ging es um Display-Zyklen, hier um den S3-Pfad, der
nachweislich heilt.

## Komponenten

| Datei | Aufgabe |
|---|---|
| `/usr/local/bin/nvac-boot-s3.sh` | Wartebedingung, Skip-Regeln, S3-Zyklus, Nachpruefung, Log, Historie |
| `/etc/init.d/nvac-boot-s3` | OpenRC-Dienst im default-Runlevel, startet das Skript im Hintergrund |
| `tools/nvac-boot-s3/nvac-boot-s3-selftest.sh` (nur Repo) | Selbsttest der Entscheidungslogik gegen gefaelschte Kommandos |

Kopien der beiden installierten Dateien liegen unter `tools/nvac-boot-s3/` im Repo.

## Ablauf des Skripts

1. Start (Dienst, `after nvac-s3-unwedge nv-watchdog greetd`). Lock per `flock` unter
   `/run/nvac-boot-s3/lock`; zweite Instanz beendet sich mit Exit 2.
2. Skip-Regeln, in dieser Reihenfolge, jede mit eigener Logzeile:
   - Sperrdatei `/etc/nvac-boot-s3.disabled` vorhanden.
   - Marker `/run/nvac-boot-s3/done` vorhanden (schon gelaufen in diesem Boot).
   - `/sys/power/suspend_stats/success` groesser 0 (in diesem Boot gab es schon ein S3,
     typisch die Watchdog-Heilung eines Boot-Modeset-Wedges).
   - Uptime beim Start groesser 600 s (kein frischer Boot, z. B. manueller Dienststart).
   `NBS_FORCE=1` setzt Marker-, S3-Zaehler- und Frischboot-Regel ausser Kraft, nicht
   die Sperrdatei.
3. Warten, bis `pgrep -x labwc` trifft UND Uptime mindestens 75 s (Poll 2 s). Ist bis
   Uptime 240 s kein labwc da: Skip "no compositor".
4. Marker schreiben (VOR dem rtcwake, damit ein haengender Resume nichts wiederholt),
   `dmesg`-Baseline der EVO-Timeouts zaehlen.
5. S3-Zyklus, spiegelt `recover()` des Watchdogs:
   `rc-service nvac-s3-unwedge stop`, `rc-service nv-watchdog stop` (TCO entwaffnen),
   `rtcwake -m mem -s 30`, danach IMMER (trap) `rc-service nv-watchdog start` und
   `rc-service nvac-s3-unwedge start`.
   30 s statt der 40 s des Watchdogs: gesunder Suspend-Eintritt 1 bis 3 s, geparkter
   gemessen 9,2 s (21.08.) und 10,6 s (07.09.). Der Watchdog behaelt seine 40 s.
6. Nachpruefung nach 10 s Ruhe: neue EVO-Timeouts (`base-N: timeout`,
   `core notifier timeout`) im dmesg-Delta zaehlen; NIC-Check `ping -c 2 -W 2 -I enp0s10
   192.168.1.1`, bei Fehlschlag nach 5 s Gnadenfrist ein zweiter Versuch, dann einmal
   `ip link set enp0s10 down` und `up` (forcedeth-Falle vom 12.07.2026) und erneut pingen.
7. Ergebnis: Zeile `RESULT rc=<n> dt=<s> evo_timeouts=<n> nic=<ok|bounced|fail>` im Log
   `/var/log/nvac-boot-s3.log` und eine Zeile je Boot in
   `/var/lib/nvac-boot-s3/history.log`.
8. Telegram (`klaus-send --plain`) NUR bei Anomalie: rtcwake-Rueckgabe ungleich 0,
   EVO-Timeouts nach dem Resume, NIC-Bounce oder NIC-Ausfall. Kein Erfolgs-Ping.

## Abschalten

`touch /etc/nvac-boot-s3.disabled` (bleibt installiert, laeuft nicht) oder
`rc-update del nvac-boot-s3 default`. Keine automatische Laufbegrenzung.

## Auswertung des Experiments

Je Boot: Zeile in `history.log` (rc, dt, evo_timeouts, nic) und die Frage, ob
`/var/log/nvac-s3-unwedge.log` in demselben Boot spaeter ein `WEDGE` zeigt.
Erwartung bei bestaetigter Hypothese: null spaetere Wedges. Ein spaeterer Wedge trotz
Boot-S3 widerlegt die Immunisierungs-Hypothese (dann zurueck auf reine Heilung).
`sudo /usr/local/bin/boot-timeline.sh 300` zeigt den Zyklus im Boot-Protokoll des
boot-blackscreen-Recorders (zeichnet bis 252 s auf).

## Risiken

- Resume bleibt aus: in 17 Watchdog-S3 und mehreren Handtests nie passiert. Der
  Alarm-Abstand von 30 s liegt deutlich ueber jedem gemessenen Suspend-Eintritt; feuert
  der RTC-Alarm vor dem Eintritt, schlaeft die Kiste bis zum Netzschalter.
- NIC-TX-Wedge nach S3 (12.07.2026): wird geprueft und einmal per Link-Bounce behandelt.
- Zweiter Claude- oder Nutzer-Prozess waehrend des Zyklus: friert 35 s ein, ueberlebt.

## Testbarkeit

Alle Pfade und Schwellen sind per `NBS_*`-Umgebungsvariablen ueberschreibbar, alle
externen Kommandos werden ueber PATH aufgeloest (`NBS_PATH_PREFIX` fuer Shims). Der
Selbsttest prueft Skip-Faelle, Wartebedingung, exakte Kommando-Reihenfolge, Neustart
der Waechter auch bei rtcwake-Fehler, NIC-Bounce, Timeout-Alarm, FORCE und Lock.
