# forcedeth patches

Not nouveau, but the same machine and the same silicon family: forcedeth
drives the onboard NIC of the MCP79 chipset this repository targets.
Patches here are kept separate from the numbered nouveau series and are
not applied by `/etc/kernel/nouveau-patches` (the bashrc rebuild hook
only builds `drivers/gpu/drm/nouveau`).

| Patch | What |
|---|---|
| `0001-forcedeth-fix-off-by-one-when-saving-restoring-non-PCI-config-space.patch` | `<=` instead of `<` in the suspend/resume config-space loops, one element past `saved_config_space[]`. Found by UBSAN on 7.1.6 during a deep S3 cycle. |

## Before sending anything upstream

- **No `Fixes:` tag yet.** The loop is long-standing mainline code and this box
  has no kernel git history (gentoo-sources ships a tarball), so the introducing
  commit could not be determined locally. `checkpatch` asks for the tag because
  the message carries a `Call Trace:`. Determine it against a real kernel clone
  before posting, rather than guessing a hash.
- **checkpatch: 0 errors, 2 warnings, 2 checks.** The two CHECKs are
  "spaces preferred around that '/'" on the touched lines. That spacing is
  pre-existing style and matches the identical loop in `nv_get_regs()`
  (forcedeth.c:4588), so it was left alone to keep the fix minimal. Expect a
  reviewer to possibly ask for it anyway.

## Still open

`nv_tx_timeout()` (forcedeth.c:2743) dumps registers with
`for (i = 0; i <= np->register_size; i += 32)`, which starts its last row
at `0x600` and reads through `0x61c`, past the `0x604` window. That one is
not a plain `<=` to `<` fix (the final row overruns either way), it needs
`i + 32 <= np->register_size` or explicit handling of the partial row.
It sits behind the `debug_tx_timeout` module parameter, which is off by
default, and it touches MMIO rather than an array, so UBSAN does not flag
it. Separate patch when someone gets to it.
