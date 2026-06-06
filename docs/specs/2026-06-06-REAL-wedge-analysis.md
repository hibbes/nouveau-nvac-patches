# REAL EVO DPMS-wake wedge — captured live & analysed (2026-06-06)

First-ever pristine capture of the *real* wedge (passive watcher, stock nouveau,
no recovery). Box stayed live-wedged ~8 min, so a full live register dump was
taken too. Raw data: `2026-06-05-REAL-wedge-bar0.txt` (watcher snapshot @14:27:58)
and `2026-06-06-REAL-wedge-LIVE-fulldump.txt` (full dump @14:35:20).

## Trigger (confirmed 1:1)
swayidle blank `wlopm --off` **14:21:13** → off **6m36s** → wake `wlopm --on`
**14:27:49** → wedge **14:27:58** = **~9 s after the wake**. The DPMS-on re-enable
commit wedges it. Only 6.5 min off was needed (not the 9 h of the 06-03 incident):
the wedge is **intermittent/probabilistic**, not bound to a long off. Short active
repro is now feasible.

## What was open
labwc + waybar/conky/mako/wleyes + 3 foot terminals; java (51 % CPU) + a C++
compile (cc1plus). **No browser.** So only widget-level base-channel commit load,
not a browser — the wedge does not need heavy load.

## The mechanism — it is the CORE channel, not the base
- **ctrl0 (CORE) = 0x8f0e001b: busy=1 (0x80000000 latched), state[23:16]=0x0e**,
  PUT=0x09e8 > offset4=0x0988 (~96 dw pending). These values are **frozen** over
  7.5 min (snapshot == live dump) → a **permanent, silent stall**.
- ctrl2 = 0x8e07001b also busy=1. ctrl1/3/4 (base/window) busy=0, ch1 idle.
- Kernel log: **1× "core notifier timeout"** then **77× "base-1: timeout"**. The
  core-notifier timeout is primary; the base timeouts are downstream (base is
  interlocked with the core, so a stuck core hangs the base commits the compositor
  keeps retrying every ~2.5 s).
- **intr_status=0, intr_pending=0** → no disp exception/fault is raised. This is a
  **silent EVO state-machine stall**, not a hard fault: the core started the DPMS-on
  head re-program (the 96 dw set.mask) and hung mid-update.

This refines the root cause: the "base-1 timeout" we chased is a *symptom*; the
*root* is the **core channel stalling busy during the DPMS-on re-program**.

## Decisive question: irreversible vs healable
Leans **hard to recover at runtime**:
- Core is **busy-latched (0x80000000)** in **state 0x0e**.
- The only existing unstick (nv50_disp_core_init, nv50.c:969-972) matches states
  0x02/0x03 → does **not** cover 0x0e. So the existing heuristic would not clear it.
- The busy bit is exactly what a fini/init re-arm waits to clear; a busy-stuck core
  likely won't clear it (matches the 0010 recovery failures + the injector's
  0x80000000-stuck init timeout). Runtime full re-init also fails (devinit -22).

→ **Recovery (heal the already-wedged core) is probably a dead end.** The realistic
driver direction is **prevention**: re-arm the core channel (fini/init) at the
DPMS-on transition, while it is still healthy, so the re-program runs on a fresh
channel instead of stalling the live one. Needs testing on the test boot, now
feasible thanks to the short repro.

## Next steps
1. Reboot to the patch0010 TEST boot.
2. Reproduce via short DPMS-off (~7-10 min) + wake, a few tries (intermittent).
3. With `disp_recover=1`, test whether recovery heals a *real* (not injector) wedge
   — the test we never got to do. Capture the core register before/after.
4. If recovery can't clear the busy-latched core (expected), build & test the
   **prevention** patch (fini/init at DPMS-on re-enable). Fall back to no-blank if
   even prevention can't keep the live core from stalling.
