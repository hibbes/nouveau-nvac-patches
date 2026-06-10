# v2 (upstream-bound resubmission)

Reworked forms of the two patches that are going back to the list as a
Cc:stable series, after the 2026-06-10 adversarial review. Rationale, tags
and verification: `../docs/specs/2026-06-10-v2-qa.md`.

- `0001-v2-...mcp79-msi-rearm.patch` -- narrowed from the shared g94 table to a
  dedicated mcp79 pci func (NVAC/0xac only).
- `0002-v2-...sor-null-guard.patch` -- NULL crtc guard via drm_WARN_ON_ONCE(),
  without the erroneous nvif_outp_release() from v1.

0003 (HPD retry) is intentionally NOT part of the v2 stable series.
Held until Fab Stz's Tested-by is confirmed before sending to the list.
