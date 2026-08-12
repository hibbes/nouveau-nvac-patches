# Einreichungsstand

Stand **2026-08-12**, gegen die lore-Archive und das Morgen-Briefing geprüft
(`t.mbox.gz` mit HTTP-Status, nicht die Volltextsuche, die von hier durch
Anubis blockiert ist).

## Kurzübersicht

| Spur | Gegenstand | Status |
|---|---|---|
| 1 | NVAC-Stabilität (0001, 0002) | **v3 auf der Liste**, seit 11.06. keine Reaktion |
| 2 | nv04-FIFO v1 (0004, 0006) | **zurückgezogen** 25.07. |
| 3 | nv04-FIFO v2 (3 Patches) | **gesendet** 06.08., keine Reaktion |
| 4 | forcedeth (netdev) | fertig, **nicht gesendet**, `Fixes:` fehlt |
| 5 | nv04-FIFO v3 (5 Patches) | fertig, **bewusst zurückgehalten**, siehe unten |

Alle vier gesendeten Threads werden vom Morgen-Briefing gepollt.

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
| Antworten auf v3 | **keine, seit über zwei Monaten** (Briefing: "weiterhin keine Reaktion") |
| 0003 | bewusst aus v2/v3 herausgenommen (schläft unter `mode_config.mutex`) |

**Erledigt seit dem letzten Stand:** der v3-Thread wird inzwischen vom
Morgen-Briefing gepollt (`~/.claude/morning-briefing.sh`, Abschnitt i-b, Baseline
3 Mails), ebenso der nv04-v2-Thread (ii-b, Baseline 4).

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
| Status | **GESENDET 2026-08-06 10:52 CEST**, bis 12.08. keine externe Reaktion |
| Betreff | `[PATCH v2 0/3] drm/nouveau: nv04 FIFO cleanup + recovery for Tesla` |
| Message-ID | `20260806085228.1848994-1-mczernohous@gmail.com` |
| Verbreitung | nouveau und dri-devel je 4 Mails binnen Minuten; lkml zog später nach |
| Basis | `c21bb4193868` (mainline, 04.08.2026) |
| Quellen | `nv04-fifo-v2/` |
| SMTP | 4x Result 250 |

Vor dem Versand geprüft: Cover und alle drei Commit-Messages gegen Quellcode,
lore-Archiv, Injektionslog und Hardware. Zwei unbelegte Aussagen wurden dabei
entfernt (eine erfundene G94-Testangabe in 1/3, ein "only a reboot clears it"
in 2/3, das der eigenen Korrektur vom 22.07. widersprach).

**Wichtig:** der sashiko-Review-Bot hat auf **diese** Fassung drei Befunde
gemeldet, alle drei berechtigt. Genau deshalb existiert Spur 5.

## Spur 4: forcedeth (netdev, nicht nouveau)

| | |
|---|---|
| Status | **fertig, nicht gesendet** |
| Quellen | `forcedeth/` |
| Belege | 0001 per Hardwaretest (2 UBSAN-Splats mit Stock-Modul, 0 mit gepatchtem, über echtes S3); 0002 nur Compile plus Begründung |
| Offen | beiden fehlt der `Fixes:`-Tag, den netdev zwingend verlangt; Betreff muss `[PATCH net]` lauten |

Nebenbefund vom 12.08.2026: der Off-by-one feuert weiterhin bei **jedem** Suspend,
zuletzt sichtbar beim Heil-S3 des EVO-Watchdogs
(`UBSAN: array-index-out-of-bounds ... forcedeth.c:6240, index 385 is out of range
for type 'u32 [385]'`). Der Fix ist also nach wie vor einschlägig.

## Spur 5: nv04-FIFO v3 (Antwort auf die drei sashiko-Befunde)

| | |
|---|---|
| Status | **fertig geschrieben, bewusst ZURÜCKGEHALTEN** |
| Umfang | 5 Patches, Quellen in `nv04-fifo-v3/` |
| Neu gegenüber v2 | 1/5 Unsubscribe vor dem Fence-Kontext, 2/5 Subscribe nach dem Fence-Kontext, 5/5 Streak-Aufräumen nach `nvkm_chid_put()` |
| Unverändert | 3/5 und 4/5 (nur rebased) |

### Warum sie noch liegt, und was vorher zu tun ist

**Der Cover-Letter enthält eine Aussage, die die Messdaten nicht decken.** Er sagt
über die Injektionsläufe:

> *The killed channel belonged to Xwayland, and in both runs Xwayland and the
> compositor exited*

Das trifft auf die Läufe 1 und 2 zu, bei denen das Opfer über Xwayland lief. In
den **Läufen 3 und 4** war das Opfer bewusst `surfaceless` mit **eigenem
DRM-Client**, also gerade nicht Xwayland. Erwartet war, dass der Kill nur den
Übeltäter trifft. Tatsächlich riss der Sitzungsabbruch beide Male auch das
laufende Testskript mit, die Protokolle brechen unmittelbar nach der
Injektionszeile ab (`injection-run3/4-2026-08-06.log`).

**Das heißt: der Kanal-Kill nimmt den Compositor auch dann mit, wenn der
getötete Kanal einem völlig unbeteiligten Prozess gehört.** Das ist ein deutlich
schlechterer Handel als der, den der Cover beschreibt, und genau der Punkt, an
dem Reviewer zu Recht einhaken würden.

**Was wir wissen und was nicht.** Das labwc-Log von Lauf 4 (`/var/log/labwc.log`,
06.08. um 14:59:48) zeigt: die Clients melden alle `Connection reset by peer`,
labwc' Socket war also schon weg, als sie es merkten. labwc selbst zeigt **keinen
Fehler**, sondern die geordnete Abbau-Sequenz (`Handle destruction of output
DP-1`, `Destroying wlr_drm_lease_device_v1 for /dev/dri/card0`). Es beendet sich
**sauber**. Wer es beendet, ist unbekannt.

**Vor dem Versand nötig, in dieser Reihenfolge:**

1. **Herausfinden, was labwc beendet.** Signal-Tracing auf den labwc-Prozess
   während einer Injektion. Das ist eine abgegrenzte Aufgabe, keine Forschung.
   Ergebnis entscheidet alles Weitere: ist es ein Kernel-seitiger Abriss, gehört
   das in den Cover als bekannter Preis; ist es ein labwc- oder seatd-Verhalten,
   gehört es benannt und der Serie nicht angelastet.
2. **Den falschen Satz im Cover ersetzen** durch die belegte Fassung: der
   Compositor geht auch bei einem fremden Kanal mit, vier Läufe, zweimal mit
   unbeteiligtem DRM-Client.
3. Erst dann senden.

Die Serie ohne Schritt 1 zu schicken hieße, den zentralen Verkaufspunkt ("wir
tauschen einen unrettbaren Freeze gegen einen neu gestarteten Client") mit einer
Beobachtung zu unterlegen, die ihn nicht trägt.

## Nie eingereicht

0005, 0009, 0010, 0011, 0015, 0016, 0017, 0018, 0019, 0020, 0021, 0022, 0023,
0024. Diese laufen lokal auf der Referenzmaschine und liegen in diesem Repo, sind
aber nirgends eingereicht. 0019 und 0020 gehen inhaltlich in die v2-Serie ein,
dort allerdings ohne den lokalen Modulparameter `chan_kill_event`; 0023 und 0024
entsprechen 2/5 und 5/5 der zurückgehaltenen v3.

**0011 erreicht sein Ziel auf dieser Maschine nachweislich nicht** (debugfs zeigt
während des Blanks head-1 mit `enable=0, active=0, connector_mask=0`). Vor einer
Einreichung wäre zu klären, ob `soft_dpms` überhaupt noch etwas beiträgt.

## Weitere offene Punkte aus den Covers

- Der im v3-Cover versprochene eigene Bericht zum **drm_panic-ioremap** (Panik
  beim Scanout-Pfad, `nv50_wndw_get_scanout_buffer` -> `ttm_bo_kmap` ->
  `__ioremap_caller`, `kernel BUG at mm/vmalloc.c:3212`) steht seit 02.06. aus.
- `Fixes:`-Tags fehlen in beiden forcedeth-Patches.
- Die `spinlock_t`-CHECK von checkpatch ist nie abgearbeitet.
- **Sicherheit:** das Gmail-App-Passwort steht im Klartext als
  `sendemail.smtppass` in `~/linux-nouveau-patches/.git/config` und gehört
  rotiert.
