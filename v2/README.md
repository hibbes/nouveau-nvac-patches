# v2 (upstream-bound resubmission)

Reworked forms of the two patches that are going back to the list as a
Cc:stable series, after the 2026-06-10 adversarial review. Rationale, tags
and verification: `../docs/specs/2026-06-10-v2-qa.md`.

- `0001-v2-...mcp79-msi-rearm.patch` -- narrowed from the shared g94 table to a
  dedicated mcp79 pci func (NVAC/0xac only).
- `0002-v2-...sor-null-guard.patch` -- NULL crtc guard via drm_WARN_ON_ONCE(),
  without the erroneous nvif_outp_release() from v1.

0003 (HPD retry) is intentionally NOT part of the v2 stable series.
Fab Stz confirmed his Tested-by on 2026-06-11; the series was sent to the
list the same day (To: Lyude Paul, Danilo Krummrich; Cc: dri-devel, nouveau,
linux-kernel, Fab Stz). `send/` holds the exact files as sent
(git format-patch output, cover Message-ID cover.1781162589).

## v3 (sent 2026-06-11, the live series)

The v2 posting from the morning of 2026-06-11 went out with a mangled mail
form (duplicated in-body From, broken threading) and drew a valid finding
from the Sashiko AI review bot: the new guard in 2/2 sat below an
unconditional nv_connector dereference that can be NULL in the very state
the guard addresses. v3 hoists the guard above the backlight block, makes
the old-connector lookup NULL-safe, annotates the stable tag on 1/2 with
v6.16+ (the new file needs the .cfg member introduced there) and fixes the
review nits. `send3/` holds the exact files as sent (cover Message-ID
20260611124535.527275-1, properly threaded, single in-body From).
Verification: checkpatch 0 errors, git am clean against pristine 7.0.12,
W=1 warning-free, full module build rc=0/0 warnings, self-test mail loop
before the real send.
