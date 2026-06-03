# Patch 0010: reactive EVO display-channel recovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover a wedged nv50 EVO core/base DMA channel at runtime (no reboot) by, on `nv50_dmac_wait` timeout, deferring a fini/init recovery (with the core unstick) of the stuck channel via a workqueue, gated behind a default-off module parameter.

**Architecture:** New nvkm per-channel recover primitive (`fini`->`intr`->`init`) reachable from dispnv50 through a new nvif disp-chan method. The dispnv50 timeout path schedules a workqueue worker that, under `disp->mutex`, recovers the core channel first (clears the core/base interlock) then the stuck channel, and resets the client-side pushbuffer pointers. Inert until `nouveau.disp_recover=1`.

**Tech Stack:** Linux kernel 7.0.11-gentoo, nouveau (dispnv50 + nvkm/engine/disp), nvif object/ioctl, out-of-tree module build via the Portage `bashrc` postinst hook.

**Design spec:** `docs/specs/2026-06-03-disp-evo-recovery-design.md` (read it for rationale; this plan does not repeat it).

**Branch:** all tasks except Task 8 on `v2-prep`. Task 8 (injector) on `dev-fault-injector`.

---

## Build helper (created once in Task 0, used by every code task)

Every code task ends with a **Build** that runs `~/nouveau-rebuild.sh`. It compiles only the nouveau module against the gentoo-sources tree, gates vermagic, strips, installs, depmods. **It does NOT reboot.** The new module only takes effect after a reboot (nouveau is in use), so Tasks 1-7 verify compile + static checks only; behaviour is validated under reboot in Task 8.

## File structure

- `include/nvif/if0014.h` (M): the recover method + args (the disp-chan class header).
- `nvkm/engine/disp/chan.c` (M): recover primitive, method dispatcher, `.mthd` registration.
- `nvkm/engine/disp/chan.h` (M): declare `nvkm_disp_chan_recover()`.
- `nouveau_drm.c` (M): `disp_recover` module parameter.
- `dispnv50/disp.h` (M): extern param; `nv50_dmac.disp` back-pointer; `nv50_disp.recover_work` + `nv50_disp.recover_dmac`; recover protos.
- `dispnv50/recover.c` (C): `nv50_dmac_recover()`, the worker, the schedule helper.
- `dispnv50/Kbuild` (M): add `recover.o`.
- `dispnv50/disp.c` (M): set `dmac->disp` in create; init `recover_work`; the timeout-branch trigger.
- `nouveau_debugfs.c` (M, Task 8, branch `dev-fault-injector`): debugfs recover injector.

---

## Task 0: build helper + stock backup

**Files:**
- Create: `~/nouveau-rebuild.sh`
- Backup: `/root/nouveau.ko.stock`

- [ ] **Step 1: Write the rebuild helper**

```bash
cat > ~/nouveau-rebuild.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
KVER=7.0.11-gentoo-dist
SRC=/usr/src/linux-7.0.11-gentoo
BIN=/usr/src/linux-7.0.11-gentoo-dist
MOD="$SRC/drivers/gpu/drm/nouveau/nouveau.ko"
DST="/lib/modules/$KVER/kernel/drivers/gpu/drm/nouveau/nouveau.ko"
cd "$SRC"
sudo cp "$BIN/.config" .config
sudo make ARCH=x86 EXTRAVERSION='' olddefconfig
sudo make ARCH=x86 EXTRAVERSION='' modules_prepare
sudo cp "$BIN/Module.symvers" Module.symvers
sudo make ARCH=x86 EXTRAVERSION='' -j"$(nproc)" M=drivers/gpu/drm/nouveau modules
vm=$(modinfo -F vermagic "$MOD" | head -1)
case "$vm" in 7.0.11-gentoo-dist*) echo "vermagic OK: $vm";;
  *) echo "VERMAGIC MISMATCH: $vm (check EXTRAVERSION='')"; exit 1;; esac
sudo strip --strip-debug "$MOD"
sudo install -m0644 "$MOD" "$DST"
sudo depmod -a "$KVER"
echo "installed $DST (effective after reboot)"
EOF
chmod +x ~/nouveau-rebuild.sh
```

- [ ] **Step 2: Back up the running (stock-for-us) module**

```bash
sudo cp /lib/modules/7.0.11-gentoo-dist/kernel/drivers/gpu/drm/nouveau/nouveau.ko /root/nouveau.ko.stock
ls -l /root/nouveau.ko.stock
```
Expected: ~8 MB file. This is the rollback target if a built module misbehaves (coldboot, then `install` this file + `depmod`).

- [ ] **Step 3: Baseline build (no source change yet) to prove the helper works**

Run: `~/nouveau-rebuild.sh`
Expected: `vermagic OK: 7.0.11-gentoo-dist ...` then `installed ...`. If vermagic mismatches, stop and fix `EXTRAVERSION=''` before proceeding.

- [ ] **Step 4: Commit the helper into the repo for reproducibility**

```bash
cd ~/projects/nouveau-nvac-patches
cp ~/nouveau-rebuild.sh scripts/nouveau-rebuild.sh 2>/dev/null || { mkdir -p scripts && cp ~/nouveau-rebuild.sh scripts/nouveau-rebuild.sh; }
git add scripts/nouveau-rebuild.sh
git commit -m "build: add manual nouveau module rebuild helper for patch 0010"
```

---

## Task 1: nvkm recover primitive + nvif method

**Files:**
- Modify: `/usr/src/linux-7.0.11-gentoo/drivers/gpu/drm/nouveau/include/nvif/if0014.h`
- Modify: `.../nvkm/engine/disp/chan.h`
- Modify: `.../nvkm/engine/disp/chan.c`

- [ ] **Step 1: Declare the recover method (if0014.h)**

Append inside the disp-chan args section of `include/nvif/if0014.h`:

```c
#define NVIF_DISP_CHAN_V0_RECOVER 0x00

struct nvif_disp_chan_recover_v0 {
	__u8  version;
	__u8  pad01[7];
};
```

- [ ] **Step 2: Declare the primitive (chan.h)**

Add near the other `nvkm_disp_chan_*` prototypes in `nvkm/engine/disp/chan.h`:

```c
int nvkm_disp_chan_recover(struct nvkm_disp_chan *);
```

- [ ] **Step 3: Implement primitive + dispatcher + registration (chan.c)**

Add `#include <nvif/if0014.h>` if not already present, then add:

```c
int
nvkm_disp_chan_recover(struct nvkm_disp_chan *chan)
{
	if (!chan->func->init || !chan->func->fini)
		return -EINVAL;

	chan->func->fini(chan);
	if (chan->func->intr)
		chan->func->intr(chan, false);
	if (chan->func->intr)
		chan->func->intr(chan, true);
	return chan->func->init(chan);
}

static int
nvkm_disp_chan_mthd_recover(struct nvkm_disp_chan *chan, void *argv, u32 argc)
{
	union {
		struct nvif_disp_chan_recover_v0 v0;
	} *args = argv;
	int ret = -ENOSYS;

	if (!(ret = nvif_unpack(ret, &argv, &argc, args->v0, 0, 0, false)))
		return nvkm_disp_chan_recover(chan);
	return ret;
}

static int
nvkm_disp_chan_mthd(struct nvkm_object *object, u32 mthd, void *argv, u32 argc)
{
	struct nvkm_disp_chan *chan = nvkm_disp_chan(object);

	switch (mthd) {
	case NVIF_DISP_CHAN_V0_RECOVER:
		return nvkm_disp_chan_mthd_recover(chan, argv, argc);
	default:
		return -EINVAL;
	}
}
```

Then add `.mthd = nvkm_disp_chan_mthd,` to the `nvkm_disp_chan` object func (the `struct nvkm_object_func nvkm_disp_chan` at chan.c:164-172), e.g. right after the `.fini` line.

- [ ] **Step 4: Build**

Run: `~/nouveau-rebuild.sh`
Expected: `vermagic OK ...` / `installed ...`, no compile errors. If `nvif_unpack` is missing an include, add `#include <nvif/ioctl.h>`.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/nouveau-nvac-patches
# capture the source diff into the repo (see Task 7 for the extract recipe); for now commit a WIP marker
git commit --allow-empty -m "wip(0010): nvkm disp-chan recover primitive + nvif method (built)"
```

---

## Task 2: dispnv50 plumbing (param, structs, recover.c, wiring)

**Files:**
- Modify: `.../nouveau_drm.c`
- Modify: `.../dispnv50/disp.h`
- Create: `.../dispnv50/recover.c`
- Modify: `.../dispnv50/Kbuild`
- Modify: `.../dispnv50/disp.c` (create-time wiring only; the trigger is Task 3)

- [ ] **Step 1: Module parameter (nouveau_drm.c)**

Next to the existing `nouveau_runpm` / `nouveau_fifo_wedge_count` params:

```c
MODULE_PARM_DESC(disp_recover, "Attempt runtime recovery of a wedged EVO display channel (default: 0 = off)");
unsigned int nouveau_disp_recover = 0;
module_param_named(disp_recover, nouveau_disp_recover, int, 0400);
```

- [ ] **Step 2: disp.h — extern, back-pointer, work fields, protos**

In `dispnv50/disp.h`:

```c
/* near top, after the includes */
extern unsigned int nouveau_disp_recover;
```

Add a back-pointer to `struct nv50_dmac` (so a stuck dmac can reach its disp):

```c
struct nv50_dmac {
	struct nv50_chan base;
	struct nv50_disp *disp;   /* <-- add this line */
	struct nvif_push push;
	struct nvif_object sync;
	struct nvif_object vram;
	u32 cur;
	u32 put;
	u32 max;
};
```

Add recovery state to `struct nv50_disp`:

```c
struct nv50_disp {
	struct nvif_disp *disp;
	struct nv50_core *core;
	struct nvif_object caps;
	/* ... existing SYNC defines and sync bo ... */
	struct mutex mutex;
	struct work_struct recover_work;   /* <-- add */
	struct nv50_dmac *recover_dmac;     /* <-- add: the channel that timed out */
};
```

Add prototypes:

```c
int  nv50_dmac_recover(struct nv50_dmac *);
void nv50_disp_recover_schedule(struct nv50_dmac *);
void nv50_disp_recover_work(struct work_struct *);
```

- [ ] **Step 3: recover.c (new file)**

```c
// SPDX-License-Identifier: MIT
#include "disp.h"
#include "core.h"

#include <nvif/if0014.h>
#include <nvif/push.h>

#include <nouveau_drv.h>

/* Re-arm a wedged EVO channel via the nvkm recover method, then resync the
 * client-side pushbuffer state to the freshly re-armed HW (PUT == 0).
 */
int
nv50_dmac_recover(struct nv50_dmac *dmac)
{
	struct nvif_push *push = &dmac->push;
	struct {
		struct nvif_disp_chan_recover_v0 v0;
	} args = { .v0.version = 0 };
	int ret;

	ret = nvif_object_mthd(&dmac->base.user, NVIF_DISP_CHAN_V0_RECOVER,
			       &args, sizeof(args));
	if (ret)
		return ret;

	dmac->cur = 0;
	dmac->put = 0;
	push->bgn = push->cur = dmac->push.mem.object.map.ptr;
	push->end = push->cur + dmac->max;
	return 0;
}

void
nv50_disp_recover_work(struct work_struct *work)
{
	struct nv50_disp *disp = container_of(work, typeof(*disp), recover_work);
	struct nv50_dmac *dmac = READ_ONCE(disp->recover_dmac);
	int ret;

	mutex_lock(&disp->mutex);

	/* Core first: clears the core<->base interlock that stalls base. */
	ret = nv50_dmac_recover(&disp->core->chan);
	if (ret)
		NV_ERROR(nouveau_drm(disp->core->disp->disp->object.client->device->object.parent->oclass ? NULL : NULL), "");
	/* (logging refined in Task 4; keep the recover call) */

	/* Then the specific channel that timed out, if it was not the core. */
	if (dmac && dmac != &disp->core->chan)
		nv50_dmac_recover(dmac);

	WRITE_ONCE(disp->recover_dmac, NULL);
	mutex_unlock(&disp->mutex);
}

void
nv50_disp_recover_schedule(struct nv50_dmac *dmac)
{
	struct nv50_disp *disp = dmac->disp;

	if (!disp)
		return;
	/* single-pending: last writer wins, worker re-reads core + this dmac */
	WRITE_ONCE(disp->recover_dmac, dmac);
	schedule_work(&disp->recover_work);
}
```

Note: the placeholder `NV_ERROR(...)` line above is replaced wholesale in Task 4 with real instrumentation; for Task 2 simplicity, replace Step 3's core-recover block with just:

```c
	(void)nv50_dmac_recover(&disp->core->chan);
```
and drop the NV_ERROR line. (Task 4 adds proper logging.)

- [ ] **Step 4: Kbuild**

In `dispnv50/Kbuild`, add to the `nouveau-y` list:

```make
nouveau-y += dispnv50/recover.o
```

- [ ] **Step 5: disp.c create-time wiring**

In `nv50_dmac_create` (disp.c ~231), after the `nv50_chan` is set up, set the back-pointer:

```c
	dmac->disp = nv50_disp(drm->dev);
```
(`drm` is the `struct nouveau_drm *` arg; `nv50_disp(drm->dev)` returns the `nv50_disp`.)

In `nv50_display_create` (disp.c ~2833), after `disp->mutex` is initialised, init the work:

```c
	INIT_WORK(&disp->recover_work, nv50_disp_recover_work);
```

- [ ] **Step 6: Build**

Run: `~/nouveau-rebuild.sh`
Expected: clean build, `vermagic OK`. If `nv50_disp(drm->dev)` is unavailable at that point (incomplete type), include `disp.h` is already present; verify `drm` is in scope in `nv50_dmac_create`.

- [ ] **Step 7: Commit**

```bash
git commit --allow-empty -m "wip(0010): dispnv50 recover plumbing + disp_recover param (built, inert)"
```

---

## Task 3: trigger in nv50_dmac_wait (default-off, byte-identical when off)

**Files:**
- Modify: `.../dispnv50/disp.c` (nv50_dmac_wait, disp.c:212-218)

- [ ] **Step 1: Edit the timeout branch**

Replace (disp.c:215-217):

```c
	) < 0) {
		WARN_ON(1);
		return -ETIMEDOUT;
	}
```

with:

```c
	) < 0) {
		struct nv50_dmac *dmac = container_of(push, typeof(*dmac), push);

		if (nouveau_disp_recover)
			nv50_disp_recover_schedule(dmac);
		WARN_ON(1);
		return -ETIMEDOUT;
	}
```

(`push` is the function arg; `container_of` matches `nv50_dmac_kick`/`nv50_dmac_wind` usage at disp.c:136/195.)

- [ ] **Step 2: Build**

Run: `~/nouveau-rebuild.sh`
Expected: clean build, `vermagic OK`.

- [ ] **Step 3: Verify byte-identical timeout path when disabled**

Confirm the recovery is fully gated: with the default `nouveau_disp_recover = 0`, the only added work is one branch test. Inspect the compiled function:

Run:
```bash
objdump -d /usr/src/linux-7.0.11-gentoo/drivers/gpu/drm/nouveau/nouveau.ko \
  | sed -n '/<nv50_dmac_wait>:/,/ret/p' | grep -iE 'disp_recover|recover_schedule|call' | head
```
Expected: a `call` to `nv50_disp_recover_schedule` guarded by a load of `nouveau_disp_recover`. The hot path (no timeout) is unchanged.

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "wip(0010): gate recovery on nv50_dmac_wait timeout via disp_recover (built)"
```

---

## Task 4: instrumentation (capture the real wedge register state)

**Files:**
- Modify: `.../dispnv50/recover.c`

This produces the §6.3 evidence: the actual `0x610200`/GET/PUT of the wedged channel, logged once when recovery runs.

- [ ] **Step 1: Add a pre-recover register dump**

In `nv50_dmac_recover`, before the `nvif_object_mthd` call, read and log the channel control register and GET/PUT via the channel's nvif device (dispnv50 already does raw MMIO via `nvif_rd32(&device->object, ...)`, cf. `nv50_dmac_kick` disp.c:145). Add:

```c
	struct nvif_device *device = dmac->base.device;
	u32 ctrl = ... ; /* chid.ctrl is nvkm-side; expose via the channel or log only 0x640000 GET */
```

Because `chid.ctrl` lives nvkm-side, log the client-visible GET/PUT and a generic note instead, and do the precise `0x610200` dump in the nvkm primitive (Step 2):

```c
	NV_INFO(nouveau_drm(dmac->disp->core->disp->disp->object.client->device),
		"disp: recovering EVO channel (cur=%u put=%u)\n", dmac->cur, dmac->put);
```

If the `nouveau_drm` lookup chain is awkward, use `pr_info("nouveau disp: recovering EVO channel cur=%u put=%u\n", dmac->cur, dmac->put);` for the dispnv50 side.

- [ ] **Step 2: Dump 0x610200/GET in the nvkm primitive**

In `nvkm_disp_chan_recover` (chan.c), before `fini`, log the per-channel control reg and PUT mirror (nvkm has `nvkm_rd32`):

```c
	struct nvkm_device *device = chan->disp->engine.subdev.device;
	int ctrl = chan->chid.ctrl;

	nvkm_warn(&chan->disp->engine.subdev,
		  "chan %d recover: 0x610200=%08x put=%08x\n", chan->chid.user,
		  nvkm_rd32(device, 0x610200 + ctrl * 0x10),
		  nvkm_rd32(device, 0x640000 + ctrl * 0x1000));
```

This is the definitive stuck-state capture (compare against the unstick masks `0x00020000`/`0x00030000`).

- [ ] **Step 3: Build + Commit**

Run: `~/nouveau-rebuild.sh` (expect clean), then:
```bash
git commit --allow-empty -m "wip(0010): log 0x610200/GET/PUT on recovery (register-state capture)"
```

---

## Task 5: optional base/window unstick (gated fallback)

**Files:**
- Modify: `.../nvkm/engine/disp/nv50.c` (a new dmac-recover variant) or `chan.c`

The base/ovly `dmac_init` has no unstick. The base recovery's primary path is the plain fini->init (already covered by Task 1's primitive). This task adds the mirrored core unstick on the base slot as an OPTIONAL extra attempt, only taken when the normal init leaves the state field set.

- [ ] **Step 1: Add a dmac unstick helper (nv50.c)**

```c
/* Mirror of the core unstick (nv50_disp_core_init) for a dmac slot.
 * Empirical/undocumented; never set the core-only 0x01000000 bit here.
 */
static void
nv50_disp_dmac_unstick(struct nvkm_device *device, int ctrl)
{
	if ((nvkm_rd32(device, 0x610200 + ctrl * 0x10) & 0x009f0000) == 0x00020000)
		nvkm_mask(device, 0x610200 + ctrl * 0x10, 0x00800000, 0x00800000);
	if ((nvkm_rd32(device, 0x610200 + ctrl * 0x10) & 0x003f0000) == 0x00030000)
		nvkm_mask(device, 0x610200 + ctrl * 0x10, 0x00600000, 0x00600000);
}
```

- [ ] **Step 2: Call it from the recover primitive only for a stuck dmac**

In `nvkm_disp_chan_recover` (chan.c), after the first `init` returns `-EBUSY` for a non-core channel (`chan->chid.ctrl != 0`), apply the unstick and retry init once:

```c
	ret = chan->func->init(chan);
	if (ret == -EBUSY && chan->chid.ctrl != 0) {
		nv50_disp_dmac_unstick(chan->disp->engine.subdev.device, chan->chid.ctrl);
		ret = chan->func->init(chan);
	}
	return ret;
```

(Declare `nv50_disp_dmac_unstick` in a shared header, or move the helper to chan.c. `init` returning `-EBUSY` is the existing dmac_init timeout, nv50.c:677.)

- [ ] **Step 3: Build + Commit**

Run: `~/nouveau-rebuild.sh` (expect clean), then:
```bash
git commit --allow-empty -m "wip(0010): optional mirrored unstick for stuck base/ovly dmac"
```

- [ ] **Step 4: Squash the WIP commits into the real 0010 patch**

Extract the cumulative source diff and turn it into the patch file (see Task 7).

---

## Task 6: assemble the 0010 patch + static review (no reboot)

**Files:**
- Create: `~/projects/nouveau-nvac-patches/0010-drm-nouveau-disp-reactive-evo-channel-recovery.patch`
- Create: `/etc/kernel/nouveau-patches/0010-...patch` (copy)

- [ ] **Step 1: Extract the diff as a patch**

```bash
cd /usr/src/linux-7.0.11-gentoo
git diff 2>/dev/null > /tmp/0010.diff || true   # if the tree is a git repo
# If not a git repo, diff against the bin skeleton sources or use the per-file backups.
```
If the source tree is not git-tracked, generate the patch from the edited files with `diff -u` against pristine copies saved before Task 1, or hand-author the patch from the task diffs. Save as
`~/projects/nouveau-nvac-patches/0010-drm-nouveau-disp-reactive-evo-channel-recovery.patch` with a proper `Subject:`/`Signed-off-by:` header (model on the existing `0006-*.patch`).

- [ ] **Step 2: checkpatch**

Run:
```bash
/usr/src/linux-7.0.11-gentoo/scripts/checkpatch.pl --no-tree --strict \
  ~/projects/nouveau-nvac-patches/0010-*.patch | tail -30
```
Expected: no ERRORs. Address WARNINGs that matter (line length, missing SOB).

- [ ] **Step 3: em-dash scan (user style rule)**

Run:
```bash
command grep -nP '\xe2\x80\x94|\xe2\x80\x93' ~/projects/nouveau-nvac-patches/0010-*.patch || echo "clean"
```
Expected: `clean`.

- [ ] **Step 4: Install the patch into the hook dir + commit to repo**

```bash
sudo cp ~/projects/nouveau-nvac-patches/0010-*.patch /etc/kernel/nouveau-patches/
cd ~/projects/nouveau-nvac-patches
git checkout v2-prep
git add 0010-*.patch docs/
git commit -m "0010: reactive EVO display-channel recovery (deferred, disp_recover-gated)

On nv50_dmac_wait timeout, defer a fini/init recovery of the wedged EVO core
and base/window channels to a workqueue via a new nvif disp-chan recover method,
reset the client pushbuffer state, recover on the next commit. Core first to
clear the core<->base interlock; optional mirrored unstick for a stuck dmac.
Gated behind module_param disp_recover (default off). NVAC/MCP79.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin v2-prep
```

---

## Task 7: fault injector (branch dev-fault-injector, DO-NOT-MERGE)

**Files:**
- Modify: `.../nouveau_debugfs.c`
- (injector trigger references `nv50_dmac_recover` / `nv50_disp` core+window channels)

- [ ] **Step 1: Add a debugfs recover trigger**

Model on the 0099 fifo injector. Add a `disp_recover` debugfs file (mode 0200) under the dri minor whose write callback calls `nv50_dmac_recover(&nv50_disp(minor->dev)->core->chan)` (and a `disp_recover_base` for a window dmac). Use `DEFINE_DEBUGFS_ATTRIBUTE` with a NULL read.

- [ ] **Step 2: Hook it in**

Near `nv04_fifo_debugfs_init` in `nouveau_debugfs.c`, call the new init with `minor->debugfs_root`, guarded `#if IS_ENABLED(CONFIG_DEBUG_FS)`.

- [ ] **Step 3: Build + commit on the injector branch only**

```bash
cd ~/projects/nouveau-nvac-patches && git checkout dev-fault-injector
# build, then:
git add 0099-* nouveau_debugfs changes...
git commit -m "0099: DO-NOT-MERGE add disp-channel recover injector for 0010 testing"
```

---

## Task 8: validation (the reboots happen here)

- [ ] **Step A: static (already done in Task 6)** — checkpatch clean, em-dash clean, `disp_recover=0` byte-identical hot path.

- [ ] **Step B: injector-driven (one reboot, new module loaded)**

1. Build with the injector branch merged locally, `~/nouveau-rebuild.sh`, then **reboot** (cold boot to be safe; the new module loads).
2. After boot: `sudo modprobe -r` is not possible (in use); confirm the new module is live: `dmesg | grep -i "disp: recover"` is empty (no recovery yet), `cat /sys/module/nouveau/parameters/disp_recover` shows 0.
3. Enable: reboot with `nouveau.disp_recover=1` (GRUB cmdline) OR set the param at load. Run a GL load (`glxgears`).
4. Trigger: `echo 1 | sudo tee /sys/kernel/debug/dri/0/disp_recover`.
5. Expect dmesg: the `chan N recover: 0x610200=... put=...` line and NO `nv50_dmac_wait` `WARN_ON(1)` hang; the display keeps working. Test idempotency (echo twice) and the base injector.
6. Param cross-check: with `disp_recover=0`, the trigger path must not fire (timeout still WARNs); with `=1` it recovers.

- [ ] **Step C: one real long-off run (the actual proof)**

1. Ensure `/root/nouveau.ko.stock` exists (Task 0) and netconsole + `journalctl -k -f` capture are armed (so a failure is logged before the coldboot).
2. Boot the recover-enabled module with `nouveau.disp_recover=1`.
3. Reproduce the wedge: display off (DPMS or physically) well past the threshold (hours), then wake and drive a commit.
4. **Success:** dmesg shows the `chan N recover` log + the `0x610200` stuck value (matching the unstick masks), the channel recovers, the desktop returns with NO reboot.
5. **Failure:** capture dmesg/netconsole, coldboot, restore `/root/nouveau.ko.stock` (`sudo install ... && depmod -a`), and feed the captured `0x610200` back into §6.3 to refine the unstick masks. Attempt only once per session (each failure costs a coldboot).

- [ ] **Step D: record the outcome**

Append the result (recovered / did-not-recover + the captured register values) to `docs/investigations/2026-06-xx-disp-evo-recovery-validation.md` and to the KG (Display-Wedge entity). If it recovers, promote the param default discussion and prep the upstream cover letter (drm-misc, cc Lyude/Ben Skeggs).

---

## Self-review notes

- **Spec coverage:** §3.1 deferral -> Task 2/3 worker+gate; §4.1 primitive+core-first -> Task 1 + Task 2 worker order; §4.2 nvif bridge -> Task 1; §4.3 trigger+deferral -> Task 3 + recover.c worker; §4.4 state reset -> recover.c `nv50_dmac_recover`; §4.5 param -> Task 2; §4.6 injector -> Task 7; base recovery -> Task 5; §5 validation -> Task 8; §5.1 build -> Task 0.
- **Known soft spots flagged for the implementer (not placeholders, real lookups):** the `nouveau_drm`/`NV_INFO` logging chain in recover.c (use `pr_info` if the lookup is awkward); the patch-extraction method in Task 6 (depends on whether the source tree is git-tracked). Both have a stated fallback.
- **Type consistency:** `nv50_dmac_recover`, `nv50_disp_recover_schedule`, `nv50_disp_recover_work`, `nvkm_disp_chan_recover`, `nouveau_disp_recover`, `recover_work`, `recover_dmac`, `disp` back-pointer used consistently across Tasks 1-5.
- **Locking (§6.5):** the worker takes `disp->mutex` (serialises vs dispnv50 commits). It does NOT serialise against the nvkm display supervisor; this is the main residual risk and is what Task 8B/C validate empirically. If the injector shows a supervisor race, add nvkm-side serialisation (take the disp super lock in the recover primitive) as a follow-up task.
