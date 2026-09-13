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
   `core notifier timeout`) im dmesg-Delta zaehlen, getrennt in VOR und NACH
   `PM: suspend exit`. Timeouts beim Suspend-Eintritt heissen: der erste Display-Zyklus
   dieses Boots hat im Teardown des Boot-S3 geparkt und derselbe S3 hat ihn geheilt
   (Logzeile `park: consumed during suspend entry`, Historie `park=N`); das ist der
   erwartete Erfolgsfall des Experiments, kein Alarm. Nur Timeouts nach dem Resume
   (`post=N`) sind eine Anomalie. Erster Boot 08.09.2026 18:59 lieferte genau diesen
   Fall (park=1, post=0); NIC-Check `ping -c 2 -W 2 -I enp0s10
   192.168.1.1`, bei Fehlschlag nach 5 s Gnadenfrist ein zweiter Versuch, dann einmal
   `ip link set enp0s10 down` und `up` (forcedeth-Falle vom 12.07.2026) und erneut pingen.
7. Ergebnis: Zeile `RESULT rc=<n> dt=<s> evo_timeouts_entry=<n> evo_timeouts_post=<n> nic=<ok|bounced|fail>` im Log
   `/var/log/nvac-boot-s3.log` und eine Zeile je Boot in
   `/var/lib/nvac-boot-s3/history.log`.
8. Telegram (`klaus-send --plain`) NUR bei Anomalie: rtcwake-Rueckgabe ungleich 0,
   EVO-Timeouts NACH dem Resume, NIC-Bounce oder NIC-Ausfall. Kein Erfolgs-Ping, kein
   Ping fuer einen beim Suspend-Eintritt konsumierten Park.

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

## Abgeschaltet am 13.09.2026 (Messpause fuer den 7.2.5-Test)

Sperrdatei `/etc/nvac-boot-s3.disabled` gesetzt, der Dienst bleibt im Runlevel und
schreibt je Boot `skip: disabled` ins Log, damit der Messarm "aus" belegbar ist.

**Warum**, Auswertung per Workflow mit adversarialer Gegenpruefung:

- Nur 2 informative Boots mit Dienst (08.09. park=1, 13.09. park=0), p = 0,096 gegen die
  unabhaengig nachgerechnete Basisrate 20/29 = 69 Prozent (Wilson 95 Prozent 51 bis 83).
  Kein Signal.
- Mit eingeschaltetem Dienst ist die Frage "heilt ein neuer Kernel" prinzipiell nicht
  messbar: er ersetzt das erste Wiedereinschalten (Mehrheit der Episoden) durch ein
  Resume-Modeset, das nie gewedget hat; der gemessene Teardown provoziert und heilt im
  selben Vorgang; die Baseline beginnt erst bei Uptime 75 s. park>=1 bleibt gueltige
  Positiv-Evidenz, park=0 beweist fast nichts. Entdeckung je Boot rund 0,69 (aus) gegen
  0,14 (an), also 3 bis 4 Boots statt rund 20 fuer dieselbe Aussage.
- 7.2.5 heilt nachweislich nicht: 0 Treffer fuer `dispnv50` im Upstream-Delta, alle 19
  nouveau-Dateien im GSP-RM-Zweig (Turing aufwaerts), nv50-Disp und `nvac_chipset`
  byteidentisch, `kernel/power` unveraendert. Der Test wird also sehr wahrscheinlich
  bestaetigen, dass der Bug noch da ist; bei p=0,69 im Mittel nach 1,4 Boots.

**Vorher gehaertet**, weil der Waechter `nvac-s3-unwedge` jetzt das alleinige Netz ist:
Netzpruefung mit einmaligem Link-Bounce, Nachlesen der EVO-Register nach dem Resume,
Ergebnismeldung per Telegram nach JEDER Heilung, RESULT-Zeile im Log. Siehe
`tools/nvac-s3-unwedge/`.

**Messrezept je Boot:** `sudo awk '!seen[$0]++' /var/log/nvac-s3-unwedge.log | tail`
zeigt WEDGE und die neue RESULT-Zeile (rc, tco, park, nic, kernel). Ein WEDGE unter 7.2.5
beantwortet die Frage (heilt nicht). 4 saubere Boots: "nicht mehr reproduzierbar"
(Restwahrscheinlichkeit 0,8 Prozent am Punktschaetzer, 5,8 Prozent an der
Wilson-Untergrenze), 6 saubere Boots tragen die Aussage auch an der Untergrenze.
Zaehlung beginnt bei jedem Kernel-Bump neu.

**Wiedereinschalten:** `sudo rm -f /etc/nvac-boot-s3.disabled` (wirkt ab dem naechsten Boot).
