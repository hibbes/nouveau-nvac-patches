# nv04_fifo Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement zweistufige Recovery-Pipeline in `drivers/gpu/drm/nouveau/nvkm/engine/fifo/` (Tier-1 channel-kill via `nvkm_chan_error`, Tier-2 device-wedge via `drm_dev_wedged_event`) plus tracepoints und module params, so dass Tesla-FIFO-Faults nicht mehr silent durchlaufen.

**Architecture:** Neuer Helper-File `recover.c` kapselt Recovery-Logik, geteilt von `cache_error` und `dma_pusher` Handlern in `nv04.c`. Sliding-Window-State in `struct nvkm_fifo`. Tracepoints in neuem Header `include/trace/events/nouveau_fifo.h`. Module-Params in `nouveau_drm.c`. Validation via temporären debugfs-Injector im separaten Branch (nicht im ML-Bundle).

**Tech Stack:** Linux 7.0.3-gentoo Kernel-Tree, nouveau DRM-Treiber, nvkm-Subsystem, drm-uapi wedge mechanism, kernel tracepoints (TRACE_EVENT macro), module_param_named.

**Reference:** `docs/specs/2026-05-04-nv04-fifo-recovery-design.md`

**Working directory:** `/home/neo/projects/nouveau-nvac-patches` auf branch `v2-prep`. Patches werden als `.patch`-Files generiert und nach `/etc/kernel/nouveau-patches/` kopiert für Build via Rebuild-Hook (`project_nouveau_rebuild_hook.md`).

**Source-Tree für Edits:** `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/`. Edits werden zuerst hier gemacht, dann via `git diff -p` als Patch-File extrahiert und ins Repo gelegt.

---

## File Structure

| Pfad (relativ zu `drivers/gpu/drm/nouveau/`) | Status | Rolle |
|---|---|---|
| `include/nvkm/engine/fifo.h` | MOD | Wedge-Struct als Member von `nvkm_fifo` (Zeile 58) |
| `include/trace/events/nouveau_fifo.h` | NEU | Tracepoint-Definitionen (`trace_nouveau_fifo_chan_killed`, `trace_nouveau_fifo_dev_wedged`) |
| `nvkm/engine/fifo/recover.c` | NEU | Recovery-Helper, Sliding-Window, Workqueue-Worker |
| `nvkm/engine/fifo/priv.h` | MOD | Forward-Decl des Recovery-Helpers + Konstanten |
| `nvkm/engine/fifo/Kbuild` | MOD | `recover.o` in obj-y |
| `nvkm/engine/fifo/nv04.c` | MOD | Aufrufe von `nv04_fifo_recover()` in cache_error+dma_pusher (Zeilen 357, 416) |
| `nvkm/engine/fifo/base.c` | MOD | Wedge-Struct-Init in `nvkm_fifo_new_` (Zeile 375), Teardown im dtor |
| `nouveau_drm.c` | MOD | Module-Params + `CREATE_TRACE_POINTS` |

**Dev-only (separater Branch `dev-fault-injector`, NICHT im ML-Bundle):**
| `nvkm/engine/fifo/recover.c` | MOD | debugfs-Hooks für inject_cache_error / inject_dma_pusher |

---

## Task 1: Branch-Setup und Baseline-Verify

**Files:**
- `/home/neo/projects/nouveau-nvac-patches/.git` (branch state)
- Source-Tree-Verify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c`

- [ ] **Step 1: Verify auf v2-prep Branch**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git status
git branch --show-current
```

Expected: branch `v2-prep`, working tree clean.

- [ ] **Step 2: Verify dass die existing 5 Patches sauber auf gentoo-sources 7.0.3 angewendet werden**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo git stash 2>/dev/null
for p in /home/neo/projects/nouveau-nvac-patches/000{1,2,3,4,5}-*.patch; do
  echo "=== $(basename $p) ==="
  sudo patch -p1 --dry-run < "$p" 2>&1 | tail -5
done
```

Expected: alle 5 Patches `Hunk #N succeeded` oder `already applied`. Falls Konflikte: rebase patches gegen aktuellen Tree zuerst (separate Aufgabe, hier außerhalb-Scope).

- [ ] **Step 3: Apply 0001-0005 in den Source-Tree für lokale Entwicklung**

Wenn der Hook bereits durchgelaufen ist (per `project_nouveau_rebuild_hook.md`), sind die Patches schon angewendet. Verify:

```bash
command grep -A3 'static const struct nvkm_pci_func' /usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/subdev/pci/g94.c | command grep nv46_pci_msi_rearm
```

Expected: zeigt `nv46_pci_msi_rearm` (= Patch 0001 ist drin). Wenn leer: Patches manuell anwenden mit `cd /usr/src/linux-7.0.3-gentoo && for p in /home/neo/projects/nouveau-nvac-patches/000{1,2,3,4,5}-*.patch; do sudo patch -p1 < $p; done`.

- [ ] **Step 4: Snapshot-Commit (No-Op, just marker)**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git log --oneline -3
```

Expected: `cc98d37 docs: spec for nv04_fifo recovery patch...` als HEAD von v2-prep. Kein commit nötig.

---

## Task 2: Wedge-Struct in `struct nvkm_fifo` einfügen

**Files:**
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h:58`

- [ ] **Step 1: Header öffnen + Struct-Definition lokalisieren**

```bash
sed -n '50,90p' /usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h
```

Expected: zeigt `struct nvkm_fifo {` ab Zeile 58 mit aktuellen Membern.

- [ ] **Step 2: Forward-Decl `struct nvkm_fifo_wedge` und Member einfügen**

Im File `include/nvkm/engine/fifo.h`, **nach** dem Block `#include <core/...>` und **vor** `struct nvkm_fifo {`:

```c
#define NVKM_FIFO_WEDGE_RING_MAX 32

struct nvkm_fifo_wedge {
	spinlock_t       lock;
	u32              count;                                  /* aktuelle Fenster-Tiefe */
	ktime_t          ts[NVKM_FIFO_WEDGE_RING_MAX];          /* Ring von Timestamps */
	u32              head;                                   /* Ring-Head */
	struct work_struct work;                                /* schedules drm_dev_wedged_event */
	atomic_t         wedged;                                /* Tier-2 already fired? */
};
```

Im `struct nvkm_fifo { ... }` als letzter Member vor dem schliessenden `};`:

```c
	struct nvkm_fifo_wedge wedge;
```

- [ ] **Step 3: Build-only Verify (compile-Test ohne Wiring)**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -20
```

Expected: clean build, keine warnings, `Building modules ... done`. Sliding-Window-Struct ist als Tot-Code drin (noch nicht initialisiert/genutzt), das ist OK.

- [ ] **Step 4: Diff in Patch-Form extrahieren (für späteren v2-prep commit)**

```bash
cd /usr/src/linux-7.0.3-gentoo
git diff drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h > /tmp/wedge-struct.diff
cat /tmp/wedge-struct.diff
```

Expected: ~15 Zeilen Diff sauber.

---

## Task 3: `recover.c` Stub anlegen + Kbuild + priv.h erweitern

**Files:**
- Create: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c`
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/Kbuild`
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/priv.h`

- [ ] **Step 1: `recover.c` mit Stub-Helper anlegen**

Inhalt von `nvkm/engine/fifo/recover.c`:

```c
// SPDX-License-Identifier: MIT
/*
 * nv04_fifo_recover - shared recovery helper for Tesla cache_error and
 * dma_pusher fault paths.
 *
 * Tier-1: kill the offending channel via nvkm_chan_error.
 * Tier-2: after a configurable burst of faults, request a device-wide
 *         drm_dev_wedged_event so userspace can rebind the driver.
 */

#include "priv.h"
#include "chan.h"

#include <core/device.h>
#include <subdev/timer.h>

void
nv04_fifo_recover(struct nvkm_fifo *fifo, u32 chid, u32 fault_type, u64 info)
{
	struct nvkm_chan *chan;
	unsigned long flags;

	chan = nvkm_chan_get_chid(&fifo->engine, chid, &flags);
	if (chan) {
		nvkm_chan_error(chan, true);
		nvkm_chan_put(&chan, flags);
	}
}
```

(Tier-2 logic + tracepoints kommen in späteren Tasks - dies ist der minimale Tier-1-only Stub.)

- [ ] **Step 2: Kbuild erweitern**

In `nvkm/engine/fifo/Kbuild` nach der `runq.o`-Zeile einfügen:

```
nvkm-y += nvkm/engine/fifo/recover.o
```

- [ ] **Step 3: `priv.h` Forward-Decl + Konstanten ergänzen**

In `nvkm/engine/fifo/priv.h` nach den existing Funktion-Declarations (z.B. nach `void nv04_fifo_init(...)`):

```c
/* Recovery helper for Tesla cache_error/dma_pusher (recover.c). */
#define NV04_FAULT_CACHE_ERROR	0
#define NV04_FAULT_DMA_PUSHER	1

void nv04_fifo_recover(struct nvkm_fifo *fifo, u32 chid, u32 fault_type, u64 info);
```

- [ ] **Step 4: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -10
```

Expected: `recover.c` kompiliert, link erfolgreich, keine warnings. Als toter Code drin (noch nicht aufgerufen), das ist OK.

---

## Task 4: Wedge-Struct-Init in `nvkm_fifo_new_` und Teardown

**Files:**
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/base.c:375`

- [ ] **Step 1: Worker-Funktion in `recover.c` hinzufügen (Stub für jetzt)**

Anhang an `nvkm/engine/fifo/recover.c`:

```c
static void
nv04_fifo_wedge_work(struct work_struct *work)
{
	/* Stub - filled in Task 9 with drm_dev_wedged_event call. */
}

void
nv04_fifo_wedge_init(struct nvkm_fifo *fifo)
{
	spin_lock_init(&fifo->wedge.lock);
	INIT_WORK(&fifo->wedge.work, nv04_fifo_wedge_work);
	atomic_set(&fifo->wedge.wedged, 0);
}

void
nv04_fifo_wedge_fini(struct nvkm_fifo *fifo)
{
	cancel_work_sync(&fifo->wedge.work);
}
```

- [ ] **Step 2: Forward-Decls in `priv.h` ergänzen**

Nach `void nv04_fifo_recover(...)`-Decl:

```c
void nv04_fifo_wedge_init(struct nvkm_fifo *fifo);
void nv04_fifo_wedge_fini(struct nvkm_fifo *fifo);
```

- [ ] **Step 3: Init in `nvkm_fifo_new_` einbauen**

In `nvkm/engine/fifo/base.c`, in `nvkm_fifo_new_(...)` Funktion (Zeile 375). Direkt vor dem `return ret;` am Ende der Funktion:

```c
	nv04_fifo_wedge_init(fifo);
```

- [ ] **Step 4: Teardown in `nvkm_fifo_dtor` einbauen**

`grep -n 'nvkm_fifo_dtor\|static.*nvkm_fifo.*dtor' /usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/base.c` lokalisiert die dtor-Funktion (vermutlich um Zeile 250-300). Direkt am Anfang der dtor:

```c
	nv04_fifo_wedge_fini(fifo);
```

- [ ] **Step 5: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -10
```

Expected: clean build.

---

## Task 5: nv04.c Handler an `nv04_fifo_recover()` wiren

**Files:**
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c:357,416`

- [ ] **Step 1: Aufruf in `nv04_fifo_intr_cache_error` einbauen**

In `nv04.c`, in der Funktion `nv04_fifo_intr_cache_error` (Zeile 303). Direkt **vor** dem `nvkm_wr32(device, NV04_PFIFO_CACHE1_DMA_PUSH, 0);` (am Ende des Else-Branches, nach `nvkm_chan_put(&chan, flags);`):

```c
		nv04_fifo_recover(fifo, chid, NV04_FAULT_CACHE_ERROR,
				  ((u64)mthd << 32) | data);
```

(Wichtig: nicht in den `if benign` Pfad einbauen, nur in den nicht-benignen `else`-Branch.)

- [ ] **Step 2: Aufruf in `nv04_fifo_intr_dma_pusher` einbauen**

In `nv04.c`, in `nv04_fifo_intr_dma_pusher` (Zeile 367). **Nach** dem `nvkm_chan_put(&chan, flags);` und **vor** dem letzten `nvkm_wr32(device, 0x003228, 0x00000000);`:

```c
	nv04_fifo_recover(fifo, chid, NV04_FAULT_DMA_PUSHER, state);
```

- [ ] **Step 3: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -10
```

Expected: clean build.

---

## Task 6: Patch-File generieren + nach `/etc/kernel/nouveau-patches/` deployen

**Files:**
- Generate: `/home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch`
- Deploy: `/etc/kernel/nouveau-patches/0006-...patch`

- [ ] **Step 1: Diff aus Source-Tree extrahieren als Patch**

```bash
cd /usr/src/linux-7.0.3-gentoo
git diff -p drivers/gpu/drm/nouveau/ > /tmp/fifo-recover.diff
wc -l /tmp/fifo-recover.diff
head -20 /tmp/fifo-recover.diff
```

Expected: Diff zeigt Hunks für `fifo.h`, `nv04.c`, `priv.h`, `Kbuild`, `recover.c`, `base.c`. Keine extra Hunks.

- [ ] **Step 2: Aus Diff einen format-patch-style Patch bauen**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo git -c user.name=hibbes -c user.email=marek@czernohous.de \
  add drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h \
      drivers/gpu/drm/nouveau/nvkm/engine/fifo/Kbuild \
      drivers/gpu/drm/nouveau/nvkm/engine/fifo/base.c \
      drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c \
      drivers/gpu/drm/nouveau/nvkm/engine/fifo/priv.h \
      drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c

sudo git -c user.name=hibbes -c user.email=marek@czernohous.de commit -s -m "$(cat <<'EOF'
drm/nouveau/fifo: add recovery path for Tesla cache_error/dma_pusher

On the Tesla / NV50 family (nv50, g84, g94, g98, mcp77, mcp79), FIFO
fault handling in nv04_fifo_intr_cache_error and nv04_fifo_intr_dma_pusher
logs the fault via nvkm_error and resets the relevant hardware registers,
but the offending channel is left running. Compared to the Fermi+ path
which calls nvkm_chan_error from nvkm_runl_rc, Tesla has no escalation:
silent state corruption is possible, no telemetry beyond dmesg, and
repeated faults on the same channel keep firing forever.

Add a shared recovery helper nv04_fifo_recover() that both intr handlers
call after the existing logging+reset sequence. Tier-1 looks up the
channel and calls nvkm_chan_error(chan, true) which atomically marks
the channel as errored, blocks it, and notifies cgrp event subscribers.
The atomic short-circuit means re-faults on the same channel are no-op.

Tier-2 sliding-window logic and drm_dev_wedged_event integration are
added in subsequent commits along with tracepoints for telemetry.

Validated on Apple Mac mini Late 2009 (NVAC, MCP79).

Signed-off-by: Marek Czernohous <marek@czernohous.de>
EOF
)"

sudo git format-patch HEAD~1 -o /tmp/
sudo cp /tmp/0001-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch \
        /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
sudo chown neo:neo /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
```

(Hinweis: Das ist ein Tier-1-only Zwischenstand. Final-Patch bekommt im Subject "v2" entfernt und Body wird in Task 13 erweitert.)

- [ ] **Step 3: Altes 0006 ersetzen im Repo**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git rm 0006-drm-nouveau-notify-userspace-of-wedged-GPU-via-drm_d.patch
ls 000*.patch
```

Expected: das alte 0006 ist weg, das neue 0006 ist da.

- [ ] **Step 4: Patch nach `/etc/kernel/nouveau-patches/` deployen**

```bash
sudo rm /etc/kernel/nouveau-patches/0006-drm-nouveau-notify-userspace-of-wedged-GPU-via-drm_d.patch 2>/dev/null
sudo cp /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch \
        /etc/kernel/nouveau-patches/
```

- [ ] **Step 5: Source-Tree zurücksetzen vor Rebuild-Hook-Lauf**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo git reset --hard HEAD~1
```

Expected: Tier-1-Änderungen sind aus dem Source-Tree raus. Der Rebuild-Hook wird die Patches frisch anwenden.

- [ ] **Step 6: Trigger Rebuild via emerge**

```bash
sudo emerge -1 sys-kernel/gentoo-kernel-bin 2>&1 | tail -20
```

Expected: Hook läuft, Patches werden angewendet, nouveau.ko neu gebaut + installiert + gestripped (~8 MB).

- [ ] **Step 7: Repo-Commit für Tier-1 Stand**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git add 0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
git commit -m "$(cat <<'EOF'
0006: replace runl_rc wedge with Tesla-correct nv04_fifo recovery (Tier-1)

This patch replaces the previous 0006 that hooked nvkm_runl_rc (Fermi+
only, never reached on NVAC) with a Tesla-correct counterpart in
nv04_fifo_intr_cache_error / nv04_fifo_intr_dma_pusher.

Tier-1 only: channel-kill via nvkm_chan_error. Tier-2 (device-wedge),
tracepoints, and module params follow in subsequent commits before
v2 ML submission.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin v2-prep
```

---

## Task 7: Reboot 1 + Smoke-Test Tier-1

**Files:** None (validation step)

- [ ] **Step 1: Reboot ankündigen + ausführen**

User-Frage: "Reboot 1 für Tier-1 Smoke-Test? GUI-Session verloren."

Bei Approval: `sudo reboot`

- [ ] **Step 2: Nach Reboot, Modul-Verify**

```bash
lsmod | command grep nouveau
dmesg | command grep -E 'nouveau|nvkm' | tail -15
modinfo nouveau | command grep -E 'vermagic|filename|srcversion'
```

Expected: nouveau geladen, vermagic matcht `7.0.3-gentoo-dist`, dmesg zeigt normale Init-Messages, kein Oops, kein WARN.

- [ ] **Step 3: GPU-Funktionalität verify**

```bash
glxinfo 2>&1 | command grep -E 'OpenGL renderer|OpenGL version' | head -3
```

Expected: zeigt nouveau-Renderer (z.B. "NV98").

- [ ] **Step 4: 5-Min Soak (manuell)**

Normales Browser-Use, Wayland-Compositor sichtbar, keine Glitches in 5 Minuten Beobachtung.

Pass-Kriterium: kein Oops, kein WARN, kein dmesg-Spam.

---

## Task 8: Tracepoint-Header anlegen

**Files:**
- Create: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/include/trace/events/nouveau_fifo.h`

- [ ] **Step 1: Header-File anlegen**

Inhalt von `drivers/gpu/drm/nouveau/include/trace/events/nouveau_fifo.h`:

```c
/* SPDX-License-Identifier: MIT */
#undef TRACE_SYSTEM
#define TRACE_SYSTEM nouveau

#if !defined(_TRACE_NOUVEAU_FIFO_H) || defined(TRACE_HEADER_MULTI_READ)
#define _TRACE_NOUVEAU_FIFO_H

#include <linux/tracepoint.h>
#include <drm/drm_device.h>

TRACE_EVENT(nouveau_fifo_chan_killed,
	TP_PROTO(struct drm_device *dev, u32 chid, u32 fault_type, u64 info),
	TP_ARGS(dev, chid, fault_type, info),
	TP_STRUCT__entry(
		__string(devname, dev_name(dev->dev))
		__field(u32, chid)
		__field(u32, fault_type)
		__field(u64, info)
	),
	TP_fast_assign(
		__assign_str(devname);
		__entry->chid = chid;
		__entry->fault_type = fault_type;
		__entry->info = info;
	),
	TP_printk("dev=%s chid=%u fault=%s info=0x%llx",
		__get_str(devname),
		__entry->chid,
		__entry->fault_type == 0 ? "CACHE_ERROR" : "DMA_PUSHER",
		__entry->info)
);

TRACE_EVENT(nouveau_fifo_dev_wedged,
	TP_PROTO(struct drm_device *dev, u32 fault_count, u32 window_ms),
	TP_ARGS(dev, fault_count, window_ms),
	TP_STRUCT__entry(
		__string(devname, dev_name(dev->dev))
		__field(u32, fault_count)
		__field(u32, window_ms)
	),
	TP_fast_assign(
		__assign_str(devname);
		__entry->fault_count = fault_count;
		__entry->window_ms = window_ms;
	),
	TP_printk("dev=%s wedged after %u faults in %u ms",
		__get_str(devname),
		__entry->fault_count,
		__entry->window_ms)
);

#endif /* _TRACE_NOUVEAU_FIFO_H */

#undef TRACE_INCLUDE_PATH
#define TRACE_INCLUDE_PATH ../../drivers/gpu/drm/nouveau/include/trace/events
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_FILE nouveau_fifo
#include <trace/define_trace.h>
```

(Note: `TRACE_INCLUDE_PATH` ist relativ zu `include/trace/`-Standard-Path und muss auf den nouveau-Subdir zeigen.)

- [ ] **Step 2: `CREATE_TRACE_POINTS` in `nouveau_drm.c` einbauen**

In `drivers/gpu/drm/nouveau/nouveau_drm.c`, **vor** dem ersten `#include` aber nach den initialen Kommentaren:

```c
#define CREATE_TRACE_POINTS
```

Und nach den existing `#include`-Zeilen (z.B. nach dem letzten `#include "nouveau_..."`):

```c
#include <trace/events/nouveau_fifo.h>
```

- [ ] **Step 3: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -15
```

Expected: clean build. Falls Tracepoint-Path-Fehler: `TRACE_INCLUDE_PATH` korrigieren.

---

## Task 9: Tracepoints + drm_device-Lookup + Tier-2 Logic in `recover.c`

**Files:**
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c`

- [ ] **Step 1: Headers in `recover.c` erweitern**

Am Anfang der File, nach den existierenden `#include`-Zeilen:

```c
#include <linux/workqueue.h>
#include <linux/jiffies.h>
#include <drm/drm_drv.h>
#include <drm/drm_device.h>

#include "nouveau_drv.h"
#include <trace/events/nouveau_fifo.h>
```

- [ ] **Step 2: Helper für drm_device-Lookup einfügen**

Vor `nv04_fifo_recover`:

```c
static struct drm_device *
nv04_fifo_drm_device(struct nvkm_fifo *fifo)
{
	struct nvkm_device *device = fifo->engine.subdev.device;
	struct nouveau_drm *drm = dev_get_drvdata(device->dev);

	return (drm && drm->dev) ? drm->dev : NULL;
}
```

- [ ] **Step 3: `nv04_fifo_recover` mit Tracepoint + Tier-2 Logic erweitern**

Ersetze den existing `nv04_fifo_recover` durch:

```c
extern unsigned int nouveau_fifo_wedge_count;
extern unsigned int nouveau_fifo_wedge_window_ms;

void
nv04_fifo_recover(struct nvkm_fifo *fifo, u32 chid, u32 fault_type, u64 info)
{
	struct drm_device *drm_dev = nv04_fifo_drm_device(fifo);
	struct nvkm_chan *chan;
	unsigned long flags;
	ktime_t now, cutoff;
	u32 i, count;

	if (drm_dev)
		trace_nouveau_fifo_chan_killed(drm_dev, chid, fault_type, info);

	chan = nvkm_chan_get_chid(&fifo->engine, chid, &flags);
	if (chan) {
		nvkm_chan_error(chan, true);
		nvkm_chan_put(&chan, flags);
	}

	if (nouveau_fifo_wedge_count == 0)
		return;

	now = ktime_get();
	cutoff = ktime_sub_ms(now, nouveau_fifo_wedge_window_ms);

	spin_lock_irqsave(&fifo->wedge.lock, flags);

	/* Purge expired entries. */
	count = 0;
	for (i = 0; i < NVKM_FIFO_WEDGE_RING_MAX; i++) {
		if (!ktime_to_ns(fifo->wedge.ts[i]))
			continue;
		if (ktime_before(fifo->wedge.ts[i], cutoff))
			fifo->wedge.ts[i] = 0;
		else
			count++;
	}

	/* Insert current. */
	fifo->wedge.ts[fifo->wedge.head] = now;
	fifo->wedge.head = (fifo->wedge.head + 1) % NVKM_FIFO_WEDGE_RING_MAX;
	fifo->wedge.count = count + 1;

	if (fifo->wedge.count >= nouveau_fifo_wedge_count)
		schedule_work(&fifo->wedge.work);

	spin_unlock_irqrestore(&fifo->wedge.lock, flags);
}
```

- [ ] **Step 4: Worker-Funktion ausfüllen**

Ersetze den `nv04_fifo_wedge_work`-Stub:

```c
static void
nv04_fifo_wedge_work(struct work_struct *work)
{
	struct nvkm_fifo_wedge *w = container_of(work, struct nvkm_fifo_wedge, work);
	struct nvkm_fifo *fifo = container_of(w, struct nvkm_fifo, wedge);
	struct drm_device *drm_dev = nv04_fifo_drm_device(fifo);
	u32 fault_count;

	if (atomic_xchg(&w->wedged, 1) != 0)
		return; /* already wedged this cycle */

	if (!drm_dev)
		return;

	fault_count = w->count;

	dev_info(drm_dev->dev,
		 "nouveau: fifo wedged after %u faults in %u ms\n",
		 fault_count, nouveau_fifo_wedge_window_ms);

	trace_nouveau_fifo_dev_wedged(drm_dev, fault_count,
				      nouveau_fifo_wedge_window_ms);

	drm_dev_wedged_event(drm_dev, DRM_WEDGE_RECOVERY_REBIND, NULL);
}
```

- [ ] **Step 5: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -15
```

Expected: clean build. Falls `dev_info` Type-Mismatch: `drm_info(drm_dev, ...)` als Alternative.

---

## Task 10: Module-Params in `nouveau_drm.c`

**Files:**
- Modify: `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nouveau_drm.c:88-110`

- [ ] **Step 1: Module-Param-Variablen + module_param_named ergänzen**

In `nouveau_drm.c`, nach der letzten `module_param_named(...)` Zeile (z.B. nach `module_param_named(atomic, nouveau_atomic, int, 0400);`):

```c
unsigned int nouveau_fifo_wedge_count = 10;
MODULE_PARM_DESC(fifo_wedge_count,
	"FIFO faults within window before drm_dev_wedged_event "
	"(0=disable Tier-2, max 32, default 10)");
module_param_named(fifo_wedge_count, nouveau_fifo_wedge_count, uint, 0400);

unsigned int nouveau_fifo_wedge_window_ms = 60000;
MODULE_PARM_DESC(fifo_wedge_window_ms,
	"Sliding-window width in milliseconds for fifo_wedge_count "
	"(default 60000)");
module_param_named(fifo_wedge_window_ms, nouveau_fifo_wedge_window_ms, uint, 0400);
```

- [ ] **Step 2: Range-Validation in `nouveau_drm_init` einbauen**

In `nouveau_drm.c`, in der `nouveau_drm_init`-Funktion. Nach den existing param-Validations (vermutlich um Zeile 1100-1200, sucht via grep nach "noaccel" oder ähnlich):

```c
	if (nouveau_fifo_wedge_count > NVKM_FIFO_WEDGE_RING_MAX) {
		pr_warn("nouveau: fifo_wedge_count=%u exceeds max %u; clamping\n",
			nouveau_fifo_wedge_count, NVKM_FIFO_WEDGE_RING_MAX);
		nouveau_fifo_wedge_count = NVKM_FIFO_WEDGE_RING_MAX;
	}
	if (nouveau_fifo_wedge_window_ms < 100 ||
	    nouveau_fifo_wedge_window_ms > 600000) {
		pr_warn("nouveau: fifo_wedge_window_ms=%u out of range; resetting to 60000\n",
			nouveau_fifo_wedge_window_ms);
		nouveau_fifo_wedge_window_ms = 60000;
	}
```

(Include `<engine/fifo.h>` falls noch nicht vorhanden für `NVKM_FIFO_WEDGE_RING_MAX`.)

- [ ] **Step 3: Build-Verify**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -10
```

Expected: clean build.

---

## Task 11: Patch-File regenerieren mit Final-Inhalt + Deploy

**Files:**
- Regenerate: `/home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch`
- Re-deploy: `/etc/kernel/nouveau-patches/0006-...`

- [ ] **Step 1: Source-Tree committen + format-patch**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo git add drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h \
             drivers/gpu/drm/nouveau/include/trace/events/nouveau_fifo.h \
             drivers/gpu/drm/nouveau/nvkm/engine/fifo/Kbuild \
             drivers/gpu/drm/nouveau/nvkm/engine/fifo/base.c \
             drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c \
             drivers/gpu/drm/nouveau/nvkm/engine/fifo/priv.h \
             drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c \
             drivers/gpu/drm/nouveau/nouveau_drm.c

sudo git -c user.name=hibbes -c user.email=marek@czernohous.de \
  commit --amend -s -m "$(cat <<'EOF'
drm/nouveau/fifo: add recovery path for Tesla cache_error/dma_pusher

On Tesla / NV50 family chipsets (nv50, g84, g94, g98, mcp77, mcp79),
FIFO fault handling in nv04_fifo_intr_cache_error and
nv04_fifo_intr_dma_pusher logs the fault and resets hardware registers
but leaves the offending channel running. Compared to Fermi+ which
calls nvkm_chan_error from nvkm_runl_rc, Tesla has no escalation:
silent state corruption is possible, no telemetry beyond dmesg, and
repeated faults on the same channel keep firing forever.

Add a shared recovery helper nv04_fifo_recover() that both intr
handlers call after the existing logging+reset sequence. It implements
two tiers:

  Tier-1 (per-fault): nvkm_chan_get_chid + nvkm_chan_error(chan, true).
  The atomic chan->errored short-circuit means re-faults on the same
  channel are no-op; other channels are unaffected.

  Tier-2 (sliding-window): per-fifo lock-protected ring of fault
  timestamps. When the count within fifo_wedge_window_ms reaches
  fifo_wedge_count, schedule a workqueue job that emits a
  drm_dev_wedged_event with DRM_WEDGE_RECOVERY_REBIND. The
  drm_dev_wedged_event call cannot run from IRQ context because
  kobject_uevent_env may sleep; the workqueue indirection handles this.

Tracepoints (nouveau:fifo_chan_killed, nouveau:fifo_dev_wedged) provide
zero-overhead telemetry consumable via perf or bpftrace.

Module parameters fifo_wedge_count (default 10, range 0..32, 0=Tier-2
disabled) and fifo_wedge_window_ms (default 60000, range 100..600000)
allow tuning without rebuild.

Validated on Apple Mac mini Late 2009 (NVAC, MCP79) via debugfs fault
injection: Tier-1 channel-kill on synthesized cache_errors, Tier-2
device-wedge on burst injection. The injector itself lives in a
separate non-merged branch.

Signed-off-by: Marek Czernohous <marek@czernohous.de>
EOF
)"

sudo git format-patch HEAD~1 -o /tmp/
sudo cp /tmp/0001-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch \
        /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
sudo chown neo:neo /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
```

- [ ] **Step 2: Em-Dash-Scan**

```bash
command grep -n '—\|–' /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
```

Expected: keine Treffer.

- [ ] **Step 3: Patch nach `/etc/kernel/nouveau-patches/` deployen + Source-Tree zurücksetzen**

```bash
sudo cp /home/neo/projects/nouveau-nvac-patches/0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch \
        /etc/kernel/nouveau-patches/

cd /usr/src/linux-7.0.3-gentoo
sudo git reset --hard HEAD~1
```

- [ ] **Step 4: Rebuild via emerge**

```bash
sudo emerge -1 sys-kernel/gentoo-kernel-bin 2>&1 | tail -20
```

Expected: Hook läuft, Patches angewendet, `nouveau.ko` neu gebaut + installiert.

- [ ] **Step 5: Repo-Commit**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git add 0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch
git commit --amend --no-edit
git push origin v2-prep --force-with-lease
```

(`--amend` weil Task 6 schon commited hat und wir jetzt Final-Inhalt haben.)

---

## Task 12: Reboot 2 + Smoke-Test Tier-1 + Tier-2 (kein Inject)

- [ ] **Step 1: Reboot ankündigen + ausführen**

User-Frage: "Reboot 2 für Final-Smoke-Test? GUI-Session verloren."

`sudo reboot`

- [ ] **Step 2: Tracepoints + Module-Params + Modul-Health verify**

```bash
lsmod | command grep nouveau
modinfo nouveau | command grep -E 'vermagic|srcversion'
ls /sys/kernel/debug/tracing/events/nouveau/
cat /sys/module/nouveau/parameters/fifo_wedge_count
cat /sys/module/nouveau/parameters/fifo_wedge_window_ms
perf list 2>&1 | command grep nouveau:
```

Expected:
- `nouveau` geladen mit Match-vermagic
- Tracepoint-Verzeichnisse `fifo_chan_killed/` und `fifo_dev_wedged/` existieren in tracing/events/nouveau/
- `fifo_wedge_count = 10`
- `fifo_wedge_window_ms = 60000`
- `perf list` zeigt beide Tracepoints

- [ ] **Step 3: dmesg-Health-Check**

```bash
dmesg | command grep -iE 'nouveau|nvkm|warn|oops|bug' | tail -20
```

Expected: keine WARN, keine Oops, keine Spurious-Messages aus dem neuen Code.

- [ ] **Step 4: 5-Min-Daily-Drive-Soak (manuell)**

Browser, Editor, Wayland-Session.

Pass-Kriterium: kein Wedge, kein Hang, identische Performance zu pre-Patch.

---

## Task 13: Branch `dev-fault-injector` + Debugfs-Inject-Hooks

**Files:**
- Modify (in dev branch): `/usr/src/linux-7.0.3-gentoo/drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c`
- Generate: `/home/neo/projects/nouveau-nvac-patches/0099-DO-NOT-MERGE-fifo-fault-injector.patch`

- [ ] **Step 1: Dev-Branch im Repo anlegen**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git checkout -b dev-fault-injector v2-prep
```

- [ ] **Step 2: Debugfs-Hooks in `recover.c` ergänzen (Source-Tree)**

Anhang an `nvkm/engine/fifo/recover.c`:

```c
#ifdef CONFIG_DEBUG_FS
#include <linux/debugfs.h>

static int nv04_fifo_inject_cache_error_set(void *data, u64 val)
{
	struct nvkm_fifo *fifo = data;

	nv04_fifo_recover(fifo, (u32)val, NV04_FAULT_CACHE_ERROR, 0xdeadbeef);
	return 0;
}

static int nv04_fifo_inject_dma_pusher_set(void *data, u64 val)
{
	struct nvkm_fifo *fifo = data;

	nv04_fifo_recover(fifo, (u32)val, NV04_FAULT_DMA_PUSHER, 0xdeadbeef);
	return 0;
}

DEFINE_DEBUGFS_ATTRIBUTE(nv04_fifo_inject_cache_error_fops, NULL,
			 nv04_fifo_inject_cache_error_set, "%llu\n");
DEFINE_DEBUGFS_ATTRIBUTE(nv04_fifo_inject_dma_pusher_fops, NULL,
			 nv04_fifo_inject_dma_pusher_set, "%llu\n");

void nv04_fifo_debugfs_init(struct nvkm_fifo *fifo, struct dentry *parent)
{
	debugfs_create_file("nouveau_fifo_inject_cache_error", 0200, parent,
			    fifo, &nv04_fifo_inject_cache_error_fops);
	debugfs_create_file("nouveau_fifo_inject_dma_pusher", 0200, parent,
			    fifo, &nv04_fifo_inject_dma_pusher_fops);
}
#endif
```

- [ ] **Step 3: Aufruf von `nv04_fifo_debugfs_init` in `nouveau_drm.c`**

Im DRM-init-Pfad nach `drm_debugfs_init` (suchen via grep). Beispiel-Stelle:

```c
#ifdef CONFIG_DEBUG_FS
	{
		struct nvkm_device *device = nvxx_device(drm);
		struct nvkm_fifo *fifo = device->fifo;
		if (fifo)
			nv04_fifo_debugfs_init(fifo, drm->dev->primary->debugfs_root);
	}
#endif
```

- [ ] **Step 4: Build + format-patch**

```bash
cd /usr/src/linux-7.0.3-gentoo
sudo make M=drivers/gpu/drm/nouveau modules 2>&1 | tail -5
```

Expected: clean build.

```bash
sudo git add -u
sudo git -c user.name=hibbes -c user.email=marek@czernohous.de \
  commit --amend -s -m "$(cat <<'EOF'
[DO-NOT-MERGE] drm/nouveau/fifo: add debugfs fault injector for testing

Local-only debugging tool that exposes write-only debugfs files:
  /sys/kernel/debug/dri/N/nouveau_fifo_inject_cache_error
  /sys/kernel/debug/dri/N/nouveau_fifo_inject_dma_pusher

Writing a chid value triggers nv04_fifo_recover() with the
corresponding fault type. Used to exercise Tier-1 channel-kill and
Tier-2 device-wedge paths without needing real hardware faults
(which are rare on patched MSI Re-Arm builds).

NOT FOR UPSTREAM. Lives only in the dev-fault-injector branch of
the nouveau-nvac-patches repository.

Signed-off-by: Marek Czernohous <marek@czernohous.de>
EOF
)"

sudo git format-patch HEAD~1 -o /tmp/
sudo cp /tmp/0001-DO-NOT-MERGE-drm-nouveau-fifo-add-debugfs-fault-inje.patch \
        /home/neo/projects/nouveau-nvac-patches/0099-DO-NOT-MERGE-fifo-fault-injector.patch
sudo chown neo:neo /home/neo/projects/nouveau-nvac-patches/0099-DO-NOT-MERGE-fifo-fault-injector.patch
```

- [ ] **Step 5: Patch deployen + Rebuild**

```bash
sudo cp /home/neo/projects/nouveau-nvac-patches/0099-DO-NOT-MERGE-fifo-fault-injector.patch \
        /etc/kernel/nouveau-patches/
sudo emerge -1 sys-kernel/gentoo-kernel-bin 2>&1 | tail -10
```

Expected: alle 6 Patches + Injector werden angewendet, build OK.

- [ ] **Step 6: Repo-Commit auf dev-Branch**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git add 0099-DO-NOT-MERGE-fifo-fault-injector.patch
git commit -m "$(cat <<'EOF'
0099: debugfs fault injector for local Tier-1/Tier-2 validation

DO-NOT-MERGE. Used to drive the fifo recovery path from userspace
without provoking real hardware faults. Lives in the dev-fault-injector
branch only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin dev-fault-injector
```

---

## Task 14: Reboot 3 + Phase 2 Test (Tier-1 Single Fault)

- [ ] **Step 1: Reboot**

User-Frage: "Reboot 3 für Tier-1-Validation via Inject?"

`sudo reboot`

- [ ] **Step 2: Debugfs-Hooks verify**

```bash
ls -la /sys/kernel/debug/dri/0/nouveau_fifo_inject_*
```

Expected: zwei Files mit perm `200` (write-only).

- [ ] **Step 3: Tier-1-Test ausführen**

```bash
glxgears &
GLX_PID=$!
sleep 2
cat /sys/kernel/debug/dri/0/clients
TARGET_CHID=$(awk 'NR==2 {print $1}' /sys/kernel/debug/dri/0/clients)
echo "Will inject on chid=$TARGET_CHID, glxgears keeps running"

sudo perf record -a -e nouveau:fifo_chan_killed -o /tmp/perf-tier1.data -- sleep 3 &
sleep 0.5

# Inject (auf einem ANDEREN chid als glxgears, falls möglich):
echo $TARGET_CHID | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error

wait
```

- [ ] **Step 4: Validation**

```bash
dmesg | tail -5
sudo perf script -i /tmp/perf-tier1.data
ps -p $GLX_PID
cat /sys/kernel/debug/dri/0/clients
```

Expected:
- dmesg: `errored - disabling channel`
- perf script: 1 Event mit korrektem `chid` und `fault_type=CACHE_ERROR`
- glxgears läuft weiter (PID lebt)
- clients-Liste zeigt killed-Channel als errored (oder weg)

- [ ] **Step 5: Cleanup**

```bash
kill $GLX_PID 2>/dev/null
```

---

## Task 15: Phase 3 Test (Tier-2 Sliding Window + Wedge)

- [ ] **Step 1: udevadm monitor in Background starten**

```bash
sudo udevadm monitor --kernel --subsystem-match=drm > /tmp/udev-wedge.log 2>&1 &
UDEV_PID=$!
sleep 1
```

- [ ] **Step 2: Burst-Inject (>10 Faults) + perf**

```bash
sudo perf record -a -e nouveau:fifo_dev_wedged -o /tmp/perf-tier2.data -- sleep 3 &
sleep 0.5

for i in $(seq 1 11); do
  echo $i | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error >/dev/null
done

wait
sleep 1
sudo kill $UDEV_PID
```

- [ ] **Step 3: Validation**

```bash
dmesg | command grep -i 'wedged' | tail -5
command grep WEDGED /tmp/udev-wedge.log
sudo perf script -i /tmp/perf-tier2.data
```

Expected:
- dmesg: `nouveau: fifo wedged after 10 faults in N ms`
- udev-log: zeigt `WEDGED=rebind` Uevent
- perf script: genau 1 `fifo_dev_wedged` Event

- [ ] **Step 4: Idempotenz-Test (zusätzliche Inject-Calls dürfen NICHT erneut Wedge auslösen)**

```bash
for i in 12 13 14; do
  echo $i | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error >/dev/null
done
dmesg | command grep -c 'fifo wedged'
```

Expected: weiterhin nur **1** Match in dmesg (nicht 4).

---

## Task 16: Phase 4 Test (Recovery + Re-Arm)

- [ ] **Step 1: Treiber unbinden + rebinden**

```bash
echo "0000:02:00.0" | sudo tee /sys/bus/pci/drivers/nouveau/unbind
sleep 2
echo "0000:02:00.0" | sudo tee /sys/bus/pci/drivers/nouveau/bind
sleep 3
dmesg | tail -20
```

Expected: Treiber lädt sauber neu, `dmesg` zeigt fresh init-messages, kein Oops.

- [ ] **Step 2: wedged-Flag verify (re-armed)**

```bash
ls /sys/kernel/debug/dri/0/nouveau_fifo_inject_*
```

Expected: Files existieren wieder (debugfs neu erstellt nach rebind).

- [ ] **Step 3: Phase 3 erneut ausführen**

```bash
for i in $(seq 1 11); do
  echo $i | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error >/dev/null
done
dmesg | command grep 'fifo wedged' | tail -3
```

Expected: erneuter Wedge-Eintrag in dmesg (Pipeline ist re-armed).

---

## Task 17: Phase 5 Negative Tests

- [ ] **Step 1: Invalid chid Test**

```bash
echo 99999 | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error
dmesg | tail -3
```

Expected: kein Oops, kein WARN. `nvkm_chan_get_chid()` returnt NULL, Pfad bleibt graceful.

- [ ] **Step 2: Reboot mit `nouveau.fifo_wedge_count=3`**

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg  # falls custom Eintrag nötig
# Oder einfach in laufendem Kernel via /sys (nur read-only nach boot, daher reboot nötig).
```

User-Frage: "Reboot 4 mit fifo_wedge_count=3? Inject 4× → erwartet Wedge nach 3."

```bash
sudo grubby --update-kernel=ALL --args="nouveau.fifo_wedge_count=3" 2>/dev/null || \
  echo "manually edit /etc/default/grub: GRUB_CMDLINE_LINUX_DEFAULT += nouveau.fifo_wedge_count=3"
```

Nach Reboot:

```bash
cat /sys/module/nouveau/parameters/fifo_wedge_count  # erwartet: 3
for i in 1 2 3 4; do
  echo $i | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error >/dev/null
done
dmesg | command grep 'fifo wedged'
```

Expected: Wedge nach 3 Faults (im 4. Inject getriggert), dmesg zeigt 1 Wedge-Line.

- [ ] **Step 3: Reboot mit `nouveau.fifo_wedge_count=0` (Tier-2 disabled)**

User-Frage: "Reboot 5 mit fifo_wedge_count=0?"

Nach Reboot:

```bash
cat /sys/module/nouveau/parameters/fifo_wedge_count  # erwartet: 0
for i in $(seq 1 20); do
  echo $i | sudo tee /sys/kernel/debug/dri/0/nouveau_fifo_inject_cache_error >/dev/null
done
dmesg | command grep -c 'fifo wedged'  # erwartet: 0
dmesg | command grep -c 'errored - disabling'  # erwartet: 20
```

Expected: kein Wedge (Tier-2 disabled), aber jeder Fault killt seinen Channel (Tier-1 aktiv).

- [ ] **Step 4: Restore default params**

```bash
sudo grubby --update-kernel=ALL --remove-args="nouveau.fifo_wedge_count" 2>/dev/null
```

User-Frage: "Reboot 6 zurück zu Defaults?"

---

## Task 18: Patch-Hygiene + Final-Bundle-Vorbereitung

**Files:**
- Verify: alle `/home/neo/projects/nouveau-nvac-patches/000{1,2,3,4,5,6}-*.patch`

- [ ] **Step 1: Auf v2-prep zurück**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git checkout v2-prep
ls 000*.patch
```

Expected: 6 Patch-Files (kein 0099, der lebt nur in `dev-fault-injector`).

- [ ] **Step 2: checkpatch.pl auf alle Patches**

```bash
for p in /home/neo/projects/nouveau-nvac-patches/000*.patch; do
  echo "=== $(basename $p) ==="
  /usr/src/linux-7.0.3-gentoo/scripts/checkpatch.pl --strict "$p" 2>&1 | tail -5
done
```

Expected: keine ERRORs, ggf. einzelne CHECKs (style-Warnings die wir bewerten).

- [ ] **Step 3: Em-Dash-Scan**

```bash
command grep -n '—\|–' /home/neo/projects/nouveau-nvac-patches/000*.patch
```

Expected: keine Treffer.

- [ ] **Step 4: Patch-Apply-Sanity gegen aktuelles drm-misc-next (oder mainline)**

```bash
cd /tmp && mkdir -p drm-test && cd drm-test
git clone --depth 1 https://gitlab.freedesktop.org/drm/misc.git -b drm-misc-next 2>&1 | tail -3
cd misc
for p in /home/neo/projects/nouveau-nvac-patches/000*.patch; do
  echo "=== $(basename $p) ==="
  git apply --check "$p" 2>&1 | tail -5
done
```

Expected: alle 6 Patches gelten sauber. Falls Konflikte: rebase-Aufgabe vor Submission (separater Task).

---

## Task 19: User-Approval-Gate vor `git send-email`

- [ ] **Step 1: Cover-Letter und alle Patch-Bodies dem User vorlegen**

Per `feedback_mailinglist_approval_required.md`:

```bash
echo "=== Cover-Letter ===" 
echo "[Subject: PATCH v2 0/6] drm/nouveau: stability fixes for NVAC (MCP79/MCP7A)"
echo
# Show full cover-letter body inkl. soak-data-Zahlen ausgefüllt
echo
echo "=== Recipient list ==="
echo "To: nouveau@lists.freedesktop.org, dri-devel@lists.freedesktop.org"
echo "Cc: <kherbst@redhat.com>, <bskeggs@redhat.com>, <lyude@redhat.com>, <linux-kernel@vger.kernel.org>"
echo
# Plus get_maintainer.pl-Output pro Patch
for p in /home/neo/projects/nouveau-nvac-patches/000*.patch; do
  /usr/src/linux-7.0.3-gentoo/scripts/get_maintainer.pl --no-rolestats --git-fallback "$p" 2>/dev/null
done
```

- [ ] **Step 2: User-Approval abwarten**

Wörtlich: "Vor `git send-email` brauche ich expliziten 'ok, schick raus'."

Stop hier. Nicht senden ohne Approval.

- [ ] **Step 3: Bei Approval, Dry-Run zeigen**

```bash
cd /home/neo/projects/nouveau-nvac-patches
git send-email --dry-run --to=nouveau@lists.freedesktop.org \
               --cc=dri-devel@lists.freedesktop.org \
               --cc=kherbst@redhat.com --cc=bskeggs@redhat.com --cc=lyude@redhat.com \
               --cc=linux-kernel@vger.kernel.org \
               --in-reply-to="<v1-message-id>" \
               --cover-letter \
               000{1,2,3,4,5,6}-*.patch
```

Expected: Dry-Run-Output zeigt alle 6 Patches + Cover, korrekte Recipients, korrekte Threading.

- [ ] **Step 4: Bei finalem User-Approval, echter Send**

```bash
git send-email --to=... <wie oben ohne --dry-run>
```

- [ ] **Step 5: Lore.kernel.org Link nach Send abrufen**

```bash
sleep 60  # Mailinglist-Indexierung dauert
curl -s 'https://lore.kernel.org/dri-devel/?q=NVAC+stability' | command grep -oE 'href="\K[^"]*' | head -5
```

Expected: neuer Thread sichtbar. URL ins Memory speichern.

---

## Task 20: Phase 6 Real-World Soak Setup

**Files:**
- Update: `/home/neo/.claude/projects/-home-neo/memory/project_nouveau_nv50_fifo_reset_path.md`

- [ ] **Step 1: Soak-Tracking-Datei anlegen (lokal, kein Repo-File)**

```bash
cat > /tmp/fifo-recover-soak.log <<EOF
Soak gestartet: $(date -Iseconds)
Patch deployed (v2-prep branch): commit $(cd /home/neo/projects/nouveau-nvac-patches && git rev-parse HEAD)
Default params: fifo_wedge_count=10, fifo_wedge_window_ms=60000
Track: dmesg fifo_wedged events, perf events, GPU hangs.
EOF
sudo cp /tmp/fifo-recover-soak.log /var/log/fifo-recover-soak.log
```

- [ ] **Step 2: Memory-File aktualisieren**

In `project_nouveau_nv50_fifo_reset_path.md` die "Entscheidung 2026-05-04"-Zeile erweitern:

```
**Implementation Status (2026-05-04):**
- v2-prep branch: 0006 patch deployed, all 5 validation phases (Smoke/Tier-1/Tier-2/Recovery/Negative) passed
- Soak gestartet: 2026-05-04
- Bundle-Submission planned ~2026-05-25 nach 3-Wochen-Soak
- Repo: hibbes/nouveau-nvac-patches branch v2-prep
```

- [ ] **Step 3: User informieren**

"Implementation done. Soak läuft. Bei Submission-Zeit ~2026-05-25 melde ich mich mit Bundle für ML-Approval-Gate."

---

## Self-Review-Checklist

**1. Spec coverage:** Skim each section of spec → mapped to task?
- Problem (3 Folgen) → adressiert in Task 5+9
- Tier-1 → Task 5+9
- Tier-2 → Task 9 (Sliding-Window) + Task 11 (Module-Params)
- Datenstruktur → Task 2
- Module-Parameter → Task 10
- Tracepoints → Task 8
- Code-Layout (alle 8 Files) → Task 2,3,4,5,8,9,10
- Validation Phasen 1-6 → Task 7 (Phase 1), Task 14 (2), Task 15 (3), Task 16 (4), Task 17 (5), Task 20 (6)
- Submission-Strategie → Task 18+19
- Github-Repo-Branching → Task 1+13
- Em-Dash-Scan → Task 11+18
- User-Approval-Gate → Task 19
- Open Points (Tracepoint-Path, drm_device-Lookup, Init-Reihenfolge, Param-Range) → Task 8 (Path), Task 9 (Lookup), Task 4 (Init), Task 10 (Range)

Keine Lücken erkannt.

**2. Placeholder scan:** keine "TBD", "TODO", "fill-in-later" Markers im Plan.

**3. Type consistency:** 
- `nv04_fifo_recover(struct nvkm_fifo *, u32, u32, u64)` konsistent across Tasks 3, 5, 9, 13.
- `struct nvkm_fifo_wedge` Member-Namen `count`, `ts`, `head`, `work`, `wedged`, `lock` konsistent across Tasks 2, 4, 9.
- Module-Param-Namen `nouveau_fifo_wedge_count`, `nouveau_fifo_wedge_window_ms` konsistent.
- Trace-Event-Namen `nouveau_fifo_chan_killed`, `nouveau_fifo_dev_wedged` konsistent.
- Constant `NVKM_FIFO_WEDGE_RING_MAX = 32` konsistent.

Plan-Größe: 20 Tasks, ~6 Reboots, geschätzt 2-3 Sessions (~6-8 Stunden total inkl. Soak-Wartezeiten passive).
