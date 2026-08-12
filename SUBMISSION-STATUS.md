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
| 5 | nv04-FIFO v3, **Viererserie** | **GESENDET 13.08.2026 01:13**, 5x SMTP 250 |
| 6 | Tesla-Recovery (ex 5/5) | zurückgestellt für v4, zwei Codefehler, siehe unten |

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
| Status | **GESENDET 2026-08-13 01:13 CEST als Viererserie** |
| Betreff | `[PATCH v3 0/4] drm/nouveau: channel-kill event ordering fixes, and lower the gate to NV50` |
| Message-ID | `20260812231330.705425-1-mczernohous@gmail.com` |
| SMTP | 5x Result 250 (Cover plus vier Patches) |
| Basis | `c21bb4193868` |
| Empfänger | nouveau, dri-devel, lkml, dazu Krummrich, Lyude, Airlie, Vetter und **Skeggs über bskeggs@nvidia.com** |
| Quellen | `nv04-fifo-v3/v4series/` |

**Zum Beobachten:** der Thread gehört ins Morgen-Briefing, Baseline 5 Mails, alle
vom 13.08. Beim Juni-Versand meldete sich `sashiko-bot@kernel.org` 13 Minuten
nach dem Send. Achtung bei der Suche: Message-ID läuft über die **Gmail**-Adresse.

Der Tesla-Recovery-Patch ist NICHT dabei, siehe unten.
| Umfang | 5 Patches, Quellen in `nv04-fifo-v3/` |
| Neu gegenüber v2 | 1/5 Unsubscribe vor dem Fence-Kontext, 2/5 Subscribe nach dem Fence-Kontext, 5/5 Streak-Aufräumen nach `nvkm_chid_put()` |
| Unverändert | 3/5 und 4/5 (nur rebased) |

### Der Sperrgrund ist am 12.08.2026 widerlegt worden

Sie lag wochenlang, weil vier Injektionsläufe zu belegen schienen, dass ein
Kanal-Kill den Compositor mitnimmt, sogar bei einem fremden Kanal. **Das war
falsch zugeschrieben.** Ein ftrace auf `signal:signal_generate` hat den Sender
benannt: `nouveau-chankill-watch.py`, ein **lokaler Wächter vom 25.07.2026**, der
auf jede `channel N killed!`-Zeile ein SIGTERM an labwc schickte, ohne den
Besitzer des Kanals zu prüfen.

Kontrollmessung mit entschärftem Wächter, gleiche Injektion, Opfer wieder
surfaceless mit eigenem DRM-Client: labwc-PID unverändert, per `wlopm` noch nach
100 Sekunden ansprechbar, D-State 0, `dma_fence_default_wait` 0, **null Signale**.
Der Kill selbst fand nachweislich statt.

Vollständige Herleitung, Rohdaten und die Lehre daraus:
[`docs/2026-08-12-chankill-watch-fehlzuschreibung.md`](docs/2026-08-12-chankill-watch-fehlzuschreibung.md).

**Der Cover-Letter ist entsprechend korrigiert** (Commit siehe unten): der Absatz
über den Wirkungsradius nennt jetzt die Fehlzuschreibung offen, zeigt den
ftrace-Auszug und die Kontrollmessung, und schließt mit "only the faulting client
dies". Das ist für die Serie eine deutlich stärkere Aussage als die alte.

### Aber: die Gegenprüfung vom 12.08. hat zwei ECHTE Codefehler gefunden

Der alte Sperrgrund ist weg, ein neuer ist da. Eine siebenlinsige Prüfung mit
anschliessender Widerlegung (99 Rohbefunde, 30 eindeutige Probleme, 26
überstanden) empfiehlt **`groesserer_umbau`**. Vollständig in
[GEGENPRÜFUNG-2026-08-12.md](nv04-fifo-v3/GEGENPRUEFUNG-2026-08-12.md).

Die beiden Codefehler, beide in 5/5, beide selbst am Quelltext nachgeprüft:

1. **`nv04_fifo_recover()` hat keinen Familien-Guard.** `nv04_fifo_intr` ist
   `.intr` für sieben Chipfamilien (nv04.c:545, nv10.c:98, nv17.c:127,
   nv40.c:237, nv50.c:383, g84.c:215, g98.c:54). Das Abo-Gate aus 4/5 steht auf
   `oclass >= NV50_CHANNEL_GPFIFO`. Auf NV04 bis NV40 feuert die Eskalation also
   ohne Abnehmer und erzeugt genau den Dead-Letter-Hänger, den 4/5 drei Patches
   vorher anklagt. Die Serie widerlegt ihre eigene Begründung im selben Diff.
   Fix: `if (device->card_type != NV_50) return;` am Funktionskopf, eine Stunde.

2. **Use-after-free von `struct nouveau_drm`.** `dev_set_drvdata` steht genau
   einmal (nouveau_drm.c:773) und wird nie genullt. `nouveau_drm_device_remove`
   ruft `_del` (:943, `kfree(drm)` bei :743) **vor** `nvkm_device_del` (:944),
   und das einzige `cancel_work_sync` für das Wedge-Work sitzt in
   `nvkm_fifo_dtor` (base.c:340 → recover.c:175), läuft also erst in :944. Ein
   eingereihtes Work liest freigegebenen Speicher und reicht ihn an `dev_info`,
   den Tracepoint und `drm_dev_wedged_event` weiter. Fix: Tier-2 in die
   DRM-Schicht heben, das löst zugleich den Schichtungsverstoss.

**Praktischer Weg laut Urteil:** 1/5 bis 4/5 mit korrigierten Commit-Texten und
`Fixes:`-Tags als geschlossene Viererserie senden (3/5 und 4/5 stehen ohne 5/5
sauber für sich, 4/5 ist dann ein wohlbegründetes No-op), und 5/5 für v4
umbauen.

**Und unabhängig davon:** `v3-0000-cover-letter.patch` ist die veraltete Fassung
und trägt die vom Autor selbst widerlegte Behauptung, der Compositor sterbe mit
dem Opfer. Diese Datei ginge raus, nicht `v3-cover-body.txt`.

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
