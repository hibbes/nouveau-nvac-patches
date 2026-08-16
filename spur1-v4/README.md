# Spur 1, v4: rebased am 16.08.2026

Basis: `c21bb4193868`. Zweig `spur1-v4` in `~/linux-nouveau-patches`.

Die v3 liegt seit dem 11.06.2026 unbeantwortet auf der Liste. Ein blosser
Ping waere wertlos gewesen, weil `0002` nicht mehr anwendet.

## Was der Rebase betraf

| Patch | vorher | jetzt |
|---|---|---|
| `0001` mcp79-msi-rearm | passte unveraendert | unveraendert uebernommen |
| `0002` kms-sor-null-guard | wandte nicht mehr an | **von Hand rebased** |

**Der Grund war fremde Kontextdrift, kein inhaltliches Problem.** Der Fehler
steht unveraendert in Mainline: `dispnv50/disp.c` macht weiterhin
`nv50_head(nv_encoder->crtc)` ohne NULL-Pruefung, und in der ganzen Funktion
gibt es keinen Guard. Verschoben hat sich nur die Signatur, durch
`5164f7e7ff8e ("drm: Rename struct drm_atomic_state to drm_atomic_commit")`.
Der Parameter heisst jetzt `struct drm_atomic_commit *state`.

## Pruefungen

- Beide Konfigurationen uebersetzt: `CONFIG_DRM_NOUVEAU_BACKLIGHT=y` **und**
  `=n`. Der Patch baut die `#ifdef`-Struktur um (zwei Bloecke statt einem),
  und genau dort bricht so etwas typischerweise. `drm` wird nur innerhalb der
  Bloecke benutzt, `drm_WARN_ON_ONCE()` nimmt `encoder->dev`.
- checkpatch: `0002` ist 0/0/0. `0001` hat drei Warnungen, alle unkritisch:
  zwei betreffen Prototypen ohne Parameternamen, was exakt dem Stil der
  Nachbarzeilen 50 bis 54 derselben Datei entspricht, und die dritte fragt
  nach MAINTAINERS, was `F: drivers/gpu/drm/nouveau/` bereits abdeckt.
- `Tested-by: Fab Stz <fabstz-it@yahoo.fr>` aus der v1-Runde ist in beiden
  Patches erhalten.

## Vor dem Versand offen

Der Cover-Letter fuer v4 fehlt noch. Er sollte die zwei Monate Stille
benennen und sagen, dass sich inhaltlich nichts geaendert hat ausser dem
Rebase, damit niemand die Serie neu durchlesen muss.
