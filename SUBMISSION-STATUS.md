# Einreichungsstand

Stand 2026-08-06, gegen die lore-Archive geprüft (`t.mbox.gz` mit HTTP-Status,
nicht die Volltextsuche, die von hier durch Anubis blockiert ist).

## Die Message-ID-Falle, bitte zuerst lesen

Die Message-IDs der Serien verwenden **unterschiedliche Absenderadressen**:

| Serie | Message-ID |
|---|---|
| April v1 | `20260409172126.115441-1-marek@czernohous.de` |
| Mai v1 | `20260513175014.96599-1-marek@czernohous.de` |
| Juni v3 | `20260611124535.527275-1-`**`mczernohous@gmail.com`** |
| August v2 (nv04-FIFO) | `20260806085228.1848994-1-`**`mczernohous@gmail.com`** |

Ab dem Juni-Versand läuft `git send-email --from="<gmail>"`, deshalb baut git die
Message-ID aus der Gmail-Adresse. Wer den v3-Thread mit `marek@czernohous.de`
sucht, bekommt **HTTP 404 auf allen Archiven** und schließt daraus fälschlich, die
Serie sei nie versendet worden. Genau das ist am 06.08.2026 einmal passiert.
Immer die vollständige Message-ID aus diesem File verwenden.

## Spur 1: NVAC-Stabilität (0001, 0002, 0003)

| | |
|---|---|
| Status | **v3 auf der Liste, wartet seit 11.06.2026 auf Reaktion** |
| v1 | `[PATCH 0/3]` 09.04.2026, Thread 8 Mails, **Fab Stz** hat extern getestet |
| v2 | `[PATCH v2 0/2]` 11.06.2026 09:26, formfehlerhaft (doppelte In-Body-From, kaputtes Threading); sashiko-bot fand zusätzlich einen echten Defekt im Guard |
| v3 | `[PATCH v3 0/2]` 11.06.2026 14:45, Guard vorgezogen, `Cc: stable # v6.16+`, auf nouveau, dri-devel und lkml je 3 Mails |
| Antworten auf v3 | **keine, seit fast zwei Monaten** |
| 0003 | bewusst aus v2/v3 herausgenommen (schläft unter `mode_config.mutex`) |

**Offen:** der v3-Thread wird vom Morgen-Briefing **nicht** gepollt. Gepollt werden
nur die beiden v1-Threads. Eine Maintainer-Reaktion auf v3 würde also niemand
mitbekommen. Das gehört in `~/.claude/morning-briefing.sh` nachgetragen.

## Spur 2: nv04-FIFO v1 (0004, 0006)

| | |
|---|---|
| Status | **zurückgezogen** |
| Gesendet | `[PATCH 0/2]` 13.05.2026 19:50 |
| Thread | 6 Mails. **Lyude Paul antwortete am 19.05.**, Marek am 20.05. |
| Rückzug | 25.07.2026, Warnung im Thread, die Serie nicht anzuwenden |
| Grund | drei selbst gefundene Defekte, siehe `nv04-fifo-v2/COVER-PRUEFUNG-2026-08-04.md` |

## Spur 3: nv04-FIFO v2 (Nachfolger von Spur 2)

| | |
|---|---|
| Status | **GESENDET 2026-08-06 10:52 CEST** |
| Betreff | `[PATCH v2 0/3] drm/nouveau: nv04 FIFO cleanup + recovery for Tesla` |
| Message-ID | `20260806085228.1848994-1-mczernohous@gmail.com` |
| Verbreitung | nouveau und dri-devel je 4 Mails binnen Minuten; lkml zog spaeter nach |
| Basis | `c21bb4193868` (mainline, 04.08.2026) |
| Quellen | `nv04-fifo-v2/` in diesem Repo |
| SMTP | 4x Result 250 |

Vor dem Versand geprueft: Cover und alle drei Commit-Messages gegen Quellcode,
lore-Archiv, Injektionslog und Hardware. Zwei unbelegte Aussagen wurden dabei
entfernt (eine erfundene G94-Testangabe in 1/3, ein "only a reboot clears it"
in 2/3, das der eigenen Korrektur vom 22.07. widersprach). Details in
`nv04-fifo-v2/COVER-PRUEFUNG-2026-08-04.md` und im Commit `5814df0`.

**Jetzt beobachten:** der Thread ist im Morgen-Briefing unter ii-b) eingetragen.
Beim Juni-Versand meldete sich `sashiko-bot@kernel.org` 13 Minuten nach dem
Send mit einem berechtigten Befund; darauf besonders achten.

## Spur 4: forcedeth (netdev, nicht nouveau)

| | |
|---|---|
| Status | **fertig, nicht gesendet** |
| Quellen | `forcedeth/` in diesem Repo |
| Belege | 0001 per Hardwaretest (2 UBSAN-Splats mit Stock-Modul, 0 mit gepatchtem, über echtes S3); 0002 nur Compile plus Begründung |
| Offen | beiden fehlt der `Fixes:`-Tag, den netdev zwingend verlangt; Betreff muss `[PATCH net]` lauten |

## Nie eingereicht

0005, 0009, 0010, 0011, 0015, 0016, 0017, 0018, 0019, 0020, 0021, 0022. Diese
laufen lokal auf der Referenzmaschine und liegen in diesem Repo, sind aber
nirgends eingereicht. 0019 und 0020 gehen inhaltlich in die v2-Serie ein, dort
allerdings ohne den lokalen Modulparameter `chan_kill_event`.
