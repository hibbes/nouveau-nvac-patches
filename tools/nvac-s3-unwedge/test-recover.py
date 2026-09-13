#!/usr/bin/env python3
"""Selbsttest fuer recover() in nvac-s3-unwedge-watchdog.py.

Prueft die Haertung vom 13.09.2026: Netzpruefung mit einmaligem Link-Bounce und
eine Telegram-Meldung des ERGEBNISSES nach jeder Heilung. Vorher meldete der
Waechter nur im Storm-Zweig, ein Wedge mit anschliessend totem Netz blieb also
in einem unbeaufsichtigten Boot vollstaendig stumm.

Reine Simulation: sh() wird ersetzt, es laeuft kein rtcwake, kein ping, kein ip.
Aufruf: python3 test-recover.py [pfad/zum/watchdog.py]
"""
import importlib.util
import sys
import types

PFAD = sys.argv[1] if len(sys.argv) > 1 else "/usr/local/bin/nvac-s3-unwedge-watchdog.py"
PASS, FAIL = 0, 0


def ok(name):
    global PASS
    PASS += 1
    print("  ok   %s" % name)


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    print("  FAIL %s%s" % (name, ("\n       " + detail) if detail else ""))


def lade():
    spec = importlib.util.spec_from_file_location("wd_unter_test", PFAD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Umgebung:
    """Ersetzt sh(), log() und sleep() im Modul und schneidet alles mit."""

    def __init__(self, m, rtcwake_rc=0, ping_fehlt=0, rtcwake_wirft=False,
                 rtcwake_none=False, rearm_rc=0, rearm_none=False, klaus_rc=0):
        self.m = m
        self.calls = []
        self.zeilen = []
        self.rtcwake_rc = rtcwake_rc
        self.ping_fehlt = ping_fehlt
        self.rtcwake_wirft = rtcwake_wirft
        self.rtcwake_none = rtcwake_none
        self.rearm_rc = rearm_rc
        self.rearm_none = rearm_none
        self.klaus_rc = klaus_rc
        m.sh = self.sh
        m.log = self.zeilen.append
        m.time.sleep = lambda _s: None

    def sh(self, args, t=40):
        args = list(args)
        self.calls.append(args)
        rc = 0
        if args[0] == "rtcwake":
            if self.rtcwake_wirft:
                raise OSError("rtcwake explodiert")
            if self.rtcwake_none:
                return None            # so liefert das echte sh() jede Ausnahme ab
            rc = self.rtcwake_rc
        elif args[:3] == ["rc-service", "nv-watchdog", "start"]:
            if self.rearm_none:
                return None
            rc = self.rearm_rc
        elif args[0] == "klaus-send":
            rc = self.klaus_rc
        elif args[0] == "ping":
            if self.ping_fehlt > 0:
                self.ping_fehlt -= 1
                rc = 1
        return types.SimpleNamespace(returncode=rc, stdout="", stderr="")

    # Auswertungshilfen
    def namen(self):
        return [c[0] for c in self.calls]

    def telegramme(self):
        return [" ".join(c) for c in self.calls if c[0] == "klaus-send"]

    def hat(self, prog, *teile):
        for c in self.calls:
            if c[0] == prog and all(any(t in a for a in c) for t in teile):
                return True
        return False

    def protokoll(self):
        return "\n".join(self.zeilen)


def rc_service(env, dienst, aktion):
    return ["rc-service", dienst, aktion] in env.calls


print("== recover()-Selbsttest gegen %s" % PFAD)
m = lade()

if not hasattr(m, "recover"):
    print("FAIL: Modul hat keine Funktion recover()")
    raise SystemExit(1)

# 1 Gesunder Verlauf: heilen, Netz pruefen, Ergebnis melden
env = Umgebung(m)
m.recover()
if rc_service(env, "nv-watchdog", "stop") and rc_service(env, "nv-watchdog", "start") \
        and "rtcwake" in env.namen():
    ok("heilung_stop_rtcwake_start")
else:
    fail("heilung_stop_rtcwake_start", str(env.namen()))

if env.hat("ping", "enp0s10", "192.168.1.1"):
    ok("gesund_prueft_netz")
else:
    fail("gesund_prueft_netz", "kein ping in %s" % env.namen())

if "ip" not in env.namen():
    ok("gesund_kein_unnoetiger_bounce")
else:
    fail("gesund_kein_unnoetiger_bounce", str(env.calls))

t = env.telegramme()
if len(t) == 1 and "rc=0" in t[0]:
    ok("gesund_meldet_ergebnis")
else:
    fail("gesund_meldet_ergebnis", "Telegramme: %r" % t)

# Reihenfolge: das Netz wird erst NACH dem Wiederbewaffnen geprueft
n = env.namen()
if "ping" in n and "rc-service" in n and n.index("ping") > (len(n) - 1 - n[::-1].index("rc-service")):
    ok("netzpruefung_nach_rearm")
else:
    fail("netzpruefung_nach_rearm", str(n))

# 2 rtcwake scheitert: Waechter trotzdem scharf, Meldung sagt es
env = Umgebung(m, rtcwake_rc=1)
m.recover()
t = env.telegramme()
if rc_service(env, "nv-watchdog", "start"):
    ok("rtcwake_fehler_rearm_trotzdem")
else:
    fail("rtcwake_fehler_rearm_trotzdem", str(env.namen()))
if t and "rc=1" in t[0] and "fehlgeschlagen" in t[0]:
    ok("rtcwake_fehler_meldet")
else:
    fail("rtcwake_fehler_meldet", "Telegramme: %r" % t)

# 3 rtcwake wirft eine Ausnahme: Waechter MUSS wieder scharf sein
env = Umgebung(m, rtcwake_wirft=True)
try:
    m.recover()
    geworfen = False
except Exception:
    geworfen = True
if rc_service(env, "nv-watchdog", "start"):
    ok("ausnahme_rearm_trotzdem%s" % (" (Ausnahme durchgereicht)" if geworfen else ""))
else:
    fail("ausnahme_rearm_trotzdem", str(env.namen()))

# 4 Netz zweimal tot, dann Bounce, danach gesund
env = Umgebung(m, ping_fehlt=2)
m.recover()
if env.hat("ip", "down", "enp0s10") and env.hat("ip", "up", "enp0s10"):
    ok("netz_tot_bounct_link")
else:
    fail("netz_tot_bounct_link", str(env.calls))
t = env.telegramme()
if t and ("ounce" in t[0] or "Bounce" in t[0]):
    ok("netz_bounce_meldet")
else:
    fail("netz_bounce_meldet", "Telegramme: %r" % t)

# 5 Netz bleibt tot: genau ein Bounce-Versuch, deutliche Meldung
env = Umgebung(m, ping_fehlt=99)
m.recover()
anzahl_down = sum(1 for c in env.calls if c[0] == "ip" and "down" in c)
if anzahl_down == 1:
    ok("netz_dauerhaft_tot_nur_ein_bounce")
else:
    fail("netz_dauerhaft_tot_nur_ein_bounce", "%d Bounce-Versuche" % anzahl_down)
t = env.telegramme()
if t and any(w in t[0].upper() for w in ("TOT", "FAIL")):
    ok("netz_dauerhaft_tot_meldet")
else:
    fail("netz_dauerhaft_tot_meldet", "Telegramme: %r" % t)

# 6 Genau eine Meldung je Heilung, kein Telegramm-Sturm
env = Umgebung(m, ping_fehlt=2)
m.recover()
if len(env.telegramme()) == 1:
    ok("genau_ein_telegramm_je_heilung")
else:
    fail("genau_ein_telegramm_je_heilung", "%d Telegramme" % len(env.telegramme()))

# 7 Die Kernelversion steht in der Meldung (sonst weiss man nicht, welcher Kernel betroffen war)
env = Umgebung(m)
m.recover()
t = env.telegramme()
if t and any(ch.isdigit() for ch in t[0].split("nvac-s3-unwedge:")[-1]):
    ok("meldung_nennt_kontext")
else:
    fail("meldung_nennt_kontext", "Telegramme: %r" % t)

# 8 Ein Fehler in der Nachpruefung darf den Waechter NIE toeten: er ist das einzige Netz.
env = Umgebung(m)
_echtes_sh = env.sh


def sh_mit_bombe(args, t=40):
    if args[0] == "ping":
        raise RuntimeError("ping explodiert")
    return _echtes_sh(args, t)


m.sh = sh_mit_bombe
try:
    m.recover()
    ok("nachpruefung_fehler_toetet_waechter_nicht")
except Exception as ex:
    fail("nachpruefung_fehler_toetet_waechter_nicht", "Ausnahme entkommen: %r" % ex)
if rc_service(env, "nv-watchdog", "start"):
    ok("nachpruefung_fehler_rearm_trotzdem")
else:
    fail("nachpruefung_fehler_rearm_trotzdem", str(env.namen()))
if len(env.telegramme()) == 1:
    ok("nachpruefung_fehler_meldet_trotzdem")
else:
    fail("nachpruefung_fehler_meldet_trotzdem", "%d Telegramme" % len(env.telegramme()))

# 9 Wiederbewaffnen des TCO scheitert: die Meldung MUSS das sagen, sonst entwarnt sie falsch
for art, kw in (("rc=1", {"rearm_rc": 1}), ("None", {"rearm_none": True})):
    env = Umgebung(m, **kw)
    m.recover()
    t = env.telegramme()
    if t and "TCO" in t[0] and ("TCO rc=0" not in t[0]):
        ok("rearm_fehler_meldet_%s" % art)
    else:
        fail("rearm_fehler_meldet_%s" % art, "Telegramme: %r" % t)

# 10 rtcwake liefert None (Timeout oder fehlendes Programm): rc='?' zaehlt als Fehlschlag
env = Umgebung(m, rtcwake_none=True)
m.recover()
t = env.telegramme()
if t and "rc=?" in t[0] and "fehlgeschlagen" in t[0]:
    ok("rtcwake_none_meldet_fehlschlag")
else:
    fail("rtcwake_none_meldet_fehlschlag", "Telegramme: %r" % t)

# 11 Protokollspur: das Ergebnis steht auch im Log, nicht nur im Telegramm
env = Umgebung(m)
m.recover()
p = env.protokoll()
if "RESULT" in p and "nic=ok" in p and "alert:" in p:
    ok("ergebnis_steht_im_log")
else:
    fail("ergebnis_steht_im_log", p)

# 12 klaus-send scheitert: das muss im Log auftauchen
env = Umgebung(m, klaus_rc=1)
m.recover()
if "klaus-send failed" in env.protokoll():
    ok("klaus_send_fehler_geloggt")
else:
    fail("klaus_send_fehler_geloggt", env.protokoll())

# 13 Mutationsschutz: down MUSS vor up kommen, und der letzte ip-Aufruf ist up
env = Umgebung(m, ping_fehlt=2)
m.recover()
ip = [c for c in env.calls if c[0] == "ip"]
if len(ip) == 2 and "down" in ip[0] and "up" in ip[-1]:
    ok("bounce_reihenfolge_down_dann_up")
else:
    fail("bounce_reihenfolge_down_dann_up", str(ip))

# 14 Mutationsschutz: ping ist per -I an enp0s10 gebunden (wlan0 hat eine Route zum selben Gateway)
env = Umgebung(m)
m.recover()
pings = [c for c in env.calls if c[0] == "ping"]
gebunden = all("-I" in c and c.index("-I") + 1 < len(c) and c[c.index("-I") + 1] == "enp0s10"
               for c in pings)
if pings and gebunden:
    ok("ping_an_interface_gebunden")
else:
    fail("ping_an_interface_gebunden", str(pings))

# 15 Nach dem Resume werden die EVO-Register neu gelesen: "geheilt" wird gemessen, nicht behauptet
def rd_aus(werte):
    return lambda off: werte.get(off, 0)


import inspect
if "rd" in inspect.signature(m.recover).parameters:
    env = Umgebung(m)
    m.recover(rd_aus({m.CORE_CTRL: 0x2d0b001b, m.BASE1_CTRL: 0x0c05001b}))
    t = env.telegramme()
    if t and "Park weg" in t[0]:
        ok("register_nachgelesen_park_weg")
    else:
        fail("register_nachgelesen_park_weg", "Telegramme: %r" % t)
    env = Umgebung(m)
    m.recover(rd_aus({m.CORE_CTRL: 0x8f0e001b, m.BASE1_CTRL: 0x8e07001b}))
    t = env.telegramme()
    if t and "PARK BESTEHT" in t[0] and "8f0e001b" in t[0]:
        ok("register_nachgelesen_park_besteht")
    else:
        fail("register_nachgelesen_park_besteht", "Telegramme: %r" % t)
else:
    fail("register_nachgelesen_park_weg", "recover() nimmt kein rd entgegen")
    fail("register_nachgelesen_park_besteht", "recover() nimmt kein rd entgegen")

print("RESULT: %d pass, %d fail" % (PASS, FAIL))
raise SystemExit(0 if FAIL == 0 else 1)
