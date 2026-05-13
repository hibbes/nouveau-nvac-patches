# Resolution: vblank-timeout storm from drm_fb_helper at boot

**Created:** 2026-05-13
**Hardware:** Apple Macmini3,1 (Early 2009), GeForce 9400M (NVAC Tesla),
              PCI 10DE:0861, Subsys 106B:00AE
**Kernel:** 7.0.6-gentoo-dist with patch stack 0001-0006, 0009, 0099
**Supersedes:** `2026-05-11-vblank-fb_helper-storm.md` (primary
                hypothesis was wrong WARN source)

## Summary

The 2026-05-11 investigation identified a boot-time storm of `vblank wait
timed out on crtc 0` messages on NVAC. Hypothesis at the time was a
`WARN_ON_ONCE` at `drm_vblank.c:747` in the atomic timestamp helper,
arising from an uninitialised `vblank->hwmode` between `drm_vblank_init`
and the first atomic commit. A patch was prepared against
`nouveau_display.c` to seed `vblank->hwmode` with a placeholder mode
(patch 0007, archived).

After the 7.0.5 to 7.0.6 kernel bump the storm grew from ~4 lines per
boot to 44 - 55, which made it visible enough to investigate properly.
The original hypothesis turned out to be wrong on two counts:

1. The WARN that actually fires once per second comes from
   `drm_vblank.c:1320` (`drm_WARN(dev, ret == 0, ...)`), not from
   `:747`. `:1320` is a `drm_WARN` without `_ONCE`, so it fires per
   timeout. The `:747` `WARN_ON_ONCE` exists but only ever fires once
   per boot and is not the dominant noise source.
2. The caller is `drm_fb_helper_ioctl` on the `FBIO_WAITFORVSYNC`
   path, not `drm_fb_helper_fb_dirty`. fbcon and Plymouth issue this
   ioctl per cursor blink / console scroll, which is why dozens of
   calls accumulate during the early boot window.

## Corrected hypothesis

`nouveau_display_vblank_enable()` is unconditional:

```c
int nouveau_display_vblank_enable(struct drm_crtc *crtc)
{
    struct nouveau_crtc *nv_crtc;
    nv_crtc = nouveau_crtc(crtc);
    nvif_event_allow(&nv_crtc->vblank);
    return 0;
}
```

`nvif_event_allow()` arms the event mask, but the NV50/NVAC display
engine produces no vblank pulses while no pixel clock is running. The
pixel clock is only programmed by the first atomic commit. Until then,
every IOCTL that goes `drm_crtc_vblank_get` -> `drm_crtc_wait_one_vblank`
will time out at one second.

Other atomic drivers (amdgpu, i915) get away with the same pattern
because their hardware inherits a working mode from BIOS POST and the
display engine ticks vblanks from boot. NVAC needs an explicit modeset
first, and on the slow reference hardware that modeset arrives roughly
85 s after `drm_fb_helper` registers the framebuffer device.

Three layers contribute to the visible boot stall:

1. **nouveau** (immediate cause): `enable_vblank` returns 0 even though
   the hardware will not deliver IRQs.
2. **DRM core** (defensive but loud): waits 1 s for a vblank counter
   increment and emits `drm_WARN` with full backtrace on timeout, by
   design.
3. **NVAC + Plymouth timing**: opens an ~85 s window where this combo
   is observable. Faster GPUs and tighter Plymouth schedules close the
   window before the human eye notices.

## Fix shipped (patch 0009)

Refuse vblank-IRQ enable while the CRTC state is not committed-active.
`drm_crtc_vblank_get()` then returns non-zero and
`drm_client_modeset_wait_for_vblank()` skips the wait silently at
`drm_client_modeset.c:1329`.

```c
if (crtc->state && !crtc->state->active)
    return -EINVAL;
```

Result on the reference host, kernel 7.0.6-gentoo-dist, fresh boot
2026-05-13 18:39: zero `vblank wait timed out` messages, zero
`drm_vblank.c:1320` WARNings, Plymouth-to-greeter transition without
the ~40 s tucker phase. Storm count compared:

| Kernel | Patch stack | Storm count per boot |
|---|---|---|
| 7.0.5-gentoo-dist | 0001-0006 + 0099 | ~4 |
| 7.0.6-gentoo-dist | 0001-0006 + 0099 | 44 - 55 |
| 7.0.6-gentoo-dist | 0001-0006 + 0009 + 0099 | 0 |

## Earlier dead-end: drm-core patch 0008

Before 0009 a drm-core patch was prepared in
`drivers/gpu/drm/drm_client_modeset.c` adding the same
`crtc->state->active` skip to `drm_client_modeset_wait_for_vblank()`
itself. The patch is upstream-tauglich, applies cleanly, and would
benefit every atomic-modeset driver with similar boot timing, not just
nouveau.

Deployment failed runtime verification because the local rebuild path
on the reference host only rebuilds modules:

- `/etc/portage/bashrc` hook on `gentoo-kernel-bin` postinst runs
  `make M=drivers/gpu/drm/nouveau modules`.
- `gentoo-kernel-bin` itself ships a pre-built `vmlinuz` from the
  Gentoo build server.
- `CONFIG_DRM_CLIENT=y` in that build, so
  `drm_client_modeset_wait_for_vblank` is linked into the kernel image
  proper. `nm` on every `.ko` under `/lib/modules/.../drivers/gpu/drm/`
  shows the symbol only as `U` (undefined extern); `/proc/kallsyms`
  shows it at `T` in the running kernel's text segment.
- 0008 was patched into the source tree but the hook never rebuilt
  the binary that contains it. The deployed kernel kept the unpatched
  function from the Gentoo build.

Patch 0008 lives under
`/etc/kernel/nouveau-patches/.attic/0008-...patch.disabled-2026-05-13-wrong-location-vmlinuz-only`
as a record of the path. Reactivating it would require building
`gentoo-kernel` (source ebuild) instead of `gentoo-kernel-bin`, which
takes 2 - 3 hours on Core 2 Duo and is not justified for the local
fix.

## Patch 0007 status

`0007-drm-nouveau-display-seed-vblank-hwmode-placeholder-at-init.patch`
was the original 11.05. attempt: seed `vblank->hwmode` from
`drm_calc_timestamping_constants()` to defeat the `:747`
`WARN_ON_ONCE`. The patch is technically correct for that WARN but
addresses a once-per-boot cosmetic, not the per-second storm. Moved to
`/etc/kernel/nouveau-patches/.attic/0007-...patch.disabled-2026-05-12`
on 2026-05-12 when the actual storm source was identified.

## Upstream submission shape

Two viable upstream patches map onto this work:

1. **nouveau-only (= 0009 as deployed).** Narrow, conservative, helps
   only NVAC and any other Tesla hardware that takes a similarly long
   time to reach the first atomic commit. Easy to argue for, no
   shared-path concerns.
2. **drm-core (= 0008 as parked).** Symmetric fix in
   `drm_client_modeset_wait_for_vblank()`. Touches a shared path,
   needs ack from drm-misc maintainers (Maxime Ripard, Thomas
   Zimmermann), but benefits every atomic-modeset driver that ever
   suffered this on slow hardware.

Best path is probably to send both as a 2-patch series: drm-core
gating as a defensive improvement, plus the nouveau-side refuse as a
driver-shape fix. Pre-flight to dri-devel before sending.

## References

- `drivers/gpu/drm/drm_vblank.c:1320` (actual WARN source,
  `drm_crtc_wait_one_vblank()` timeout)
- `drivers/gpu/drm/drm_vblank.c:747` (red herring, `WARN_ON_ONCE` in
  atomic timestamp helper)
- `drivers/gpu/drm/drm_fb_helper.c:934` (caller,
  `FBIO_WAITFORVSYNC` ioctl)
- `drivers/gpu/drm/drm_client_modeset.c:1329` (silent-skip path used
  by patch 0009 via `drm_crtc_vblank_get()` returning non-zero)
- `drivers/gpu/drm/nouveau/nouveau_display.c` (patched by 0009)
- `2026-05-11-vblank-fb_helper-storm.md` (superseded investigation)
