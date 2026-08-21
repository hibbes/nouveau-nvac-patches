# Stand 21.08.2026, vor dem Reboot auf 7.2.0

## Was jetzt startet

`7.2.0-gentoo-nvac-soak`, von Hand gebaut, mit lockdep und Debug-Optionen.
Stapel: 21 eigene Patches (0004 AKTIV, dazu die "0060-probe"-Messung im
Quellbaum), 6 Lyude-Originale, 2 drm_panic-Neufassung. Fallback 7.1.8 im
Advanced-Menue, Rettungseintraege auf 7.1.8.

NICHT drin: der neue 2/3-Handschlag. Der lebt nur im Pruefbaum.

## Nach dem Reboot zuerst

    /home/neo/nvac-v2-qa/soak-abnahme.sh --panic

Erwartet: 16/16 Parameter, Spur 1, Teardown, Lyude-Serie, beide
drm_panic-Marker, drei Waechter, sechs Cmdline-Parameter.

Dann `git -C ~/linux-nouveau-patches worktree prune` (Scratchpad weg).

## Woran zu denken ist

- **0060-probe**: sobald `grep '0060-probe' /var/log/kernel/*` einen
  Treffer zeigt, steht darin `pull0`, HASH_FAILED/HASH_BUSY und ob der
  Griff im RAMHT war. Das entscheidet Puller-Aussetzer gegen Treiberfehler.
- **v4 senden**: drei Patches, Anschreiben, Empfaenger liegen unter
  `~/projects/nouveau-nvac-patches/nv04-fifo-v3/v4-vorbereitet/v4series-neu/`.
  Fehlt nur `0000-cover-letter.patch` zum Sendezeitpunkt. NICHTS GESENDET.
- **2/3 soaken**: braucht einen Kernel mit dem neuen Handschlag. Der
  7.2.0-Soakbaum hat noch 0023 (v3-Form). Umbau auf 2/3 = 0023 ersetzen.
- 7.1.9 rentnern: Module und Quellen liegen noch, /boot ist schon sauber.
- 0003 und 0024 ansehen: nie auf einer Liste gewesen.

## Heute gelernt, alles im Memory

Patch-Drift: Anwenden ist nicht Uebersetzen. dmesg_restrict. Ringpuffer
laeuft ueber. Dauerlog ist stapelweise. fifo_*_count sind Schwellwerte.
Ein redigiertes dmesg-Zitat ist der teuerste Fehler. Eine Pruefer-Angabe
ist erst nach eigener Pruefung eine Tatsache.
