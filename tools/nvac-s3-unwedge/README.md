# nvac-s3-unwedge: Waechter fuer den EVO-Fetch-Park

Installiert als `/usr/local/bin/nvac-s3-unwedge-watchdog.py`, OpenRC-Dienst
`nvac-s3-unwedge`, Log `/var/log/nvac-s3-unwedge.log` (jede Zeile steht doppelt,
stdout und stderr gehen in dieselbe Datei; zum Zaehlen `awk '!seen[$0]++'`).

Erkennt den Park per read-only BAR0-mmap (Bit31 im ctrl-Register plus eingefrorener
GET-Zeiger, 3 Bestaetigungen bei 3,0 s Poll) und heilt ihn per `rtcwake -m mem -s 40`.

## Haertung vom 13.09.2026

Anlass: `nvac-boot-s3` wurde abgeschaltet, dieser Waechter ist seitdem das alleinige Netz.
Vorher meldete er nur im Storm-Zweig; ein Wedge plus Heilung plus totes Netz blieb in
einem unbeaufsichtigten Boot stumm.

- Nach dem Resume werden die EVO-ctrl-Register neu gelesen: "geheilt" ist gemessen.
- Netzpruefung `ping -I enp0s10 192.168.1.1`, bei Ausfall nach Gnadenfrist genau EIN
  `ip link set enp0s10 down/up` (forcedeth-S3-TX-Falle vom 12.07.2026).
- Nach jeder Heilung eine Telegram-Meldung mit Kopf aus der Messung ("geheilt",
  "NICHT geheilt, S3-Zyklus fehlgeschlagen", "NICHT geheilt, Park besteht"), plus
  rtcwake-rc, Dauer, TCO-Rueckgabe, Park- und Netzzustand, Kernel.
- `RESULT`-Zeile und jede Meldung auch im Log; ein gescheiterter klaus-send wird geloggt.
- Die Nachpruefung laeuft gekapselt, die Meldung im finally: ein Fehler dort kann den
  Waechter nicht toeten und die Meldung nicht verschlucken.

## Test

`python3 test-recover.py [pfad]` (26 Faelle, simuliert sh(), kein root, kein echtes S3).
Mutationsprobe am 13.09.: 12 von 12 gezielten Verfaelschungen werden rot (vertauschtes
down/up, ping ohne Bindung, invertierte Auswertung, fehlender Alarm, doppelter Bounce,
fest verdrahtetes "ok", fehlender Re-Arm, falscher Kopf, fehlendes Registerlesen,
fehlende Logzeilen, verworfenes TCO-Ergebnis).

## Offen

Der Storm-Zweig (Schwelle STORM_N=3 in STORM_WINDOW=1800 s) heilt NICHT: er loggt,
beendet den Idle-Blanker und alarmiert, der ausloesende Wedge bleibt stehen. Die Schwelle
ist faktisch 4, weil `hits.append()` nach `recover()` steht. Praktisch sehr
unwahrscheinlich, weil der Bug nur den ersten Zyklus je Boot trifft und der Zaehler je
Prozessstart neu beginnt. Bei eingefrorenem Bild nach einer Storm-Meldung: selbst
`sudo rtcwake -m mem -s 40`.
