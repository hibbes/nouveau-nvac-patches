# Stand 21.08.2026, 18:30, nach dem zweiten Reboot

## Laeuft
- 7.2.0-gentoo-nvac-soak seit 18:23, Abnahme gruen, 3 Waechter.
- Modul: voller Stapel + **2/3-Handschlag (v4-Form)** + **0060-probe-v2**.
  Der Soak der eingereichten 2/3 beginnt jetzt.
- lockdep-Splat reproduzierbar bei jedem Boot (70 s, Cursor).
- Warner schweigt bei 0060-probe-Zeilen (nur Log).

## Draussen, wartet auf Menschen
- v4 (17:23): 3 Bot-Antworten, Entwurf der Erwiderung liegt.
- lockdep-Bericht (17:37): 0 Antworten.

## Bereit, wartet auf Lyude
- v5 (nv04-fifo-v5/): fence_armed-Zeiger statt ready-bool. checkpatch 0/0/0.
- Bot-Antwort (nv04-fifo-v4/ANTWORT-BOT-ENTWURF.txt).

## Offene Messung
- Naechster CACHE_ERROR auf mthd 0060: Probe v2 sagt pull0 + alle
  RAMHT-Eintraege des Kanals. Erster Treffer (18:09, v1) sagte HASH_FAILED
  echt, MISSING Artefakt.

## Lehren des Tages, im Memory
- Splat SOFORT sichern. Probe muss Annahme mitliefern. Bot-Befund selbst
  pruefen (einer von vier hielt nicht, drei hielten). Pruefer-Angabe ist erst
  nach eigener Pruefung Tatsache (Mesa-Fundstelle). get_maintainer liefert
  tote Adressen mit.
