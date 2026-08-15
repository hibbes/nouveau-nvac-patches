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
| 4 | forcedeth (netdev) | fertig, **nicht gesendet**; `Fixes:` seit 13.08. ermittelt, Rest mechanisch |
| 5 | nv04-FIFO v3, **Viererserie** | **GESENDET 13.08.2026 01:13**, 5x SMTP 250 |
| 6 | Tesla-Recovery (ex 5/5) | zurückgestellt für v4, zwei Codefehler, siehe unten |
| 7 | Teardown (3 Patches) | fertig, **nicht gesendet** |
| 8 | drm_panic-Bericht | **GESENDET 15.08.2026 18:07**, 12 Empfänger, 0 abgelehnt |

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

### Stand 15.08.2026: der Fehler lebt, die Serie ist verrottet

Gegen `c21bb4193868` geprüft, nur lesend mit `git apply --check`:

| Patch | Ergebnis |
|---|---|
| `0001` mcp79-msi-rearm | **passt sauber** |
| `0002` kms-sor-null-guard | **passt nicht mehr** |

**0002 scheitert nicht inhaltlich, sondern an fremder Kontextdrift.** Der Fehler
selbst steht unverändert in Mainline: `dispnv50/disp.c:1568` macht weiterhin
`struct nv50_head *head = nv50_head(nv_encoder->crtc);` ohne NULL-Prüfung, und
in der ganzen Funktion gibt es keinen Guard. Verschoben hat sich nur die
Signatur, durch `5164f7e7ff8e ("drm: Rename struct drm_atomic_state to
drm_atomic_commit")`. Der Parameter heißt jetzt `struct drm_atomic_commit *state`.

**Folge:** vor einem Ping oder einem Neuversand als v4 muss 0002 rebased werden.
Das ist eine Kontextanpassung, keine Neufassung. Danach ist ein v4 mit dem
Hinweis auf die zwei Monate Stille die naheliegende Form, ein bloßer Ping auf
einen Thread, dessen Patches nicht mehr anwenden, hilft niemandem.

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
| Offen | Betreff auf `[PATCH net]`, Tags eintragen, neu erzeugen, checkpatch, Empfängerliste |
| Blocker weg | **Die `Fixes:`-Commits sind am 13.08. ermittelt und per Diff belegt.** 0001: `1a1ca86158ee`, 0002: `86a0f04387bf`. Herleitung und Methode in [`forcedeth/README.md`](forcedeth/README.md) |

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

### Dritte Auflage für v4: der Erholungspfad greift an der falschen Quelle

Am **13.08.2026** hing die Referenzmaschine hart, und der Vorfall ist für den
Umbau von 5/5 unmittelbar einschlägig. Vollständig in
[`docs/2026-08-13-pgraph-ccache-hang/`](docs/2026-08-13-pgraph-ccache-hang/).

Kurz: Chromes GPU-Prozess löste einen VM-Fault auf den Constant Buffer aus
(`gr: TRAP_CCACHE`, `PAGE_NOT_PRESENT`). Nouveau meldete den Fault und ließ ihn
fallen. Kein `nvkm_chan_error()`, kein Kanal-Kill, kein Fence-Signal. PGRAPH
stand danach dauerhaft (`PGRAPH_STATUS 00000503` unverändert über Minuten,
`PFIFO_CACHE1_GET` auf 0 gegen `PUT 0244`), `labwc` hing in
`nouveau_gem_ioctl_cpu_prep`, dreizehn TTM-Worker im D-State. Nur Reboot half,
und der blieb an eben diesen Workern hängen, sodass die Maschine danach erst
nach einem manuellen `fsck` auf `sda3` wieder bootete.

Zwei Schlüsse, sauber getrennt:

1. **Was der Vorfall belegt.** Die Annahme hinter 4/4 der gesendeten Serie
   stimmt, jetzt erstmals mit Messwerten von echter Hardware statt aus dem
   Quelltext hergeleitet: ein Kanalfehler ohne Abnehmer bedeutet Fences, die nie
   signalisieren, und genau die vorhergesagte Blockade dahinter.
2. **Was er über 5/5 sagt, unbequem.** Der zurückgestellte Patch hätte diesen
   Hänger **nicht** gefangen. Er hängt sich an `cache_error` und `dma_pusher` in
   `nv04_fifo_intr`, der real aufgetretene Fehler kam aber aus **PGRAPH**. Der
   Umbau muss die PGRAPH-Traps also mitnehmen, sonst deckt der Erholungspfad
   ausgerechnet den Fall nicht ab, der auf der Referenzhardware tatsächlich
   auftritt.

**Nebenbefund, korrigiert:** in der ersten Fassung des Befunds stand,
Bit 31 in `PGRAPH_TRAPPED_ADDR` zeige einen eingerasteten Trap an. Das war aus
einer einzigen Beobachtung erfunden und ist falsch. `nv50_gr_intr()`
(`nvkm/engine/gr/nv50.c:628`) liest aus dem Register nur `subc` und `mthd`,
Bit 31 nirgends, und quittiert über `0x400100`; das Register wird nie
zurückgesetzt. Gegenprobe auf frisch gebooteter, leerlaufender GPU: `STATUS 0`,
`TRAPPED_ADDR 800315e0` mit gesetztem Bit 31. Brauchbarer Indikator ist
`PGRAPH_STATUS`, mehrfach gelesen.

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

- **GESENDET 15.08.2026 18:07.** Der versprochene Bericht zum
  **drm_panic-ioremap** ist raus, Message-ID
  `178681005908.3524476.7115000150741026287@gmail.com`, 12 Empfänger, keine
  Ablehnung. Quellen und Versandprotokoll in
  [`drm-panic-report/`](drm-panic-report/). **Zum Beobachten:** gehört ins
  Morgen-Briefing, Baseline 1 Mail. Antworten sind hier eher zu erwarten als
  bei den Patchserien, weil die drm_panic-Maintainer direkt im To stehen. **Korrektur einer Datumsangabe, die hier falsch stand:** der
  02.06. ist das Datum des *Absturzes*. Das *Versprechen* steht im **v2**-Cover
  (`20260806085228.1848994-1-mczernohous@gmail.com`, 06.08.2026), nicht im
  gesendeten v3-Cover. Es war also neun Tage alt, nicht zweieinhalb Monate.
- `Fixes:`-Tags fehlen in beiden forcedeth-Patches.
- Die `spinlock_t`-CHECK von checkpatch ist nie abgearbeitet.
- **Sicherheit:** das Gmail-App-Passwort steht im Klartext als
  `sendemail.smtppass` in `~/linux-nouveau-patches/.git/config` und gehört
  rotiert.

## Reaktionen auf die Viererserie (13.08.)

### sashiko-bot: KEIN Defekt in den Patches

Erstmals nach zwei Runden. Die Meldungen zu 1/4 und 2/4 sind ausdrücklich als
**"Pre-existing issues"** gekennzeichnet und betreffen Code, den die Serie nicht
anfasst. Beide selbst am Quelltext nachgeprüft und **bestätigt**:

1. **`nouveau_fence_context_del()`** (`nouveau_fence.c:97-109`) ruft
   `cancel_work_sync(&fctx->uevent_work)` bei :99, aber `nvif_event_dtor(&fctx->event)`
   erst bei :101. Dazwischen ist das Ereignis noch scharf, und
   `nouveau_fence_wait_uevent_handler` (`:161-166`) reiht bedingungslos
   `schedule_work(&fctx->uevent_work)` ein. Das eingereihte Work trifft dann den
   freigegebenen `fctx`. **Das ist exakt die Spiegelung unseres eigenen 1/4, eine
   Ebene tiefer.**
2. **`nouveau_connector_destroy()`** (`nouveau_connector.c:395-407`) gibt den
   Connector bei :406 frei, `schedule_work(&nv_connector->irq_work)` steht bei
   :1210, und im gesamten Treiber gibt es **kein einziges** `cancel_work_sync`
   dafür.

**Naheliegender Nachfolger:** eine kleine Serie mit genau diesen zwei
Teardown-Fixes. Das Muster ist dasselbe, das die Viererserie beschreibt, und
niemand kennt es gerade besser. **Umgesetzt, siehe Spur 7.**

## Spur 7: Teardown-Serie (Dreierserie, FERTIG, NICHT GESENDET)

| | |
|---|---|
| Status | **fertig und gebaut, wartet auf Freigabe zum Versand** |
| Betreff | `[PATCH 0/3] drm/nouveau: teardown ordering fixes for events and work` |
| Branch | `nouveau-event-teardown` in `~/linux-nouveau-patches` |
| Basis | `c21bb4193868` (dieselbe wie die Viererserie) |
| checkpatch | `--strict` sauber auf allen dreien **und auf dem Cover** |
| Bau | **Vollbau 14.08.2026 01:06, rc=0**, 0 Warnungen, 0 Fehler, `Module.symvers` und `nouveau.ko` erzeugt. Bewusst der volle Kernel und nicht nur `make M=`, sonst haette `modpost` mangels `Module.symvers` gar nicht aufgeloest und die Aussage ueber das Binden waere ungedeckt gewesen |

| Patch | Gegenstand | Fixes |
|---|---|---|
| 1/3 | `nouveau_fence_context_del()`: Ereignis vor dem Entleeren des Works abbauen | `39126abc5e20` |
| 2/3 | `nouveau_connector_destroy()`: `irq_work` entleeren, bevor der Connector fällt | `773eb04d14a1` |
| 3/3 | `nouveau_dp_irq()`: `outp` erst prüfen, dann dereferenzieren | `773eb04d14a1` |

Alle drei mit `Cc: stable`. 1/3 und 2/3 sind die beiden sashiko-Befunde von
oben, 3/3 fiel beim Lesen derselben Funktion mit ab.

**Dass 2/3 und 3/3 denselben Commit zitieren, ist kein Versehen:**
`773eb04d14a1` machte `nouveau_dp_irq()` zum Work-Callback und erzeugte damit in
einem Zug beides, das nie entleerte Work und den vorgezogenen Zugriff (der
`drm`-Zeiger war vorher ein Argument und wurde danach aus dem Encoder geholt,
was die Dereferenzierung über die vorhandene NULL-Prüfung schob).

### Was die Gegenprüfung vor dem Versand gefunden hat

Vier Befunde, davon zwei echt:

1. **ECHT, behoben.** Der Commit-Text von 1/3 behauptete,
   `nouveau_fence_context_kill()` hänge nicht am Ereignis. Der Quelltext sagt das
   Gegenteil: die Funktion ruft `nvif_event_block(&fctx->event)` für jeden Fence,
   den sie signalisiert. Die Umstellung ist trotzdem richtig, aber aus einem
   anderen Grund, als der Text behauptete: `nvif_event_block()` steht hinter
   `nvif_event_constructed()`, und `nvif_object_dtor()` setzt `object->client`
   auf NULL, der Aufruf verpufft also folgenlos. Der Commit-Text sagt das jetzt.
2. **ECHT, behoben.** 3/3 hatte weder `Fixes:` noch `Cc: stable`. Der Ursprung
   ist per `git log -S` und `git show` auf `773eb04d14a1` festgenagelt, nicht
   geraten: Lyudes Commit von 2020 (`a0922278f83e`) scheidet aus, dort war `drm`
   noch ein Funktionsparameter.
3. **WIDERLEGT.** "Das Muster wiederholt sich eine Ebene höher, `drm->hpd_work`
   wird beim Abbau nie geleert." Doch, wird es: `nouveau_display_fini()`
   (`nouveau_display.c:600`) ruft `cancel_work_sync(&drm->hpd_work)` direkt nach
   dem Sperren der Hotplug-Ereignisse. Deshalb kein vierter Patch.
4. **ENTKRÄFTET.** "Die Umstellung verbreitert ein Fenster, in dem
   `nvif_event_allow()` auf ein zerstörtes Ereignis trifft." Derselbe
   `nvif_event_constructed()`-Riegel deckt auch `nvif_event_allow()` in
   `nouveau_fence_enable_signaling()` ab.

### Empfängerliste (entschieden 13.08.2026)

**Skeggs bleibt weg.** Entscheidung von Marek, nachdem `bskeggs@nvidia.com` beim
Versand der Viererserie mit `550 Access denied` abgelehnt hatte und
`get_maintainer.pl` mit `bskeggs@redhat.com` nur eine Adresse aus MAINTAINERS und
Historie anbietet, also aus genau der Quellenart, die in den Bounce geführt hat.
Er war ohnehin nur als Autor der `Fixes:`-Commits im Cc; die zuständigen
Maintainer erreicht die Serie ohne ihn.

```
To:  nouveau@lists.freedesktop.org
     dri-devel@lists.freedesktop.org
Cc:  linux-kernel@vger.kernel.org
     Danilo Krummrich <dakr@kernel.org>
     Lyude Paul <lyude@redhat.com>
     David Airlie <airlied@gmail.com>
     Simona Vetter <simona@ffwll.ch>
```

Das ist die Liste der Viererserie minus Skeggs, die dort 5x SMTP 250 lieferte.
`get_maintainer.pl` nennt zusätzlich die drm-misc-Runde (Lankhorst, Ripard,
Zimmermann, Airlie unter der Red-Hat-Adresse). Die war bei den bisherigen
Versänden nicht dabei und bleibt es vorerst auch nicht, damit der Thread dort
liegt, wo die vorigen liegen.

### Bounce: bskeggs@nvidia.com nimmt keine Post an

`550 5.4.1 Recipient address rejected: Access denied` von
`nvidia-com.mail.protection.outlook.com`. Das ist eine Exchange-Online-Richtlinie
gegen externe Absender, kein "unbekannter Empfänger".

**Lehre, und das war ein Fehler in der Vorbereitung:** ich hatte über
`git log --format=%ae` geprüft, von welcher Adresse Skeggs *committet*, und
daraus geschlossen, dass sie auch Post *annimmt*. Das folgt nicht auseinander.
Für den nächsten Versand: prüfen, von welcher Adresse die Person zuletzt **auf
der Liste geschrieben** hat, denn diese Adresse empfängt nachweislich.

Praktische Folge gering: die Serie liegt auf nouveau, dri-devel und lkml, und die
zuständigen Maintainer (Krummrich, Lyude) haben sie. Skeggs war nur als Autor des
`Fixes:`-Commits im Cc.
