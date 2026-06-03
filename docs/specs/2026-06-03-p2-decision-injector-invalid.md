# Patch 0010 P2 root-cause: the debugfs injector is an invalid test

Date: 2026-06-03. Backed by multi-agent research (raw: `2026-06-03-p2-rootcause-research-raw.json`)
and the v2 failure evidence (commit 899384e: dmesg + BAR0 snapshot).

## The reframing

The v2 injector test (core re-arms, windows stay `put=0` -> `base-1 timeout` -> 32x loop) is
**not evidence that v2 fails on a real wedge**. The debugfs injector fires
`nv50_disp_recover_schedule()` on a **healthy, running** display; the worker then re-arms
**all** channels, including the **actively scanning** window/base channels.

BAR0 proof (wedged-state snapshot, commit 899384e): window control regs
`0x610200+ctrl*0x10 = 0x4003001b`. Low byte `0x1b = 0x13 | 0x08` -> the arm bits **plus** the
mid-fetch/active bit. `nv50_dmac_recover()` (recover.c:39-43) resets a **live, scanning** window
channel to `PUT=0` / empty ring **while the HW is still fetching** -> GET freezes at 0 ->
`base-1 timeout`. **The injector creates the very wedge it then fails to recover.** It teaches
us nothing about real-wedge recovery.

Note: v2's replay **does** emit the window image push (forced `mode_changed=true` ->
`nv50_wndw_atomic_check` modeset=true -> wndw.c:288 `|| modeset` -> `set.image=true`, wndw.c:327).
So the "missing push / SW-state discrepancy" theory is **not** the cause here; the push is
emitted and hangs because the channel was reset mid-fetch.

## Decisions

- **Engine-level re-init (the chosen option C): NOT pursued.** Even the agent that designed it
  concluded it does not solve the fetch problem (finding 3d). `nvkm_disp_fini/init` does not reach
  the channel objects (base.c walks the subdev list, not channel objects); the per-channel re-arm
  is already done via `nvkm_disp_chan_recover`; the only substance it would add (SW PUT mirroring)
  is already in `recover.c:39-43`. It adds risk without a new mechanism. (It IS runtime-safe /
  POST-free, that part checked out, just not useful here.)

- **Fix candidate A (drm_mode_config_reset): deferred.** A only helps if the defect were a missing
  push; here the push is already emitted. Revisit only if a real-wedge test shows a missing-push
  symptom.

## Revised plan (test methodology first, science before fixes)

0. **Param writable:** `module_param_named(disp_recover, ..., uint, 0644)` (was 0400) so it can be
   toggled at runtime (stop a loop / arm a test without reboot).
1. **Loop guard:** a `RECOVER_ACTIVE` flag in `nv50_disp` that suppresses re-scheduling while the
   worker runs (the replay's own `nv50_dmac_wait` timeout must not re-trigger). One replay attempt
   per wedge event; on failure log + give up (screen stays black but kernel stays stable, no storm).
2. **Replace the injector with a REAL wedge trigger** (debugfs, DEBUG_FS only): poke an unmapped
   push address into a **window** channel and kick PUT so the HW takes a genuine FIFO error and the
   channel wedges **by itself**, then let the normal `nv50_dmac_wait` timeout -> recover path fire.
   Do NOT pre-reset the channel. Alt: blank/unblank stress (wlopm off 30s / on, loop) closer to the
   real 2026-06-02 wedge but non-deterministic.
3. **Test the CURRENT v2 against a real wedge.** It is entirely possible v2 already recovers a real
   wedge and the whole negative result was an injector artifact.
4. **Only if real-wedge recovery fails AND the window `0x610200` shows the stuck pattern**
   `(v & 0x003f0000) == 0x00030000`: mirror the core unstick (nv50.c:968-972) into
   `nv50_disp_dmac_init` (nv50.c:654). This is the one documented core/window asymmetry: the core
   init has the unstick, the dmac (window/base) init does not.

## Open risk

Not proven that current v2 recovers a real wedge; not proven that it does not. Proven only that the
existing negative result is a test artifact. The unstick-on-window mask (0x00600000/0x00800000) is
documented for the core channel; its semantics on a window/base ctrl offset must be cross-checked
against envytools/nvkm headers before upstreaming.
