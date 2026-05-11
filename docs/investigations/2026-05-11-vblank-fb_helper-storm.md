# Investigation: vblank wait timeout + boot-time FIFO wedge storm

**Created:** 2026-05-11 ~05:45
**Trigger:** Live-Debug-Session 10./11. Mai. swaybg-Buffer war im oberen
Bildschirmbereich nach 24 h gefroren; nach swaybg-Restart sauber. User
wollte Ursache fixen statt symptomatisch zu restarten.

**Kernel:** 7.0.5-gentoo-dist (Boot 11.05. 05:41)  -  vorher 7.0.4-p1
**Hardware:** Apple Mac mini 3,1 (Early 2009), PCI 10DE:0861 = GeForce 9400M
              (NVAC, Tesla), Subsys 106B:00AE = Apple-OEM
**Userspace:** labwc (wlroots) + swaybg + waybar + 2× conky + wleyes

## Beobachtete Symptome

### A. vblank-Timeout-Storm beim Boot
```
[4.158] [drm] Initialized nouveau 1.4.2
[4.230] fbcon: nouveaudrmfb (fb0) is primary device
[4.251] drm_WARN_ON_ONCE(drm_drv_uses_atomic_modeset(dev))
        in drm_crtc_vblank_helper_get_vblank_timestamp_internal+0x154/0x3d0
        Workqueue: events drm_fb_helper_ioctl
        Stack: drm_crtc_get_last_vbltimestamp
             -> drm_update_vblank_count
             -> drm_vblank_enable
             -> drm_vblank_get
             -> drm_client_modeset_wait_for_vblank
             -> drm_fb_helper_ioctl
[5.278] vblank wait timed out on crtc 0
[6.428] vblank wait timed out on crtc 0   (+1.15 s)
[7.438] vblank wait timed out on crtc 0   (+1.01 s)
[8.451] vblank wait timed out on crtc 0   (+1.01 s)
... ca. 10 wiederholungen
```

### B. fifo_wedge_count = 10 nach 3 Min Uptime
- Patch 0006 silent-recoveries (CACHE_ERROR / DMA_PUSHER)
- Keine dmesg-lines durch Patch 0004 + 0006 silencing
- 10 Wedges = Threshold-Marke fuer Tier-2 device-wedge erreicht

### C. Periodischer FIFO-firmware-reload bei voller Live-Last
- z.B. zwischen Uptime 35.0 h und 35.4 h: 15× `Loading firmware: nouveau/nvac_fuc084`
- Burst-Charakter: vermutlich Feedback-Loop, nicht zeitlich verteilt

### D. Live-Symptom: gefrorener swaybg-Buffer im oberen Bereich nach ~24 h Uptime
- Wallpaper-Lueke oben (Y=30-80px) zeigt solid schwarz statt Rainnight-Skyline
- Swaybg-PID lief, hatte aber stale Buffer
- Sauber nach `kill $swaybg && swaybg ... &`

## Bug-Hypothese (hohe Konfidenz)

**Haupt-Ursache: API-Mismatch in drm_fb_helper.**

`drm_crtc_vblank_helper_get_vblank_timestamp_internal` ist fuer
LEGACY-Treiber gebaut. Der `WARN_ON_ONCE` feuert bei atomic-modeset-Treibern.
nouveau IST atomic. Ergo: Helper liefert keinen brauchbaren Timestamp,
`drm_crtc_wait_one_vblank` haengt im 1-s-Timeout, gibt auf, retried, fault-Schleife.

**Folge-Wirkung 1:** Jeder failing fb_helper-IOCTL submittet einen FIFO-Push
fuer den implied mode-set. Push haengt, FIFO erkennt das als
CACHE_ERROR/DMA_PUSHER, Patch 0006 recover()'t silent. Loop produziert
~10 Wedges in den ersten 38 s.

**Folge-Wirkung 2 (Live-Symptom Wallpaper):** Pending pageflip auf einem
CRTC wartet auf den verworfenen FIFO-Push. Vblank-Event kommt nie. Compositor
sieht keine "frame finished"-Notification, geht in Stall-State; das letzte
gerenderte Buffer-Region bleibt stehen.

## Affected Components

| File | Worum es geht |
|---|---|
| `drivers/gpu/drm/drm_vblank.c:747` | `drm_crtc_vblank_helper_get_vblank_timestamp_internal`, der `WARN_ON_ONCE` |
| `drivers/gpu/drm/drm_fb_helper.c` | `drm_fb_helper_ioctl` calls `drm_client_modeset_wait_for_vblank` |
| `drivers/gpu/drm/nouveau/nouveau_display.c` | nouveau atomic-modeset registration |
| `drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c` | Patch 0006  -  Reaktion, nicht Ursache |

## Fix-Pfade (Trade-offs)

### Pfad 1: nouveau implementiert `get_vblank_timestamp` atomic-tauglich (richtig)
- Implementiere `dev->driver->get_vblank_timestamp` mit korrekter atomic-API
- ODER: drop drm_crtc_vblank_helper_get_vblank_timestamp_internal-Aufruf zugunsten der atomic-Variante
- Upstream-tauglich (kein DO-NOT-MERGE), echte Loesung
- Mehr Aufwand, eventueller Bug-Report bei nouveau-ml ratsam

### Pfad 2: fb_helper-Aufruf entfernen (lokaler Workaround)
- Patch `drm_fb_helper_ioctl` so dass `drm_client_modeset_wait_for_vblank()`
  bei atomic-Treibern uebersprungen wird
- Cleaner Workaround, aber faellt unter "fixing wrong place"
- Tritt bei jedem atomic-Treiber auf, nicht nur nouveau

### Pfad 3: nouveau-fb_helper-Pfad deaktivieren via Kernel-cmdline
- `nofbdev` oder `video=...` Magic
- Schnell testbar  -  wenn Storm verschwindet, Hypothese bestaetigt
- Boot-Console verloren, Plymouth ggf. broken; nur Test-Werkzeug

### Pfad 4 (Diagnose-Werkzeug): trace_nouveau_fifo_chan_killed enable
- `echo 1 > /sys/kernel/debug/tracing/events/nouveau_fifo/chan_killed/enable`
- Zeigt JEDEN recover()-call (was Patch 0004/0006 silencen)
- Faults korrelieren mit fb_helper-IOCTL-Aufrufen → confirmt Feedback-Loop

## Reproduzieren

**Wichtig  -  KEIN Patch 0099 mit aktiven chids:** chid>=1 = system hard-freeze
auf laufender Wayland-Session (Live-Test 2026-05-11 hat genau das passiert).
Siehe `feedback_nouveau_fault_injector_dangerous.md` im memory.

**Stattdessen: passiv Boot-Pattern beobachten.** Jeder Boot triggert ~10
wedges in den ersten 60 s. Reicht fuer Diagnose ohne aktiver Inject.

**Wenn Fault-Injektion noetig:**
- Stoppe Wayland-Session vorher: `chvt 2 && pkill labwc` von tty
- Inject nur in dedizierten ttyN, dann zurueck zu labwc

## Naechste konkrete Schritte (priorisiert)

1. **trace-event aktivieren** und nochmal booten, dmesg+trace korrelieren
2. **fb_helper-Trace** ueber `ftrace function-graph` filtered auf
   `drm_fb_helper_*` und `drm_*vblank*` waehrend Boot  -  exakte Call-Sequenz
3. **Pfad 1 oder 2 als Patch** entwickeln (Pfad 1 ist sauberer)
4. **Patch lokal bauen**, mit Boot-Pattern verifizieren (Wedge-Count muss
   nach 60 s ≪ 10 sein)
5. **Bug-Report upstream**: `nouveau@lists.freedesktop.org` + dri-devel-ML,
   plus eventuell `drm@lists.freedesktop.org` wegen helper-API

## References

- `drivers/gpu/drm/drm_vblank.c:747` (WARN_ON_ONCE-Quelle)
- `drivers/gpu/drm/drm_vblank.c:1320` (vblank-wait timeout)
- `drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c` (Patch 0006)
- Memory `project_gentoo_nouveau_hook.md`  -  Patch-Stack-Uebersicht
- Memory `feedback_nouveau_fault_injector_dangerous.md`  -  chid>=1 = Freeze
- dmesg-Schnipsel: `/var/log/dmesg` (Boot 11.05. 05:41 UTC+2)
