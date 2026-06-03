# Design: Patch 0010 — reactive EVO display-channel recovery (dispnv50/nvkm)

**Created:** 2026-06-03
**Hardware:** Apple Macmini3,1, GeForce 9400M (NVAC / MCP79/MCP7A), PCI 10DE:0861
**Kernel:** 7.0.11-gentoo-dist, out-of-tree patched nouveau (OE)
**Status:** design / spec (no code written yet)
**Related:** root-cause analysis in the nv50-EVO-wedge investigation (KG: "gentoo-neo Display-Wedge 2026-06-02"); precedent patches 0006 (Tesla FIFO recovery, deferred workqueue) and 0099 (debugfs fault injector).

## 1. Problem

On NVAC the nv50 EVO display engine wedges after a long display-off period: the
EVO `core` and `base`/window DMA pushbuffer channels stop advancing their GET
pointer. The first real window-flush after re-enable then blocks. `nv50_dmac_wait`
(`dispnv50/disp.c:192-225`) polls the HW GET pointer for 2000 ms, never sees
progress, and returns `-ETIMEDOUT` after `WARN_ON(1)` at `disp.c:216`. Symptom in
dmesg: `core notifier timeout` and `base-1: timeout`, repeated per commit.

The only code that unsticks such a channel is the heuristic in
`nv50_disp_core_init` (`nvkm/engine/disp/nv50.c:968-972`), which runs only on
suspend/resume/reload/coldstart (via the nvkm object lifecycle), never on the
DPMS/atomic path. Therefore today only a reboot heals it.

This is a known upstream nouveau bug class on this hardware (fdo#79532,
Mageia#27357, kernel.org#210333, RH#1898103/1900099), predating all local patches.
Confirmed via netconsole: the first wedge (02.06 23:01) began with `core notifier
timeout`, the 10.8 MB log contains zero `CACHE_ERROR`/`DMA_PUSHER`/FIFO faults, so
no FIFO path and no local patch (incl. 0006) is involved.

## 2. Goal and scope

Make a wedged EVO channel recover at runtime so no reboot is needed. Local-first
but structured for later upstream submission. Gated behind a module parameter
(default off) so the patch is inert (byte-identical timeout path) until explicitly
enabled and validated.

Out of scope: prophylactic prevention (the wedge can still occur, it just heals);
the drm-core side. The first real wedge after enabling is still required to validate
end to end.

## 3. Design overview

Reactive recovery, **deferred to a workqueue** (not inline). On `nv50_dmac_wait`
timeout, if enabled, schedule a recovery worker and fail the current commit. The
worker, in process context and serialized against the display supervisor, drives
the stuck channel(s) through a controlled fini/init cycle (which runs the core
unstick), resets the dispnv50-side pushbuffer state, and returns. The next atomic
commit then finds a healthy channel.

### 3.1 Why deferred and not inline (key safety decision)

`nv50_dmac_wait` runs in the atomic-commit path (`nv50_disp_atomic_commit_tail`,
`disp.c:2175`, in the atomic-tail worker `disp.c:2425`). The recovery touches the
same PDISP registers (`0x610200`/`0x640000`) as the display supervisor
(`disp->super.mutex`, `nv50.c:1373`) and as parallel commits, and `core_fini`/
`core_init` busy-wait up to 2000 ms each (`nv50.c:951`/`983`). Running that
synchronously inside `nv50_dmac_wait` risks deadlock against `disp->super.mutex`
and schedule-while-atomic. Patch 0006 deferred its FIFO recovery to a workqueue for
the same reason; 0010 follows that precedent.

## 4. Components

### 4.1 nvkm recovery primitive (nvkm/engine/disp/chan.c)

A per-channel recover that replicates the nvkm object fini/init sequence exactly,
not a raw `chan->func->fini/init` pair:

- fini path: `chan->func->fini(chan)` then `chan->func->intr(chan, false)`
- init path: `chan->func->intr(chan, true)` then `chan->func->init(chan)`

The `intr` toggle (`nv50_disp_chan_intr`, `nv50.c:557`, writes `0x610028`) is
mandatory and the order is inverted between the two paths (cf.
`nvkm_disp_chan_fini` chan.c:131-138 vs `nvkm_disp_chan_init` chan.c:141-147).
`fini` saves the channel PUT into `chan->suspend_put` (core: `nv50.c:959` reads
`0x640000`; dmac: `nv50.c:651` reads `0x640000 + ctrl*0x1000`); `init` writes it
back (core `nv50.c:979`, dmac `nv50.c:667`). `chan->suspend_put` (`chan.h:24`) is
managed by this roundtrip and must not be touched directly, so the channel resumes
at the correct PUT.

- Core channel (`nv50_disp_core_func`, `nv50.c:995`): fini→init is sufficient
  because `core_init` contains the unstick heuristic (`nv50.c:968-972`).
- Base/ovly dmac (`nv50_disp_dmac_func`, `nv50.c:705`; ctrl=1 base, ctrl=3 ovly):
  `dmac_init` (`nv50.c:654`) has NO unstick. If base recovery does not take in
  practice, mirror the core unstick before dmac init, addressing
  `0x610200 + ctrl*0x10`.
- `init` returns `-EBUSY` on its 2000 ms timeout (`nv50.c:677`/`989`). The recover
  primitive must check this and escalate (retry once, else leave the old behaviour)
  rather than silently continue. `fini` returns void and only WARNs.
- Multi-channel order: recover core first (it carries the method/HEAD state,
  `nv50_disp_core_mthd`), then base/ovly, because base binds via core state
  (`nv50_disp_dmac_bind`, `nv50.c:626`). For a pure base stall do not touch core.

### 4.2 nvif bridge (nvkm/engine/disp/chan.c + include/nvif/if0014.h)

The shared object func `nvkm_disp_chan` (`chan.c:164-172`) currently has no `.mthd`
callback, so any method call returns `-EINVAL`. (Note: the many `.mthd = ...` fields
in nv50.c/g84.c are the `nvkm_disp_chan_mthd` register-debug table, `chan.h:107`, a
different structure, not a callable ioctl.) Add a `.mthd` dispatcher modeled on
`nvkm_uhead` (`uhead.c:45-103`) / `nvkm_uoutp`, registered once on `nvkm_disp_chan`
so core/base/ovly/curs/oimm of all generations get it at one place.

- New in `include/nvif/if0014.h` (the header for `NVIF_CLASS_DISP_CHAN`):
  `#define NVIF_DISP_CHAN_V0_RECOVER 0x00` plus a versioned
  `nvif_disp_chan_recover_v0 { __u8 version; __u8 pad01[7]; }`. The method number is
  a `__u8` (`nvif_ioctl_mthd_v0.method`, `ioctl.h:63`); 0x00 fits.
- Handler validates `argc == sizeof(v0) && v0.version == 0` (pattern uhead.c:50),
  then calls the 4.1 recover primitive.
- Caller from dispnv50 uses the existing per-channel nvif object `dmac->base.user`
  (`disp.h:57-60`, set in `nv50_chan_create` `disp.c:93`) via `nvif_object_mthd`
  (== macro `nvif_mthd`, `object.h:37/67`). The ioctl routes
  `nvif_object_mthd -> NVIF_IOCTL_V0_MTHD -> nvkm_ioctl_mthd (core/ioctl.c:171) ->
  nvkm_object_mthd -> the new chan.c dispatcher`.

Open verification: the in-kernel nvif call path (dispnv50 client calling its own
nvkm channel method) is new; uhead/uoutp methods are called from userspace/RM
today. Check against `nvif_object_ioctl` for owner/route assumptions before relying
on it. If the in-kernel nvif path is problematic, fall back to a direct in-module
function call into the nvkm recover primitive (dispnv50 and nvkm are the same
module), keeping the recover primitive as the single source of truth.

### 4.3 dispnv50 trigger and deferral (dispnv50/disp.c)

In the `nv50_dmac_wait` timeout branch (`disp.c:212-218`):

- If `nouveau_disp_recover == 0`: keep the exact current behaviour
  (`WARN_ON(1); return -ETIMEDOUT;`), byte-identical.
- If enabled: record the stuck `nv50_dmac` (via `container_of(push, ...)`,
  `disp.c:195`) and the need for recovery, `schedule_work` on a recovery worker held
  in `nv50_disp`, and return `-ETIMEDOUT` (the current commit fails cleanly; the
  caller `nv50_disp_atomic_commit_tail` is void, no crash). Do not recover inline.

The worker (process context):
1. Serialize against the supervisor (take `disp->super.mutex` or wait for
   supervisor-pending) and against parallel commits on the affected channel.
2. Issue the nvif recover (4.2) on the core channel, then the stuck base/ovly.
3. Reset the dispnv50 pushbuffer state (4.4).
4. Clear the pending flag.

Commits arriving before the worker finishes will also time out and (re)schedule;
the worker is single-pending. After recovery the next commit's `nv50_dmac_wait`
finds a healthy channel.

### 4.4 dispnv50 pushbuffer state reset (dispnv50/disp.c)

After the HW channel is re-armed, the client-side `nv50_dmac`/`nvif_push` pointers
must be reset to the create-time values (`disp.c:259-264`) so the next kick is not
corrupt:

- `dmac->cur = 0`, `dmac->put = 0` (paired with HW PUT = 0 after re-arm; otherwise
  `nv50_dmac_kick` `disp.c:139` writes a wrong PUT).
- `push->cur = push->bgn = dmac->push.mem.object.map.ptr`,
  `push->end = map.ptr + dmac->max`.
- Do not touch `dmac->max` or `push->hw` (the live HW GET mirror, `disp.c:162`).
- After reset, the recovered `nv50_dmac_wait` (or the next one) returns 0 with an
  empty ring.

### 4.5 module parameter (nouveau_drm.c, dispnv50/disp.h)

`uint nouveau_disp_recover = 0` with `module_param_named(..., 0400)`, declared
`extern` in `dispnv50/disp.h`, placed next to the existing `runpm`/`fifo_wedge_count`
params (`nouveau_drm.c:117-129`). Default 0 keeps the timeout path byte-identical.
The recover helper itself lives in a new `dispnv50/recover.c` (added to Kbuild like
0006 added `recover.o`).

### 4.6 fault injector (separate branch, DO-NOT-MERGE)

A disp-side debugfs injector that triggers the recover path on the core / a window
dmac without a real long-off wedge, so the recovery code can be exercised in one
reboot instead of an hours-long reproduction. Structure modeled on 0099
(`DEFINE_DEBUGFS_ATTRIBUTE`, `debugfs_create_file` mode 0200, hooked in
`nouveau_debugfs.c` near `nv04_fifo_debugfs_init`), but 0099 targets nv04_fifo, so a
NEW disp injector is required (0099 is only a structural template; it needs
`nv50_disp(minor->dev)` instead of `nvxx_device(drm)->fifo`). Lives only on branch
`dev-fault-injector`, never merged.

## 5. Validation

Three stages, because each failed real-wedge attempt costs a coldboot.

- **A (static, no reboot):** `objdump -d` the new `nv50_dmac_wait` recover path
  against source; `scripts/checkpatch.pl --strict` on the generated `0010-*.patch`;
  em-dash scan on the patch.
- **B (injector-driven, one reboot):** build the 4.6 injector on `dev-fault-injector`,
  run a GL load (glxgears), `echo` into the inject file, confirm dmesg shows recovery
  instead of a bare `WARN_ON(1)` hang; test idempotency and the invalid/NULL graceful
  path; param cross-check (`disp_recover=0` vs `1`).
- **C (one real long-off run):** attempt exactly once. Display off past the wedge
  threshold, then wake. Success = no reboot needed, channel recovers, dmesg shows a
  recovery log instead of the `-ETIMEDOUT` hang. Arm netconsole + `journalctl -k`
  capture first, so a failure is forensically analysable before the coldboot.

### 5.1 Build/test loop (manual rebuild, no re-emerge)

The real build mechanism is the Portage postinst hook (`/etc/portage/bashrc:56-184`),
not the README's kernel-install.d hook (which does not exist on the host). Manual
rebuild against `/usr/src/linux-7.0.11-gentoo` (the gentoo-sources tree with .c;
`-gentoo-dist` is a header skeleton):

1. `KVER=7.0.11-gentoo-dist`, `SRC=/usr/src/linux-7.0.11-gentoo`,
   `BIN=/usr/src/linux-7.0.11-gentoo-dist`, `EXTRA=''` (KV_BASE=SRC_PV=7.0.11).
2. Edit only the `nv50_dmac_wait` timeout branch in `$SRC/.../dispnv50/disp.c`
   (0001-0006+0009 are already applied in the tree; do NOT re-apply, they reject).
3. `cp $BIN/.config .config && make ARCH=x86 EXTRAVERSION='' olddefconfig &&
   make ARCH=x86 EXTRAVERSION='' modules_prepare && cp $BIN/Module.symvers .`
4. `make ARCH=x86 EXTRAVERSION='' -j$(nproc) M=drivers/gpu/drm/nouveau modules`
5. vermagic gate: `modinfo -F vermagic .../nouveau.ko` MUST start with
   `7.0.11-gentoo-dist`. The `EXTRAVERSION=''` override is mandatory; the source
   Makefile says `-gentoo`, which without override yields the double vermagic
   `7.0.11-gentoo-gentoo-dist` and fails the gate.
6. `strip --strip-debug .../nouveau.ko` (~240 MB to ~8 MB; .config has
   CONFIG_DEBUG_INFO=y).
7. Backup the running module to `nouveau.ko.stock` FIRST (reversible via
   coldboot+restore, since reactive recovery is untested), then
   `install -m0644 .../nouveau.ko $MODDIR/nouveau.ko && depmod -a $KVER`. No
   vmlinuz/initramfs needed (nouveau is a module).
8. After validation, extract the source diff as
   `~/projects/nouveau-nvac-patches/0010-*.patch`, copy to
   `/etc/kernel/nouveau-patches/`, reset the source tree, so the bashrc hook
   re-applies it on future gentoo-kernel-bin updates.

## 6. Open questions and risks

1. **Reactive recovery is unproven.** The `core fini: 8f0e0008` rmmod log shows fini
   *survives* a stuck channel, NOT that init+unstick then heals it (no productive
   init followed during rmmod). Whether fini→init+unstick actually revives a real
   wedged channel is the central hypothesis to validate (stages B/C).
2. **Base/ovly has no unstick.** `dmac_init` lacks the core's heuristic; base
   recovery may need a mirrored unstick on `0x610200 + ctrl*0x10`.
3. **Unstick mask match.** The heuristic targets
   `(0x610200 & 0x009f0000)==0x00020000` / `(&0x003f0000)==0x00030000`. The observed
   stuck core value during the live freeze read 0x2d0b001b (a non-wedged active
   state, that was a different OOM/TTM freeze, not the EVO wedge), so the real
   wedge's 0x610200 value still has to be captured (the recovery log should dump it).
4. **In-kernel nvif path** (4.2) is new and needs checking; direct in-module call is
   the fallback.
5. **Deferral correctness:** the worker must not race the supervisor; locking to be
   nailed in the implementation plan.

## 7. Files touched

- `include/nvif/if0014.h` (new method + versioned args)
- `nvkm/engine/disp/chan.c` (recover primitive + `.mthd` dispatcher + registration)
- `dispnv50/disp.c` (timeout-branch trigger, deferral worker, state reset)
- `dispnv50/disp.h` (extern param)
- `dispnv50/recover.c` (new; recover helper) + Kbuild
- `nouveau_drm.c` (module_param)
- injector: `nouveau_debugfs.c` + new file, branch `dev-fault-injector` only

## 8. Branching

Param + recover primitive + bridge + worker land on `v2-prep` (where 0006/0009
live). The injector is DO-NOT-MERGE on `dev-fault-injector`. Default-off keeps
`master`/`v2-prep` safe.
