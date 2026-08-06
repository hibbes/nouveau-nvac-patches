# Gegenprüfung des v2-Cover-Letters, 2026-08-04

Jede Faktenbehauptung aus `v2-cover-body.txt` gegen echte Artefakte geprüft.
Nichts gesendet. Korrigierte Fassung: `v2-cover-body-korrigiert-2026-08-04.txt`.

## Belegt, unverändert übernehmbar

| Behauptung | Beleg |
|---|---|
| `nvkm_chan_error(chan, true)` derefereniert NULL auf Tesla | `chan.c:235-236` ruft `chan->func->preempt(chan)` ohne NULL-Prüfung; `nv50.c` und `g84.c` haben **0** `.preempt`-Einträge, `gf100.c` hat 2 |
| Präzedenz `preempt=false` | `runl.c:80` `nvkm_chan_error(chan, false)` |
| Trace vom 02.06. wörtlich | `session_nouveau_crash_2026_06_02_fifo_cache_error`: `CACHE_ERROR - ch 2 [labwc[3950]] subc 3 mthd 0f00 data 0000007b`, `nv04_fifo_intr_cache_error+0x111 → nv04_fifo_recover+0x80 → nvkm_chan_error+0x99`, `RIP: 0010:0x0`. Kernel war 7.0.10-p1, Aufzeichnung per netconsole auf lorawan-gw |
| drm_panic eskaliert die Oops zur Panic | ebd.: `nv50_wndw_get_scanout_buffer → nouveau_bo_map → ttm_bo_kmap → __ioremap_caller` → `kernel BUG at mm/vmalloc.c:3212` |
| Puller benennt den residenten Kanal | `nv04.c:227` Kommentar „sending incorrect instance offsets to PGRAPH" in `nv04_fifo_pause()` |
| Mainline abonniert kill nur ab `FERMI_CHANNEL_GPFIFO` | `nouveau_chan.c:375-376`, else-Zweig des gepatchten Ternärs |
| `channel N killed!` ist die Marker-Zeile | `nouveau_chan.c:57` |
| Leiter, Fensterablauf, Kill zugestellt | `~/nvac-v2-qa/injection-proof-2026-07-25.log`, Zeilen 5/7/9/11/12 |
| 0 D-State-ttm-Worker nach dem Fix, labwc lief weiter | `session_nouveau_0019_0020_analyse_2026_07_25` |
| SIGSEGV in libgallium | ebd. |
| Mesa 26.0.8 | `qlist -Iv media-libs/mesa` = 26.0.8 |
| `coding-assistants.rst` existiert | im 7.1.6-Baum vorhanden |
| „zweimal" bei Compositor-Kill und Frozen Desktop | zwei getrennte Vorfälle: 02.06. (`ch 2 [labwc[3950]]`) und 22.07. (`ch 2 [labwc[4593]]`), am 22.07. zusätzlich ein Rezidiv am Abend |

## Falsch oder ungedeckt, korrigiert

**1. „A fault 30 seconds after the previous one counted as 1/3 again"**
Log: 21:28:20 auf 21:28:38, also **18 Sekunden**. Die 30 stammen aus der
Analyse-Notiz vom 25.07. und sind von dort in den Cover gewandert. Inhaltlich
bleibt die Aussage richtig (Fenster ist 10 s), die Zahl war es nie.

**2. Zitierter Log-Block war beschnitten**
Cover zitierte `channel 5 killed!`, im Log steht `Xwayland[4931]: channel 5 killed!`.
Der Präfix kommt von `NV_PRINTK(warn, cli, ...)` und nennt den DRM-Client; der
GL-Testprozess lief unter Xwayland. Jetzt wörtlich zitiert.

**3. Falscher Stack-Frame als Messung ausgegeben**
Cover schrieb `<- dma_resv_wait_timeout <- ttm_bo_delayed_delete`. **Beobachtet
wurde `ttm_bo_fini`.** Dass die operative Wartestelle `ttm_bo_delayed_delete`
ist, ist eine Schlussfolgerung aus `chrome-deadlock.md` (Inlining statischer
Funktionen), keine Messung. Jetzt steht der beobachtete Frame im Zitat und die
Schlussfolgerung daneben in Prosa.

**4. „so only a reboot cleared it" ist überzogen**
Die eigene Korrektur vom 22.07. widerlegt das: greetd respawnte labwc, das Bild
kam zurück, die Uptime lief durch. Die verkeilte Workqueue löst sich nach
Minuten per Fence-Timeout. Abgeschwächt auf „minutenlang, bis die Fences
auslaufen; ein Reboot räumt es sofort".

**5. Soak-Platzhalter gefüllt**
Aus „I will report the soak duration when I post the series" wurden **10 Tage**
(25.07. bis 04.08.), plus der Hinweis auf den Kernelwechsel 7.1.5 auf 7.1.6 am
04.08. bei unveränderter Patch-Serie.

**6. Compile-Coverage war veraltet**
Stand „downstream 7.1.5 tree", die Referenzmaschine läuft seit 04.08. auf 7.1.6.

## Muss vor dem Senden noch passieren

- **Trailer sind unvollständig.** 0001 hat ein `Signed-off-by`, aber **kein**
  `Assisted-by`; 0002 und 0003 haben `Assisted-by`, aber **kein**
  `Signed-off-by`. Der Cover behauptet „Every patch carries an Assisted-by
  trailer". Erst der SoB-Lauf aus `SENDEN.md` 2a (macht Marek selbst), dann
  0001 den `Assisted-by` nachtragen.
- **Gesoakter Code ist nicht byte-gleich mit der Einreichung.** Das lokal
  laufende 0019 trägt einen Modulparameter `chan_kill_event` (7 Fundstellen,
  Default 1, live auf 1), die einzureichende `v2-0002` schaltet
  `NV50_CHANNEL_GPFIFO` bedingungslos frei. Bei Default ist das Verhalten
  identisch, aber der Cover darf nicht suggerieren, exakt dieser Diff sei
  gesoakt worden. Entsprechend präzisiert.
- **base-commit ist 10 Tage alt** (`3dab139d4795`, rust-fixes-7.2-2). Vor dem
  Senden Sparse-Tree fetchen und neu rebasen, sonst stimmt „rebased onto
  current mainline" nicht mehr.
- **Zusage aus dem Cover ist offen:** „a separate, pre-existing problem that I
  will report separately" zum drm_panic-ioremap. Seit 02.06. nicht gemeldet.
  Entweder melden oder die Formulierung entschärfen.
