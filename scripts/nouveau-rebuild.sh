#!/usr/bin/env bash
set -euo pipefail
KVER=7.0.11-gentoo-dist
SRC=/usr/src/linux-7.0.11-gentoo
BIN=/usr/src/linux-7.0.11-gentoo-dist
MOD="$SRC/drivers/gpu/drm/nouveau/nouveau.ko"
DST="/lib/modules/$KVER/kernel/drivers/gpu/drm/nouveau/nouveau.ko"
cd "$SRC"
cp "$BIN/.config" .config
make ARCH=x86 EXTRAVERSION='' olddefconfig
make ARCH=x86 EXTRAVERSION='' modules_prepare
cp "$BIN/Module.symvers" Module.symvers
make ARCH=x86 EXTRAVERSION='' -j"$(nproc)" M=drivers/gpu/drm/nouveau modules
vm=$(modinfo -F vermagic "$MOD" | head -1)
case "$vm" in 7.0.11-gentoo-dist*) echo "vermagic OK: $vm";;
  *) echo "VERMAGIC MISMATCH: $vm (check EXTRAVERSION='')"; exit 1;; esac
strip --strip-debug "$MOD"
sudo install -m0644 "$MOD" "$DST"
sudo depmod -a "$KVER"
echo "installed $DST (effective after reboot)"
