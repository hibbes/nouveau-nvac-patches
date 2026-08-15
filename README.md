# nouveau NVAC stability patches

Out-of-tree Linux kernel patch series providing stability fixes for the
**NVAC** chipset family (MCP79 / MCP7A integrated GeForce 9400M, part of
the NVIDIA NV50 / Tesla family). A series of small, reviewable patches that
collectively turn an out-of-the-box "boots, but flakes under load"
configuration into a daily-driver-stable system.  Patches 0001-0006 address
FIFO/PCI/DP stability; 0009-0021 address the two display-side failure classes
that surfaced later: the EVO supervisor wedge and the channel-kill dead letter.

Maintained by Marek Czernohous (hibbes) since 2026-04 against the NVIDIA
9400M IGP in an Apple Mac mini Late 2009.

## Reference hardware

| Property | Value |
|---|---|
| Machine | Apple Mac mini, Late 2009 (Macmini3,1) |
| CPU | Intel Core 2 Duo P7350 (2 x 2.0 GHz) |
| Chipset | NVIDIA MCP79 |
| GPU (IGP) | NVIDIA GeForce 9400M (NVAC, NV50 / Tesla) |
| chipid | 0xac080b1 |
| BIOS pstates | 03 (150/300 MHz, 0.90 V), 0e (350/800 MHz, 0.90 V), 0f (450/1100 MHz, 1.01 V) |
| Connector | DisplayPort over Mini-DisplayPort |

The closely related NVAA (MCP77 / MCP73) chipset has had broken-MSI
disabled in nouveau since the driver's early days. NVAC was never given
the same treatment despite identical integration-architecture
characteristics. Patch 0001 brings NVAC into line.

Other NV50 / Tesla cards (G80 - GT218) share most of the relevant code
paths; some patches (0002, 0003, 0004) are likely useful there too,
though they are validated only on NVAC.

## Why this series exists

`nouveau` mainline upstream considers Tesla support feature-frozen: GSP
firmware drives modern NVIDIA cards (Turing+), and pre-Pascal hardware
gets bug-fix maintenance only. The NVAC IGP in Mac mini 2009 falls in
the "old, low-priority" bucket: it works, but several long-standing
issues bite under regular desktop use:

- spurious PFIFO faults on DPMS resume, eventually wedging a channel
- kernel oopses on Wayland session teardown
- DisplayPort link flicker after backlight wake
- dmesg noise that obscures real problems
- a kernel WARN-loop that turns a transient channel fault into a
  3-minute hung shutdown

Each patch addresses one of these. None of them are speculative: every
patch has a concrete, reproducible failure mode on the reference
hardware, and a successful soak period before submission.

## Patch series

| # | Subject | Status |
|---|---|---|
| 0001 | drm/nouveau/pci: use nv46 MSI rearm for G94 (NVAC/MCP79) | sent ML 2026-04-09, 3-week soak reported 2026-04-26 |
| 0002 | drm/nouveau/kms: add NULL check for CRTC in nv50_sor_atomic_disable | sent ML 2026-04-09, soak reported |
| 0003 | drm/nouveau/dp: retry link check once on HPD IRQ before disconnect | sent ML 2026-04-09, soak reported |
| 0004 | drm/nouveau/fifo/nv04: filter benign CACHE_ERROR from Mesa NV50 bind probe | local only; cosmetic, ML send deferred |
| 0005 | drm/nouveau/clk: stop reclocking after consecutive failures | local only; userland-side mitigated by nouveau-pstate-daemon v0.2.0, ML send deferred |
| 0006 | drm/nouveau/fifo: add recovery path for Tesla cache_error/dma_pusher | local only; Tier-1 channel-kill + Tier-2 device-wedge with `drm_dev_wedged_event`; debugfs fault-injector validation Phases 1-5 done, Phase 6 soak in progress |
| 0009 | drm/nouveau/display: reject vblank enable on inactive CRTC | local only |
| 0010 | drm/nouveau/disp: reactive EVO channel recovery | local only; dormant knob, superseded by the S3 re-POST watchdog |
| 0011 | drm/nouveau/disp: soft-DPMS, keep head+core armed across DPMS off/on | local only; prevents the full re-program that wedges the EVO core |
| 0015 | drm/nouveau/disp: soft-DPMS lean blank suppression | local only; suppresses background base-channel repaints while blanked |
| 0016 | nvac: reclock pin | local only |
| 0017 | drm/nouveau/disp: hold flip event while blanked | local only; fixes `validate: -22` redraw corruption caused by 0015 completing flips it had suppressed |
| 0018 | drm/nouveau/disp: dump EVO push buffer on channel timeout | local only; diagnostics, no behaviour change |
| 0019 | drm/nouveau: EVO supervisor-handshake rescue + Tesla channel-kill dead-letter fix | **0020a part is an upstream candidate** (see below); rescue half is diagnose-only pending phase confirmation |
| 0020 | drm/nouveau/fifo: Tier-0 escalation ladder for Tesla CACHE_ERROR/DMA_PUSHER | local only; rework of 0006, first faults survive instead of killing the channel |
| 0021 | drm/nouveau/disp: compact supervisor snapshot around core updates | local only; diagnostics, no behaviour change |
| 0022 | drm/nouveau/fifo: debug fault injector for the Tesla recovery path | local only, **not for upstream**; drives `nv04_fifo_recover()` via two write-only module params to exercise the ladder deterministically |
| 0023 | drm/nouveau: subscribe to the channel-kill event after the fence context | local counterpart of v3 2/5 (nv04-FIFO v3 series sent ML 2026-08-13) |
| 0024 | drm/nouveau/fifo: streak cleanup only after nvkm_chid_put | local counterpart of the v3 5/5 correction (sent ML 2026-08-13) |

The **Status** column above is a snapshot. For the authoritative, dated submission
state of each track, including the nv04-FIFO v3 four-patch series sent 2026-08-13, see
[`SUBMISSION-STATUS.md`](SUBMISSION-STATUS.md).

### 0001 — pci: use nv46 MSI rearm for G94 (NVAC/MCP79)

**Problem.** On NVAC the default G94 path uses
`nv40_pci_msi_rearm()`, which re-arms MSI interrupts via memory-mapped
register access. The MMIO path is unreliable on this integrated chipset
and produces sporadic FIFO errors and GPU hangs over hours of normal
use. The closely related NVAA chipset has MSI disabled outright in the
driver with a comment marking it "reported broken".

**Fix.** Switch G94 to `nv46_pci_msi_rearm()`, which re-arms MSI via
direct PCI config-space access (`pci_write_config_byte` at offset 0x68).
This bypasses the problematic MMIO route while keeping MSI enabled.

**Result.** No `NvMSI=0` workaround needed; zero observed FIFO errors
across multi-day operation including DPMS cycles.

**Files touched.** `drivers/gpu/drm/nouveau/nvkm/subdev/pci/g94.c`
(1 LOC).

### 0002 — kms: NULL CRTC check in nv50_sor_atomic_disable

**Problem.** Race between `atomic_check` and `atomic_commit` under
Wayland compositors using atomic modesetting:
`nv_encoder->crtc` can be NULL by the time the disable callback runs.
The code dereferences via `nv50_head(nv_encoder->crtc)`, and
`container_of(NULL, ...)` returns a garbage pointer rather than NULL,
leading to a kernel oops on VT-switch or session teardown.

**Fix.** Explicit NULL check; if the CRTC is gone, release the output
resource and return early.

**Note.** This cannot be caught by checking the return value of
`nv50_head()` because `container_of(NULL, ...)` produces a non-NULL
bogus pointer. The check must happen at the source.

**Result.** Wayland session teardown and DPMS cycles are stable on
Weston / labwc.

**Files touched.** `drivers/gpu/drm/nouveau/dispnv50/disp.c` (~6 LOC).

### 0003 — dp: retry link check once on HPD IRQ before disconnect

**Problem.** Transient DisplayPort link glitches trigger an HPD IRQ
where the first `nouveau_dp_link_check()` momentarily fails. The driver
then falls through to connector status redetection and treats it as a
disconnect, producing a brief blackout followed by a re-plug. Visible
flicker after DPMS resume.

**Fix.** One retry with 100 ms delay before giving up on the link.
DisplayPort link training typically completes in a few milliseconds;
100 ms is generous enough for worst-case re-negotiation on older
hardware while imperceptible for genuine unplug events. The retry is
bounded (exactly one attempt) and applies only to the IRQ path; real
plug / unplug events are unaffected.

**Result.** Clean DPMS transitions; no flicker over extended cycle
testing.

**Files touched.** `drivers/gpu/drm/nouveau/nouveau_display.c`
(~10 LOC).

### 0004 — fifo/nv04: filter benign CACHE_ERROR from Mesa NV50 bind probe

**Problem.** The Mesa userspace driver issues a method-`0x0060` /
data-`0xbeef02xx` binding probe on Tesla GPUs at session start. The
probe is harmless and recovers cleanly, but it triggers `CACHE_ERROR`
in the PFIFO interrupt handler, flooding dmesg at error-level on every
X / Wayland session start.

**Fix.** Demote that exact pattern (`mthd & 0x1ffc == 0x0060` and
`data & 0xffffff00 == 0xbeef0200`) to debug-level. Real CACHE_ERROR
events are unaffected and still log at error.

**Character.** Cosmetic, not a stability fix. Userland workarounds
(`journalctl -p err`, rsyslog filter, `loglevel=4` boot arg) exist but
all push the noise further down the stack.

**Files touched.** `drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c`
(17 / -5 LOC).

### 0005 — clk: stop reclocking after consecutive failures

**Problem.** When the GPU enters an unrecoverable state (for example
after a Chrome WebGL workload triggers TRAP_CCACHE / PT_NOT_PRESENT),
`gt215_clk_pre()` repeatedly times out waiting for the FIFO to idle and
returns -EIO from `nvkm_pstate_prog()`. Userspace clients that poll
`/sys/kernel/debug/dri/0/pstate` (such as a load-based pstate daemon)
keep triggering `nvkm_pstate_calc()`, which schedules the work item
again and again. Each iteration emits a WARN_ON, hammers dead hardware,
and turns shutdown into a 3-minute hung-workqueue stall before a hard
reset.

**Fix.** Track consecutive `nvkm_pstate_prog()` failures. After three
consecutive failures (`NVKM_CLK_PROG_FAIL_LIMIT`), latch the subsystem
as wedged and make `nvkm_pstate_calc()` return -EIO without scheduling
further work. A successful prog resets the counter, so transient errors
do not latch.

**Reproducer.** Apple Mac mini Late 2009, Chrome with a heavy WebGL
workload (the original was a personal browsing session; the reproducer
is hard to construct deterministically). The pstate daemon was the
trigger; v0.2.0 of nouveau-pstate-daemon switches to event-driven
writes via swayidle and removes that trigger surface.

**ML status.** Submission deferred while the userland-side fix
(daemon v0.2.0) reduces the in-the-wild urgency. Patch 0006 reaches
the same wedge-state observability through `drm_dev_wedged_event` as
the Tier-2 action of its FIFO recovery path, so 0005 may end up
withdrawn in favour of 0006 alone.

**Files touched.**
`drivers/gpu/drm/nouveau/include/nvkm/subdev/clk.h` (+2),
`drivers/gpu/drm/nouveau/nvkm/subdev/clk/base.c` (+12).

### 0006 — fifo: add recovery path for Tesla cache_error/dma_pusher

**Problem.** On Tesla (nv50 / g8x / g9x including MCP77/MCP79),
`nv04_fifo_intr_cache_error` and `nv04_fifo_intr_dma_pusher` log the
fault, reset the HW registers, and return. The offending channel
keeps running with potentially corrupt state. There is no call to
`nvkm_chan_error`, no DRM wedge event, no counter, no tracepoint. The
only signal is `dmesg`. Fermi+ gets channel-kill and device-wedge
automatically through `nvkm_runl_rc`; Tesla was feature-frozen before
the DRM wedge uAPI existed.

Three concrete consequences:

1. Silent state corruption: the channel produces wrong pixels or
   compute output after the fault, with no notice to userspace.
2. Observability gap: no counters, no tracepoints, no wedge event,
   only dmesg.
3. Repeated-fault loop: if a channel faults persistently, the
   log-and-reset cycle repeats forever instead of killing the channel.

**Fix.** A two-tier recovery pipeline kept in a new helper file
`nvkm/engine/fifo/recover.c`. Existing intr handlers gain one extra
function call each.

*Tier 1 (per fault).* Look up the channel via `nvkm_chan_get_chid`,
call `nvkm_chan_error(chan, true)`, fire tracepoint
`nouveau:fifo_chan_killed`. Idempotent through the existing
`chan->errored` short-circuit, so repeated faults on the same channel
are no-ops; other channels are unaffected.

*Tier 2 (sliding window).* Per-`nvkm_fifo` ring buffer of fault
timestamps. When the window count reaches the threshold, schedule a
worker that calls
`drm_dev_wedged_event(drm, DRM_WEDGE_RECOVERY_REBIND, NULL)` and
fires tracepoint `nouveau:fifo_dev_wedged`. Worker context is needed
because `kobject_uevent_env` allocates `GFP_KERNEL` and may sleep,
which is illegal from the IRQ path. `atomic_xchg` makes the wedge
emit idempotent across concurrent faults; the flag clears implicitly
on driver rebind.

`DRM_WEDGE_RECOVERY_REBIND` is the right hint for this hardware:
`BUS_RESET` would tear the Mac mini PCI tree apart, and `NONE` would
not signal that userspace should act. `REBIND` tells session managers
to unbind+bind the driver and restart the compositor.

**Module parameters.** `nouveau.fifo_wedge_count` (uint, range 0..32,
default 10) sets the Tier-2 threshold; `0` disables Tier-2 entirely
while leaving Tier-1 channel-kill active. `nouveau.fifo_wedge_window_ms`
(uint, range 100..600000, default 60000) sets the window width.

**Validation.** Phases 1-5 of the test plan in
`docs/specs/2026-05-04-nv04-fifo-recovery-design.md` are done,
exercised through the `dev-fault-injector` debugfs writes (separate
branch, `[DO-NOT-MERGE]`). Phase 6 (real-world soak without manual
injection) is in progress on the reference host. The companion
[hibbes/nouveau-pstate-daemon](https://github.com/hibbes/nouveau-pstate-daemon)
v0.2.0 includes a udev subscriber for the resulting `WEDGED=rebind`
event and was end-to-end validated on 2026-05-05.

**ML status.** Local-only; submission with patches 4 and 5 in the v2
bundle, blocked on Phase 6 soak completion.

**Files touched.**
`drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c` (new, ~150 LOC),
`drivers/gpu/drm/nouveau/nvkm/engine/fifo/nv04.c` (+2 call sites),
`drivers/gpu/drm/nouveau/nvkm/engine/fifo/base.c` (+~10),
`drivers/gpu/drm/nouveau/nvkm/engine/fifo/priv.h` (+~3),
`drivers/gpu/drm/nouveau/nvkm/engine/fifo/Kbuild` (+1),
`drivers/gpu/drm/nouveau/include/nvkm/engine/fifo.h` (+~15),
`include/trace/events/nouveau.h` (+~30 for two `TRACE_EVENT`),
`drivers/gpu/drm/nouveau/nouveau_drm.c` (+~5 for module params).


### 0019 — EVO supervisor-handshake rescue and the Tesla channel-kill dead letter

Two independent fixes, each behind its own runtime module parameter.

**`chan_kill_event` (upstream candidate).**  `nouveau_channel_init()` subscribes to
the channel-killed event only for `FERMI_CHANNEL_GPFIFO` and newer.  On NV50/Tesla
the subscription therefore never happens, so when the FIFO kills a channel the
`ERRORED` event is delivered into an empty notifier list,
`nouveau_fence_context_kill()` never runs, and the killed channel's fences are never
signalled.  Anything waiting on them waits forever: the display commit tail
(`drm_atomic_helper_wait_for_fences`, uninterruptible and without timeout) and the
TTM delayed-delete workers hang in D state, which presents to the user as a frozen
desktop while the machine itself is still alive.  This is a dma-fence contract
violation, and the same delivery chain has been running on Fermi and newer for years.
The patch lowers the class gate to `NV50_CHANNEL_GPFIFO`.

A second, smaller fix in the same file moves `nvif_event_dtor(&chan->kill)` ahead of
the fence-context teardown in `nouveau_channel_del()`.  Previously a killed event
arriving during teardown could read a fence context that was already being freed.
That race exists identically on Fermi and newer; it simply was not reachable on Tesla
before the gate change.

**`sv_rescue` (local, diagnose-only for now).**  On this MCP79 the EVO supervisor
handshake occasionally stalls: a core UPDATE is accepted, `0x610030` carries a
supervisor request, but the corresponding interrupt never latches in `0x610024`, so
the supervisor worker never runs, the continue write never happens, and the channel
parks.  Only a re-POST clears it, which in practice means an S3 suspend/resume cycle.
The patch adds a staged notifier wait that can synthesise the missing interrupt
behind a four-way guard.  Instrumentation added in 0021 showed that the stall happens
*after* phase SV2, not at SV1 as first assumed, so the synthesis phase is still being
determined and the code ships in diagnose-only mode.

### 0020 — fifo: Tier-0 escalation ladder

The original 0006 killed a channel on its first `CACHE_ERROR`.  On this hardware the
PFIFO cache puller names the *resident* channel rather than the offending one, so an
unrelated process (in the observed cases the Wayland compositor) could be killed for
somebody else's fault.  0020 keeps upstream's behaviour for the first faults (skip the
method or drop the push segment, resume) and only escalates to the kill when the same
channel object collects `fifo_kill_count` faults inside `fifo_kill_window_ms`.
The per-channel streak is invalidated when the channel is torn down, so a recycled
channel object cannot inherit it.  The `CACHE_ERROR` log line was extended with the
puller state, the engine routing nibble, and the age of the last graphics trap, so the
next incident can settle whether the attribution is spurious.

### 0018 / 0021 — diagnostics

Neither patch changes behaviour.  0018 dumps the EVO push buffer around the frozen GET
pointer on any channel timeout; 0021 logs one compact line with the supervisor state
before and after every core update.  Together they produced the observation that a
healthy soft-DPMS wake performs no supervisor sequence at all, while the wedging wake
requests one and then stalls: the wedge needs both a supervisor-requesting commit and
a swallowed interrupt.

### 0022 — fifo: debug fault injector

Local debug patch, not for upstream.  It drives `nv04_fifo_recover()` directly through
two write-only module parameters, so the Tier-0 ladder, the Tier-1 kill and everything
downstream of it (the channel-killed event, fence signalling, userspace fallout) can be
exercised deterministically instead of waiting for a real `CACHE_ERROR` to occur.

### 0023 / 0024 — local counterparts of the submitted nv04-FIFO v3 series

These mirror patches 2/5 and 5/5 of the nv04-FIFO v3 series sent to the list on
2026-08-13, adapted to the stack running here.  0023 subscribes to the channel-kill
event only after the fence context exists; on this host that subscription is
additionally gated by the local `chan_kill_event` module parameter 0019 adds, which the
upstream version omits.  0024 moves the `chfault[].owner` cleanup in `nvkm_chan_del()`
to run only after `nvkm_chid_put()`: until the slot is cleared the dying channel is
still discoverable, so `nv04_fifo_recover()` could re-set `cf->owner` and a later
allocation on the same slab would inherit a stale owner.

## Building locally

The patches apply against an unmodified upstream nouveau source tree
(extracted from `linux-7.0.tar.xz` or any nearby Linus tag). The full
build flow on the reference Gentoo host:

```sh
WORK=$(mktemp -d)
tar -xf /var/cache/distfiles/linux-7.0.tar.xz \
    --strip-components=1 -C "$WORK" linux-7.0/drivers/gpu/drm/nouveau
for p in 000*.patch; do
    patch -d "$WORK" -p1 < "$p"
done
make -C /lib/modules/$(uname -r)/build \
    M="$WORK/drivers/gpu/drm/nouveau" modules -j$(nproc)
sudo install "$WORK/drivers/gpu/drm/nouveau/nouveau.ko" \
    /lib/modules/$(uname -r)/kernel/drivers/gpu/drm/nouveau/
sudo depmod $(uname -r)
```

## Local integration on the reference host

A `kernel-install` plugin at
`/etc/kernel/install.d/50-nouveau-patches.install` runs on every
`gentoo-kernel-bin` update before `dracut` builds the initramfs:

1. extracts the matching upstream nouveau source from
   `/var/cache/distfiles/linux-${MAJOR_MINOR}.tar.xz`
2. applies every `*.patch` from `/etc/kernel/nouveau-patches/`
   (skipping any that already merged upstream, with `--dry-run` check)
3. builds `nouveau.ko` and replaces the stock module (saving the
   original as `nouveau.ko.stock` for rollback)
4. runs `depmod` so the next boot picks up the patched module

The patches in this repo mirror the contents of
`/etc/kernel/nouveau-patches/`. Updating one updates the other; the
install hook is the source of truth for what the next-built kernel
will carry.

## Submission workflow

The canonical submission channel for nouveau patches is the mailing
list:

- list address: `nouveau@lists.freedesktop.org`
- archive: <https://lore.kernel.org/nouveau/>
- CC: `dri-devel@lists.freedesktop.org`

Patches are sent via `git send-email` from a `git format-patch` series.
This GitHub repository exists for archival reference and to make the
individual patch files easily citable (for example, when a maintainer
asks for the full patch file or an old version).

The patches are kept on a dedicated working branch in a separate local
clone of `torvalds/linux` (sparse-checked-out for `drivers/gpu/drm/nouveau`
only, to keep the working set manageable). The local branch is
`nouveau-nvac-fixes` (patches 0001 through 0006).

## Companion userland

A separate project tracks the userland half of the story:
[hibbes/nouveau-pstate-daemon](https://github.com/hibbes/nouveau-pstate-daemon).
That project is an event-driven swayidle bridge plus a small privileged
helper that toggles between the `0e` (active) and `03` (idle) pstates
on user-activity transitions. v0.2.0 (released 2026-05-05) dropped the
previous polling design, which was the dominant trigger for the
WARN-loop that motivates patch 0005, in favour of writing pstate only
on real activity events.

v0.2.0 also ships a udev subscriber for the `WEDGED=rebind` uevent
that patch 0006 emits as its Tier-2 action. The subscriber is
log-only: it appends to `/var/log/nouveau-pstate-wedge.log` and
writes a sticky snapshot at `/run/nouveau-pstate.wedged` for status
bars and session managers to consume. End-to-end validation on the
reference host on 2026-05-05 captured a real `WEDGED=rebind` uevent
on `/dev/dri/card0`.

## Soak methodology

Each patch is daily-driven on the reference machine for at least one
week before submission, and the cover-letter / soak-report includes:

- number of clean boots on the patched kernel
- number of regressions observed (zero is the bar)
- specific scenarios exercised (DPMS cycles, Wayland VT-switches,
  Chrome WebGL, suspend / resume cycles where applicable)

Submission is held until that bar is met. Patches 0001 - 0003 received
a 3-week soak across 17 boots before the soak report on 2026-04-26.

## Acknowledgements

Thanks to Ben Skeggs and the wider nouveau community for keeping the
NV50 era alive, to the DRM core authors for shipping
`drm_dev_wedged_event` as a generic mechanism, and to the Mesa /
graphics stack folks whose bug reports across the years map closely to
several of the issues this series fixes.

## License

Patches are submitted under standard Linux kernel licensing
(GPL-2.0-only). Each patch carries a `Signed-off-by:` line. See the
individual patch files for details.
