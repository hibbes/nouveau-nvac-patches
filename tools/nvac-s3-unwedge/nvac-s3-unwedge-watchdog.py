#!/usr/bin/env python3
# nvac-s3-unwedge-watchdog (2026-06-29): auto-recover the nv50/MCP79 EVO
# base-channel fetch-park (the "nouveau ...: drm: base-1: timeout" wedge) via a
# deep-S3 suspend/resume cycle instead of a cold reboot. The S3 resume re-POSTs
# the GPU (devinit), which is the ONLY thing that clears the bit31-latched park
# (proven live 2026-06-29: `rtcwake -m mem` resumes clean AND unwedges, registers
# core/base1 bit31 -> clear). Detection is a read-only BAR0 mmap; recovery stops
# nv-watchdog (disarm the TCO so it can't fire mid-suspend), runs rtcwake -m mem,
# then restarts nv-watchdog. Storm guard: too many recoveries in a window kills
# the idle-blank swayidle (back to no-blank) + Telegram-alert, watchdog stays up.
#
# 2026-06-30: capture the EVO register set + dmesg to an event file BEFORE the S3.
# The read-only observatory sampler raced the fast S3 (its capture_event was
# mid-burst when the suspend hit on 2026-06-30 07:42, so no event file). The
# watchdog OWNS the timing, so its pre-S3 snapshot is guaranteed.
import mmap, struct, os, time, subprocess, signal

os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/sbin:/usr/bin:/bin:" + os.environ.get("PATH", "")

PCI                   = "/sys/bus/pci/devices/0000:02:00.0/resource0"
CORE_CTRL,  CORE_GET  = 0x610200, 0x640004
BASE1_CTRL, BASE1_GET = 0x610220, 0x642004
INTERVAL     = 3.0      # poll period (s)
CONFIRM      = 3        # consecutive (bit31 set AND get frozen) samples => wedge (~9s)
RTCWAKE_S    = 40       # deep-S3 wake timer; must exceed the ~25s wedged suspend-entry
COOLDOWN     = 30.0     # settle time after a recovery (s), watchdog blind during it
STORM_N      = 3        # this many recoveries...
STORM_WINDOW = 1800.0   # ...within 30 min => storm: kill idle-blank + alert
# 2026-09-13: post-S3 hardening. The watchdog is the ONLY net once nvac-boot-s3 is off,
# so every heal now checks the NIC (deep-S3 can wedge the forcedeth TX path, 2026-07-12,
# curable only by an admin down/up) and reports its OUTCOME via Telegram. Before this,
# alert() was reachable from the storm branch only: an unattended wedge + heal + dead NIC
# produced exactly zero notification. base-wedge-capture.sh does ping on a wedge, but it
# only matches "base-N: timeout" and stays silent on a pure core park (seen 2026-09-08).
IFACE          = "enp0s10"   # onboard forcedeth
GW             = "192.168.1.1"
POST_S3_SETTLE = 8.0         # s of quiet after the resume before probing the NIC
NIC_GRACE      = 5.0         # s second chance before touching the link
KERNEL         = os.uname().release
LOG          = "/var/log/nvac-s3-unwedge.log"
EVENTDIR     = "/home/neo/nvac-evo-observatory/events"   # snapshots go into the public repo
# diagnostic register set captured pre-S3 (the meaningful EVO + error-latch regs)
DIAG_REGS = [
    (0x000200, "pmc"),
    (0x610200, "core_ctrl"), (0x610210, "base0_ctrl"), (0x610220, "base1_ctrl"),
    (0x610020, "intr0"), (0x610024, "intr1"), (0x61002c, "intr_en"), (0x610030, "supervisor"),
    (0x610080, "core_err_m"), (0x610084, "core_err_d"),
    (0x610090, "base1_err_m"), (0x610094, "base1_err_d"),
    (0x640000, "core_put"), (0x640004, "core_get"),
    (0x641000, "base0_put"), (0x641004, "base0_get"),
    (0x642000, "base1_put"), (0x642004, "base1_get"),
]

def log(msg):
    line = time.strftime("%Y-%m-%dT%H:%M:%S ") + msg
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)

_run = True
def _stop(*_):
    global _run
    _run = False
signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def sh(args, t=40):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=t)
    except Exception as e:
        log("cmd %r failed: %s" % (args, e))
        return None

def capture_diag(rd):
    """Dump the EVO register set + a short GET-park burst + dmesg to an event
    file. Called BEFORE the S3 so it is guaranteed (unlike the observatory's
    read-only capture, which the fast S3 raced). nv50_disp_intr_error logs every
    real method-error trap unconditionally, and intr0 & 0x001f0000 latches a real
    exception; both let a future reader tell fetch-park from method-error."""
    ts = time.strftime("%Y%m%dT%H%M%S")
    path = os.path.join(EVENTDIR, "wedge-%s-watchdog.txt" % ts)
    KW = ("base-1: timeout", "base-0: timeout", "core: timeout", "nv50_dmac_wait",
          "notifier timeout", "ERROR", "mthd", "chid", "nv50_disp_intr_error")
    try:
        dl = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=6).stdout.splitlines()
        ctx = "\n".join(l for l in dl if any(k in l for k in KW))[-8000:]
        tail = "\n".join(dl[-120:])
    except Exception as ex:
        ctx = tail = "(dmesg failed: %s)" % ex
    def dec(em, intr0, chid):
        return "valid=%d type=%d mthd=0x%03x pend=%d" % ((em >> 31) & 1, (em >> 12) & 7, em & 0xffc, (intr0 >> (16 + chid)) & 1)
    try:
        with open(path, "w") as e:
            e.write("# nvac-s3-unwedge: pre-S3 wedge capture %s\n\n" % time.strftime("%Y-%m-%dT%H:%M:%S"))
            e.write("# register burst (~100ms cadence) -- GET frozen behind PUT = fetch-park:\n")
            v = None
            for i in range(8):
                v = {n: rd(o) for o, n in DIAG_REGS}
                e.write("+%.1fs " % (i * 0.1) + " ".join("%s=%08x" % (n, v[n]) for _, n in DIAG_REGS) + "\n")
                time.sleep(0.1)
            e.write("\n# decode (chid core=0, base1=2):\n")
            e.write("#   core : %s\n" % dec(v["core_err_m"], v["intr0"], 0))
            e.write("#   base1: %s\n" % dec(v["base1_err_m"], v["intr0"], 2))
            e.write("#   intr0=%08x supervisor=%08x  (intr0 & 0x001f0000 != 0 => real EVO exception latched -> method-error, not fetch-park)\n" % (v["intr0"], v["supervisor"]))
            e.write("\n# dmesg trap/timeout lines (presence of 'ERROR ... mthd' => method-error):\n%s\n" % ctx)
            e.write("\n# dmesg tail (last 120):\n%s\n" % tail)
        log("diag captured -> %s" % path)
    except Exception as ex:
        log("capture_diag failed: %s" % ex)

def nic_ok():
    r = sh(["ping", "-c", "2", "-W", "2", "-I", IFACE, GW], t=15)
    return bool(r) and r.returncode == 0


def check_nic():
    """Probe the NIC after the S3 and, if needed, bounce the link exactly ONCE.

    Returns "ok", "bounced" or "tot". The forcedeth TX wedge after deep-S3 survives
    the kernel's own NETDEV watchdog; only an administrative down/up rebuilds the rings.
    """
    if nic_ok():
        return "ok"
    time.sleep(NIC_GRACE)
    if nic_ok():
        return "ok"
    log("nic: %s dead after the S3 (gateway %s unreachable) -> link bounce" % (IFACE, GW))
    sh(["ip", "link", "set", IFACE, "down"])
    time.sleep(1)
    sh(["ip", "link", "set", IFACE, "up"])
    time.sleep(NIC_GRACE * 2)
    if nic_ok():
        log("nic: ok after bounce")
        return "bounced"
    log("nic: still DEAD after bounce")
    return "tot"


def recover(rd=None):
    """Heal the park with one deep-S3 cycle, then verify and report the outcome.

    rd: BAR0 reader from main(). With it, the EVO ctrl registers are re-read after the
    resume, so "geheilt" in the report is a measurement, not an assumption.
    """
    log("S3 recovery: nv-watchdog stop -> rtcwake -m mem -s %d -> nv-watchdog start" % RTCWAKE_S)
    rc, dt, tco = "?", 0.0, "?"
    try:
        sh(["rc-service", "nv-watchdog", "stop"])
        t0 = time.time()
        r = sh(["rtcwake", "-m", "mem", "-s", str(RTCWAKE_S)], t=RTCWAKE_S + 120)
        dt = time.time() - t0
        rc = r.returncode if r else "?"
        log("rtcwake rc=%s dt=%.1fs" % (rc, dt))
    finally:
        ra = sh(["rc-service", "nv-watchdog", "start"])  # ALWAYS attempt to re-arm the TCO
        tco = ra.returncode if ra else "?"
    # Post-check. Wrapped: this daemon is the only net, a surprise here must never kill it,
    # and the report goes out in the finally, so even a failed post-check is reported.
    nic, park = "?", "Register nicht gelesen"
    try:
        time.sleep(POST_S3_SETTLE)
        if rd is not None:
            c2, b2 = rd(CORE_CTRL), rd(BASE1_CTRL)
            if (c2 | b2) & 0x80000000:
                park = "PARK BESTEHT core=%08x base1=%08x" % (c2, b2)
            else:
                park = "Park weg"
        nic = check_nic()
    except Exception as ex:  # noqa: BLE001 - a failed post-check must not stop the watchdog
        log("post-S3 check failed: %r" % ex)
    finally:
        if rc != 0:
            kopf = "EVO-Wedge NICHT geheilt, S3-Zyklus fehlgeschlagen"
        elif park.startswith("PARK BESTEHT"):
            kopf = "EVO-Wedge NICHT geheilt, Park besteht nach dem S3"
        elif park == "Park weg":
            kopf = "EVO-Wedge geheilt"
        else:
            kopf = "S3-Zyklus gefahren"
        log("RESULT rc=%s dt=%.1fs tco=%s park=%s nic=%s kernel=%s"
            % (rc, dt, tco, park, nic, KERNEL))
        alert("%s (%s): rtcwake rc=%s dt=%.1fs, %s, TCO rc=%s, Netz %s"
              % (kopf, KERNEL, rc, dt, park, tco, nic))

def kill_blanker():
    sh(["bash", "-c", "for p in $(pgrep -f 'swayidle -d -w timeout 600'); do kill \"$p\"; done"])

def alert(msg):
    log("alert: " + msg)
    r = sh(["klaus-send", "--plain", "nvac-s3-unwedge: " + msg], t=15)
    if not r or r.returncode != 0:
        log("alert: klaus-send failed rc=%s" % (r.returncode if r else "?"))

def main():
    fd = os.open(PCI, os.O_RDONLY)
    n = min(os.fstat(fd).st_size, 0x800000)
    m = mmap.mmap(fd, n, mmap.MAP_SHARED, mmap.PROT_READ)
    rd = lambda o: struct.unpack_from("<I", m, o)[0]
    dry = os.environ.get("NVAC_S3_DRYRUN") == "1"
    streak = 0
    last_cg = last_bg = None
    hits = []
    log("start interval=%ss confirm=%s rtcwake=%ss%s" % (INTERVAL, CONFIRM, RTCWAKE_S, "  [DRY-RUN]" if dry else ""))
    while _run:
        c, b = rd(CORE_CTRL), rd(BASE1_CTRL)
        cg, bg = rd(CORE_GET), rd(BASE1_GET)
        # wedge = ctrl bit31 latched AND the GET pointer frozen (channel not draining)
        cw = bool(c & 0x80000000) and cg == last_cg
        bw = bool(b & 0x80000000) and bg == last_bg
        wedged = last_cg is not None and (cw or bw)
        last_cg, last_bg = cg, bg
        streak = streak + 1 if wedged else 0
        if streak >= CONFIRM:
            log("WEDGE core=%08x base1=%08x cget=%08x bget=%08x streak=%d" % (c, b, cg, bg, streak))
            streak = 0
            now = time.time()
            hits = [t for t in hits if now - t < STORM_WINDOW]
            if len(hits) >= STORM_N:
                log("STORM: %d recoveries < %ds -> kill idle-blank + alert (watchdog stays up)" % (len(hits) + 1, int(STORM_WINDOW)))
                if not dry:
                    kill_blanker()
                    alert("Wedge-Storm (%d in %dmin) -> Idle-Blank gekillt (no-blank), bitte schauen" % (len(hits) + 1, int(STORM_WINDOW // 60)))
                hits = []
                time.sleep(COOLDOWN)
                last_cg = last_bg = None
                continue
            capture_diag(rd)   # GUARANTEED pre-S3 register+dmesg snapshot (read-only)
            if dry:
                log("DRY-RUN: would S3-recover now (skipped)")
            else:
                recover(rd)
            hits.append(time.time())
            time.sleep(COOLDOWN)
            last_cg = last_bg = None   # re-baseline GET pointers after the re-POST
            continue
        time.sleep(INTERVAL)
    log("stop")

if __name__ == "__main__":
    main()
