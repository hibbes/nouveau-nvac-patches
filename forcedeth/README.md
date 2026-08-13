# forcedeth patches

Not nouveau, but the same machine and the same silicon family: forcedeth
drives the onboard NIC of the MCP79 chipset this repository targets.
Patches here are kept separate from the numbered nouveau series and are
not applied by `/etc/kernel/nouveau-patches` (the bashrc rebuild hook
only builds `drivers/gpu/drm/nouveau`, so a patch dropped in there would
be applied to the source tree but never compiled or installed).

Both patches are generated against 7.1.6, apply cleanly on their own and
cumulatively (`patch --dry-run`, 0 rejects), and are independent of each
other: they touch different functions and neither changes the line count.

| Patch | What | checkpatch |
|---|---|---|
| `0001-forcedeth-fix-off-by-one-when-saving-restoring-non-PCI-config-space.patch` | `<=` instead of `<` in the `nv_suspend()` / `nv_resume()` config-space loops. Indexes one element past `saved_config_space[]`, and on resume `writel()`s that value one dword past the window. Found by UBSAN on 7.1.6 during a deep S3 cycle. | 0 errors, 2 warnings, 2 checks |
| `0002-forcedeth-stop-the-tx_timeout-register-dump-past-the-ioremap-window.patch` | `nv_tx_timeout()` dumps eight-dword rows but only bounds the row's *start*, so the final row reads 12 to 28 bytes past the window on every supported variant. | clean |

## Why both matter more than "reads a bit too far"

`np->base = ioremap(addr, np->register_size)` maps **exactly**
`register_size` bytes. Every overrun described above therefore leaves the
mapping, it is not merely past a notional register range. On x86 the
ioremap gets rounded up to page granularity so nothing faults in
practice, which is presumably why this survived so long.

## Hardware test, 2026-08-04

Patch 0001 is no longer reasoning-only. The patched module was stripped,
installed, reloaded (md5 of the active module checked against the installed
one) and put through a real `rtcwake -m mem -s 30` deep S3 on the reference
machine:

    stock module,   first S3 of the boot (17:49):  2 UBSAN splats
    patched module, second S3 (21:19:56 - 21:20:01): 0 UBSAN splats

The network came back cleanly (`link up`, DHCP lease restored, ping 0% loss)
and there were no `tx_timeout` events. The stock module was restored
afterwards, so the fix is **not** installed permanently: the bashrc rebuild
hook only builds `drivers/gpu/drm/nouveau` and would silently overwrite a
patched forcedeth on the next kernel merge.

Patch 0002 is still compile-and-reasoning only. Its code path sits behind the
`debug_tx_timeout` module parameter and needs a genuine TX timeout to run,
which cannot be forced safely.

## Before sending anything upstream

- ~~**Neither patch carries a `Fixes:` tag.**~~ **RESOLVED 2026-08-13.** The
  claim that this box has no kernel git history is out of date: since the
  nouveau submission work there is a full clone at `~/linux-nouveau-patches`
  with 1.46M commits reaching back to `1da177e4c3f4` (2.6.12-rc2, 2005). Both
  introducing commits were found there and **verified by reading the diffs**,
  not guessed from a pickaxe hit alone:

  | Patch | Tag to add |
  |---|---|
  | 0001 config space | `Fixes: 1a1ca86158ee ("[netdrvr] forcedeth: save/restore device configuration space")` |
  | 0002 tx_timeout dump | `Fixes: 86a0f04387bf ("[PATCH] forcedeth: fix initialization")` |

  Method, for repeatability: `git blame` is useless here because the clone
  carries one shallow boundary (`.git/shallow` holds a 2026 merge), so blame
  reports `^a55f7f5f29b3` for everything. Bracketing across release tags works
  instead: the pattern is absent in v2.6.16, present once in v2.6.20, and
  three times by v2.6.30. `git log -S 'i <= np->register_size' v2.6.16..v2.6.20`
  and `git log -S 'saved_config_space' v2.6.25..v2.6.30` on the old path
  `drivers/net/forcedeth.c` then name the two commits.

  Worth knowing: `86a0f04387bf` introduced the `<=` at **two** sites. The one
  in `nv_get_regs()` (today line 4588) was corrected at some point, the one in
  the tx_timeout dump was not. That is why the file carries both spellings
  today.

- **`Cc: stable`, corrected understanding.** An earlier note assumed netdev
  refuses `Cc: stable`. `Documentation/process/maintainer-netdev.rst` says the
  opposite in its "Stable tree" section: "While it used to be the case that
  netdev submissions were not supposed to carry explicit CC:
  stable@vger.kernel.org tags that is no longer the case today." Follow the
  normal stable rules. For 0001 that is justified (real bug, reproduced on
  hardware); for 0002 probably not, since it sits behind a debug module
  parameter.

- **Subject prefix must be `[PATCH net]`**, not `[PATCH]`. Fixes go to the
  `net` tree, and `maintainer-netdev.rst` lists tree designation and the
  `Fixes:` tag as the first two requirements.

- **Check "reverse xmas tree"** before posting. Both patches only change loop
  conditions, so it most likely does not apply, but netdev enforces it.
- **0001 has two checkpatch CHECKs**, "spaces preferred around that '/'"
  on the touched lines. That spacing is pre-existing and matches the
  identical loop in `nv_get_regs()` (forcedeth.c:4588), so it was left
  alone to keep the fix minimal. A reviewer may still ask for it.
- **0002 drops a partial trailing row** from the debug dump: 16 bytes for
  VER1, 20 for VER2, 4 for VER3. That is a deliberate trade against
  open-coding a second narrower dump in a debug-only path, and the commit
  message says so. If a reviewer wants those registers back, the
  follow-up is a short remainder loop after the main one.
- Nothing has been sent anywhere. Marek approves recipients and full text
  first, as with the nouveau series.

## Verified state after both patches

    2743:  for (i = 0; i + 32 <= np->register_size; i += 32) {
    4588:  for (i = 0; i < np->register_size/sizeof(u32); i++)     (was already correct)
    6224:  for (i = 0; i < np->register_size/sizeof(u32); i++)
    6239:  for (i = 0; i < np->register_size/sizeof(u32); i++)

No `i <= np->register_size` bounds left in the file.
