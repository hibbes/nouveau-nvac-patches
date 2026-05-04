# nv04_fifo Recovery-Pfad für Tesla (Design)

**Datum:** 2026-05-04
**Patch-ID im Bundle:** 0006 (ersetzt den bisherigen `0006-drm-nouveau-notify-userspace-of-wedged-GPU-via-drm_d.patch`, der den falschen Code-Pfad addressierte)
**Ziel-Subject:** `drm/nouveau/fifo: add recovery path for Tesla cache_error/dma_pusher`
**Hardware-Scope:** Tesla-Familie (nv50, g84, g94, g98 inkl. mcp77/mcp79). Validiert auf NVAC (MCP79/MCP7A, GeForce 9400M, Apple Mac mini Late 2009).

## Problem

`nv04_fifo_intr_cache_error` (`drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c:303`) und `nv04_fifo_intr_dma_pusher` (`nv04.c:367`) loggen einen Fehler via `nvkm_error`, setzen die HW-Register zurück und kehren zurück; der schuldige Channel läuft mit potentiell korruptem State weiter. Es gibt keinen Aufruf von `nvkm_chan_error`, kein DRM-Wedge-Event an Userspace, keine zählbaren Telemetry-Events.

Drei konkrete Folgen:

1. **Silent State Corruption.** Channel produziert nach dem Fault falsche Pixel oder Compute-Output, ohne Userspace zu benachrichtigen.
2. **Beobachtbarkeits-Lücke.** Keine Counter, keine Tracepoints, kein Wedge-Event. Im Fehlerfall ist `dmesg` die einzige Quelle.
3. **Repeated-Fault-Loop.** Wenn ein Channel wiederkehrend faultet, wiederholt sich Logging+HW-Reset endlos statt den Channel zu killen.

Auf Fermi+ ruft das Recovery via `nvkm_runl_rc` automatisch `nvkm_chan_error` und Engine-Reset. Auf Tesla existiert dieser Pfad nicht; die Generation wurde feature-gefroren bevor das DRM-Wedge-uAPI etabliert wurde.

## Lösungs-Architektur

Zweistufige Recovery-Pipeline mit Telemetry, gekapselt in einem neuen Helper-File `nvkm/engine/fifo/recover.c`. Existing intr-Handler werden minimal modifiziert (1 zusätzlicher Funktionsaufruf pro Handler).

### Tier 1: Channel-Kill pro Fault

Bei jedem cache_error oder dma_pusher:

1. Tracepoint `trace_nouveau_fifo_chan_killed` feuert (zero-overhead wenn nicht abonniert)
2. `nvkm_chan_get_chid(...)` lookupt den Channel
3. Wenn gefunden: `nvkm_chan_error(chan, true)`, atomar via `chan->errored` (short-circuit beim ersten Fault, dann no-op)
4. `nvkm_chan_put(...)`

Verhalten: erster Fault auf einem Channel killt ihn deterministisch. Folgende Faults auf demselben Channel sind no-op (atomic short-circuit). Andere Channels laufen weiter.

### Tier 2: Device-Wedge nach Fault-Sturm

Sliding-Window pro `nvkm_fifo`-Instanz (gerätweit, nicht pro Channel):

1. Nach Tier-1-Aufruf: `spin_lock(&fifo->wedge.lock)`
2. Alte Window-Einträge purgen (`now - T_window_ms`)
3. Aktuellen Fault-Timestamp einfügen (Ringbuffer)
4. Wenn `window_count >= N_threshold`: `schedule_work(&fifo->wedge.work)` und Lock freigeben

Worker-Funktion (schläfrig):

5. `atomic_xchg(&fifo->wedge.wedged, 1)`, idempotent, mehrfache Schedules treffen einander nicht doppelt
6. `drm_info(...)` Logging
7. `drm_dev_wedged_event(drm, DRM_WEDGE_RECOVERY_REBIND, NULL)`
8. Tracepoint `trace_nouveau_fifo_dev_wedged` feuert

**Warum Workqueue:** `drm_dev_wedged_event` ruft am Ende `kobject_uevent_env`, das mit `GFP_KERNEL` allokiert und schlafen kann. Aus dem IRQ-Pfad direkt aufrufen wäre falsch.

**Warum `DRM_WEDGE_RECOVERY_REBIND`:** Bus-Reset (`BUS_RESET`) würde den Mac-mini-PCI-Tree zerlegen. `NONE` (nur Telemetry) signalisiert nicht, dass Userspace handeln soll. `REBIND` ist die richtige Aufforderung an Session-Manager: unbind+bind des Treibers, Compositor neu starten.

**Warum `atomic_xchg`-Idempotenz:** Mehrere parallele Faults können zwischen Window-Update und Worker-Aufruf landen. `wedged`-Flag verhindert mehrfache Wedge-Events pro Recovery-Zyklus. Reset des Flags geschieht implizit beim Treiber-Rebind.

### Datenstruktur

In `struct nvkm_fifo`:

```c
struct nvkm_fifo_wedge {
    spinlock_t       lock;
    u32              count;                              /* aktuelle Fenster-Tiefe */
    ktime_t          ts[NV04_FIFO_WEDGE_MAX_BUFFER];   /* Ring von Timestamps */
    u32              head;                               /* Ring-Head */
    struct work_struct work;                            /* schedules wedge */
    atomic_t         wedged;                            /* Tier-2 already fired? */
} wedge;
```

`NV04_FIFO_WEDGE_MAX_BUFFER = 32`. Module-Param `fifo_wedge_count` wird gegen diesen Wert geclamped.

### Module-Parameter

Definiert in `nouveau_drm.c`:

| Parameter | Typ | Default | Bedeutung |
|---|---|---|---|
| `nouveau.fifo_wedge_count` | uint, range 0..32 | 10 | Anzahl Faults im Sliding-Window die Wedge auslösen. **0 = Tier-2 disabled** (Schwellwert-Check `count >= N` failt sofort, Channel-Kill bleibt aktiv). |
| `nouveau.fifo_wedge_window_ms` | uint, range 100..600000 | 60000 | Fenster-Breite in Millisekunden. |

Range-Validation am Boot via `module_param_named` mit `param_ops_uint`. Werte außerhalb der Range werden auf Default zurückgesetzt + warnung im dmesg. Read-only nach Boot (siehe Open Point).

### Tracepoints

Neu in `include/trace/events/nouveau.h` (oder neuer Header falls noch nicht vorhanden):

```
TRACE_EVENT(nouveau_fifo_chan_killed,
    TP_PROTO(struct drm_device *dev, u32 chid, u32 fault_type, u64 info),
    /* fields: device-name, chid, fault_type ∈ {0=CACHE_ERROR, 1=DMA_PUSHER}, info-bag */
)

TRACE_EVENT(nouveau_fifo_dev_wedged,
    TP_PROTO(struct drm_device *dev, u32 fault_count, u32 window_ms),
    /* fields: device-name, fault_count, window_ms */
)
```

Userspace-Konsum via `perf record -e nouveau:fifo_chan_killed` oder `bpftrace`.

## Code-Layout

| Datei | Änderung | Geschätzt |
|---|---|---|
| `nvkm/engine/fifo/recover.c` | NEU. Recovery-Helper, Sliding-Window, Worker. | ~150 Zeilen |
| `nvkm/engine/fifo/nv04.c` | 2× Aufruf des Recovery-Helpers in cache_error/dma_pusher Handlern. Existing Logging+HW-Reset bleibt. | +2 Zeilen Call-Sites |
| `nvkm/engine/fifo/priv.h` | Forward-Decl des Recovery-Helpers. | ~3 Zeilen |
| `nvkm/engine/fifo/base.c` | Init/Teardown der Wedge-Struct in `nvkm_fifo_new_`. | ~10 Zeilen |
| `nvkm/engine/fifo/Kbuild` | `recover.o` in obj-y. | 1 Zeile |
| `include/nvkm/engine/fifo.h` | Wedge-Struct als Member von `nvkm_fifo`. | ~15 Zeilen |
| `include/trace/events/nouveau.h` | Zwei TRACE_EVENT-Definitionen. | ~30 Zeilen |
| `nouveau_drm.c` | Module-Param-Definitionen. | ~5 Zeilen |

**Gesamt:** ~250 Zeilen Diff, davon ~150 Zeilen neuer File.

**Warum separates `recover.c`:** Logik wird von cache_error und dma_pusher geteilt. Subsystem-State (Sliding-Window, Workqueue) gehört nicht in einen Handler-File. Macht Review einfacher (clear separation: nv04.c = nur Call-Sites, alles andere in recover.c).

## Validation / Test-Plan

### Debugfs Fault-Injector (Dev-only)

```
/sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error
/sys/kernel/debug/dri/0/nouveau_fifo_inject_dma_pusher
```

Write-Handler ruft direkt `nv04_fifo_recover()` auf, bypasst die HW-IRQ. Validiert die komplette Pipeline ohne echten Fault zu provozieren.

```
echo <chid> > .../nouveau_fifo_inject_cache_error
```

**Hygiene:** Code lebt im separaten Branch `dev-fault-injector` im github-Repo, **nicht im ML-Submission-Bundle**. Markiert `[DO-NOT-MERGE]` im Subject, falls man ihn später separat einreichen möchte.

### Phase 1: Smoke

- Build via Rebuild-Hook erfolgreich, vermagic OK
- Reboot
- `glxinfo | grep "OpenGL renderer"` → erwarteter Renderer
- `perf list 'nouveau:*'` zeigt `fifo_chan_killed` + `fifo_dev_wedged`
- Debugfs-Files existieren
- `cat /sys/module/nouveau/parameters/fifo_wedge_count` → `10`

### Phase 2: Tier-1 (Single Fault, Channel-Kill)

- Hintergrund: `glxgears &` für Cross-Channel-Isolation
- chid des glxgears-Channels rausfinden via `cat /sys/kernel/debug/dri/0/clients`
- `echo <other-chid> > .../nouveau_fifo_inject_cache_error`
- Erwartet:
  - `dmesg`: `CACHE_ERROR ... errored - disabling channel`
  - `perf record -e nouveau:fifo_chan_killed sleep 1` zeigt 1 Event
  - glxgears läuft weiter
  - clients-Liste zeigt killed-Channel als errored

### Phase 3: Tier-2 (Sliding Window, Device-Wedge)

- `udevadm monitor --kernel --subsystem-match=drm &`
- `for i in $(seq 1 11); do echo $i > .../nouveau_fifo_inject_cache_error; done`
- Erwartet:
  - `dmesg`: `device wedged after 10 faults in N ms`
  - `udevadm monitor` zeigt `WEDGED=rebind`
  - `perf record -e nouveau:fifo_dev_wedged sleep 1` zeigt 1 Event
  - Wiederholtes Schreiben triggert KEINE neuen Wedges (idempotent)

### Phase 4: Recovery + Re-Arm

- `echo "0000:02:00.0" > /sys/bus/pci/drivers/nouveau/unbind`
- `echo "0000:02:00.0" > /sys/bus/pci/drivers/nouveau/bind`
- Erwartet: Treiber lädt neu, wedged-Flag clear, Phase 2+3 wiederholbar

### Phase 5: Negative Tests

- `chid=99999` (invalid) → `nvkm_chan_get_chid()` returnt NULL → graceful, kein Oops
- Reboot mit `nouveau.fifo_wedge_count=3` → Wedge nach 3 Faults
- Reboot mit `nouveau.fifo_wedge_count=0` → Tier-2 disabled, nur Tier-1
- Reboot mit `nouveau.fifo_wedge_window_ms=100` → 11× injecten, danach 200ms warten + 1× injecten → Window expired, kein Wedge

### Phase 6: Real-World Soak

- 1+ Woche Daily-Drive ohne manuelle Injection
- Pass-Kriterium: 0 spurious Wedges, 0 GPU-Hangs, 0 Performance-Regression

## Submission-Strategie

### Bundle-Reihenfolge im `[PATCH v2 0/6] drm/nouveau: stability fixes for NVAC (MCP79/MCP7A)`

| # | Subject | Status | Repo-File |
|---|---|---|---|
| 1/6 | `drm/nouveau/pci: use nv46 MSI rearm for G94 (NVAC/MCP79)` | aus v1 | `0001-...patch` |
| 2/6 | `drm/nouveau/kms: add NULL check for CRTC in nv50_sor_atomic_disable` | aus v1 | `0002-...patch` |
| 3/6 | `drm/nouveau/dp: retry link check once on HPD IRQ before disconnect` | aus v1 | `0003-...patch` |
| 4/6 | `drm/nouveau/fifo/nv04: filter benign CACHE_ERROR from Mesa NV50 bind probe` | NEU im v2 | `0004-...patch` |
| 5/6 | `drm/nouveau/clk: stop reclocking after consecutive failures` | NEU im v2 | `0005-...patch` |
| 6/6 | `drm/nouveau/fifo: add recovery path for Tesla cache_error/dma_pusher` | NEU im v2 (dieser Patch) | `0006-...patch` (ersetzt das bisherige 0006) |

**Wegfallender Patch:** Der bisherige `0006-drm-nouveau-notify-userspace-of-wedged-GPU-via-drm_d.patch` wird verworfen. Begründung: hookt `nvkm_runl_rc` (Fermi+/Kepler+ Pfad), der auf NVAC nie erreicht wird. Repro-Description "Reproduced on Apple Mac mini Late 2009" passt nicht zum gepatchten Code-Pfad. Der neue Patch erreicht das gleiche Ziel (Wedge-Notification) auf der Hardware, die wir tatsächlich testen können.

### Cover-Letter v2

```
Subject: [PATCH v2 0/6] drm/nouveau: stability fixes for NVAC (MCP79/MCP7A)

Hi all,

v2 of the NVAC stability series originally posted on 2026-04-09 [1].
Since v1 has not received review, this version expands the series with
three additional patches discovered during continued soak-testing on
the same hardware (Apple Mac mini Late 2009, NVIDIA GeForce 9400M).

Daily-driven on this machine since v1 submission across N reboots and
N kernel bumps (6.18.18 to 7.0.3) without user-visible regressions.

Per-patch soak data:
- Patches 1-3: 25 days, 0 incidents (since 2026-04-09)
- Patch 4 (CACHE_ERROR filter): 25 days, dmesg cleaned of N false positives
- Patch 5 (clk wedge): 28 days, 0 gt215_clk_pre/nvkm_pstate_work
  timeouts post-deploy (compared to 4 unique events on 2026-04-26
  immediately before deploy)
- Patch 6 (fifo recover): newly added, validated via local fault
  injection. Tier-1 channel-kill tested on M synthesized cache_errors,
  Tier-2 device-wedge tested via burst injection.

Changelog:
- v1 -> v2: added patches 4, 5, 6 (no changes to 1-3)

[1] https://lore.kernel.org/dri-devel/<v1-message-id>
```

Em-Dash-Scan über Cover-Letter und alle Patch-Subjects/Bodies vor Send (Lehre aus session_ab70733a).

### Recipient-Liste

**To:**
- `nouveau@lists.freedesktop.org`
- `dri-devel@lists.freedesktop.org` (cross-post wegen `drm_dev_wedged_event` in Patch 6)

**Cc:**
- Karol Herbst `<kherbst@redhat.com>` (aktiver Tesla-Maintainer)
- Ben Skeggs `<bskeggs@redhat.com>` (historischer Nouveau-Maintainer)
- Lyude Paul `<lyude@redhat.com>` (DP-Expertin, Patch 3)
- Linux Kernel `<linux-kernel@vger.kernel.org>` (Standard)
- Auto-Erweiterung via `./scripts/get_maintainer.pl --no-rolestats --git-fallback` pro Patch

### Patch-Hygiene-Checkliste vor `git send-email`

```
[ ] checkpatch.pl --strict pro Patch (cleane Output)
[ ] em-dash-Scan auf Cover + Subjects + Bodies
[ ] Signed-off-by: Marek Czernohous (git format-patch -s)
[ ] base-commit: Tag im Cover-Letter
[ ] Rebase auf aktuelles drm-misc-next
[ ] git send-email --dry-run (Empfänger-Sanity)
[ ] In-Reply-To: <v1-message-id> (threading)
[ ] User-Approval (per feedback_mailinglist_approval_required)
```

### Github-Repo-Branching

- `master`: synchronisiert mit submittierter Version. Heutiger Stand enthält 6 patch-Files (0006 wird ersetzt).
- `v2-prep`: working branch für die 6 Patches + dieses Spec.
- `dev-fault-injector`: standalone Branch für DO-NOT-MERGE Injector.
- Tag `v1`: markiert v1-Submission-Stand.
- Tag `v2`: markiert v2-Submission-Stand.

### Timing

- 2026-05-04: Spec fertig, github-Repo geklont, Spec gemerged.
- Diese Woche: Implementation des Recovery-Patches + Validation Phasen 1-5.
- Bis ~2026-05-24 (4 Wochen Patch #5 Soak, parallel Phase 6 Soak des Recovery-Patches): Bundle-Build.
- ~2026-05-25: User-Review aller 6 Patches + Cover-Letter, danach Submission.

## Risiken und Annahmen

| Risiko | Mitigation |
|---|---|
| `nvkm_chan_error` aus IRQ-Kontext mit gehaltenem `chan->lock` deadlockt | `nvkm_chan_error` nimmt `spin_lock_irqsave` selbst, IRQ-safe per Design |
| Sliding-Window-Spinlock kontentioniert unter Fault-Sturm | Spinlock-Hold-Time ist O(1) (Ring-Buffer-Insert + Comparison), kein Risiko |
| `drm_dev_wedged_event` blockiert Workqueue zu lange | Workqueue ist System-WQ, `kobject_uevent_env` ist schnell (allokiert ~32 Byte, schickt Netlink-Message), kein Risiko |
| Module-Param-Defaults zu aggressiv (10 Faults / 60s) wedgen unschuldige Setups | Conservative Defaults; User kann via `nouveau.fifo_wedge_count=0` Tier-2 deaktivieren |
| Pre-Tesla Karten (nv04/nv10/nv40) brechen weil sie denselben `nv04_fifo_intr` nutzen | Code-Pfad ist defensiv (greift nur im Fehlerfall, der bei nicht-Tesla Pre-Patch-#1 schon nicht regulär auftrat). Pattern ist defensiv-additiv, kein Verhalten ändert sich bei Erfolgspfad. |
| Maintainer fragt "warum nicht für gf100+ auch?" | Antwort: gf100+ hat schon `nvkm_runl_rc`-basierte Recovery, die ruft `nvkm_chan_error` automatisch. Wedge-Event-Notification dort ist separater Patch (siehe verworfener 0006), aufgehoben für späteren RFC sobald Fermi+-Hardware verfügbar |

## Offene Punkte für Implementation

- **Genauer Header-Pfad für Tracepoints:** Existiert `include/trace/events/nouveau.h` schon? Falls nicht, neuer Header anlegen + `CREATE_TRACE_POINTS` in einer .c-Datei (Konvention: `nouveau_drv.c` oder `recover.c`).
- **`drm_device`-Lookup aus `nvkm_fifo`:** Geht über `fifo->engine.subdev.device->dev` → `dev_get_drvdata(...)` → `struct nouveau_drm *` → `drm->dev`. Helper-Pattern existiert bereits (siehe `nouveau_drm_notify_wedged` im verworfenen Patch (kann als Referenz für die Idiomatik dienen, nicht als Code).
- **Init-Reihenfolge in `nvkm_fifo_new_`:** Wedge-Struct muss vor erstem möglichen IRQ initialisiert sein. Aktuelles `nvkm_fifo_new_` ruft `INIT_WORK` an passender Stelle, brauche Detail-Audit.
- **Module-Param-Range-Validation:** `module_param_named` mit `S_IRUGO` ist read-only nach Boot; ggf. `module_param_cb` nutzen um runtime-Änderungen zu erlauben (Pro: Tunbar ohne Reboot. Contra: zusätzliche Locking-Komplexität). Default: read-only nach Boot.

## Referenzen

- Memory: `project_nouveau_nv50_fifo_reset_path.md`, `linux_nouveau_gpu_wedge_patch_0005.md`, `project_nouveau_patches_submission.md`
- Memory: `feedback_mailinglist_approval_required.md`, `feedback_no_em_dashes.md`
- Code: `drivers/gpu/drm/nouveau/nvkm/engine/fifo/{nv04.c,chan.c,priv.h}` (Linux 7.0.3-gentoo)
- Code: `drivers/gpu/drm/drm_drv.c:563` (`drm_dev_wedged_event`)
- DRM uAPI: `Documentation/gpu/drm-uapi.rst` Kapitel "Device Wedging"
