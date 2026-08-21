#!/usr/bin/env python3
"""Sendet die v4-Serie. Neuer Faden, 1/3..3/3 als Antwort auf das Cover.
Sendet NUR mit --really. Ohne: zeigt Empfaenger, Betreffe, Message-IDs."""
import os, sys, re, email, smtplib, ssl, time, socket
from email import policy
from email.utils import make_msgid, formatdate

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = sorted(f for f in os.listdir(HERE) if re.match(r'000[0-3]-.*\.patch$', f))
TO  = ["nouveau@lists.freedesktop.org", "dri-devel@lists.freedesktop.org"]
CC  = ["linux-kernel@vger.kernel.org",
       "Lyude Paul <lyude@redhat.com>",
       "Danilo Krummrich <dakr@kernel.org>",
       "Maarten Lankhorst <maarten.lankhorst@linux.intel.com>",
       "Maxime Ripard <mripard@kernel.org>",
       "Thomas Zimmermann <tzimmermann@suse.de>",
       "David Airlie <airlied@gmail.com>",
       "Simona Vetter <simona@ffwll.ch>",
       "Ben Skeggs <bskeggs@redhat.com>"]
ENVELOPE_FROM = "mczernohous@gmail.com"   # Gmail-Login, Envelope
HEADER_FROM   = "Marek Czernohous <marek@czernohous.de>"  # wie in den Patches

def load_env():
    env = {}
    for line in open(os.path.expanduser("~/.smtp-gmail.env")):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    return env["SMTP_USER"], env["SMTP_PASS"].replace(" ", "")

def build(path, in_reply_to, references):
    raw = open(os.path.join(HERE, path), "rb").read()
    msg = email.message_from_bytes(raw, policy=policy.compat32)
    # git format-patch setzt From/Date/Subject; wir setzen Envelope-konforme Kopfzeilen
    msg.replace_header("From", HEADER_FROM) if "From" in msg else msg.add_header("From", HEADER_FROM)
    msg["To"] = ", ".join(TO)
    msg["Cc"] = ", ".join(CC)
    mid = make_msgid(domain="gmail.com")
    msg["Message-ID"] = mid
    if "Date" in msg: msg.replace_header("Date", formatdate(localtime=True))
    else: msg["Date"] = formatdate(localtime=True)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references
    if "MIME-Version" not in msg: msg["MIME-Version"] = "1.0"
    if "Content-Type" not in msg: msg["Content-Type"] = "text/plain; charset=UTF-8"
    if "Content-Transfer-Encoding" not in msg: msg["Content-Transfer-Encoding"] = "8bit"
    return msg, mid

def main():
    really = "--really" in sys.argv
    rcpts = TO + [re.sub(r'.*<([^>]+)>.*', r'\1', c) for c in CC]
    print("Dateien:", *FILES, sep="\n  ")
    print("Empfaenger (%d):" % len(rcpts), *rcpts, sep="\n  ")
    msgs, cover_mid = [], None
    for f in FILES:
        msg, mid = build(f, cover_mid, cover_mid)
        if cover_mid is None: cover_mid = mid
        msgs.append((f, msg, mid))
        print("  %-60s %s" % (msg["Subject"][:60], mid))
    if not really:
        print("\nTROCKENLAUF. Nichts gesendet. Mit --really senden.")
        return 0
    user, pw = load_env()
    log = open(os.path.join(HERE, "SEND-LOG-%s.txt" % time.strftime("%Y-%m-%d")), "a")
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    s.starttls(context=ssl.create_default_context()); s.login(user, pw)
    for f, msg, mid in msgs:
        refused = s.sendmail(ENVELOPE_FROM, rcpts, msg.as_bytes())
        line = "%s  %s  %s  refused=%s" % (time.strftime("%H:%M:%S"), f, mid, refused or "none")
        print(line); log.write(line + "\n"); log.flush()
        time.sleep(2)
    s.quit(); log.close()
    print("GESENDET:", len(msgs), "Mails. Cover Message-ID:", cover_mid)
    return 0

if __name__ == "__main__":
    sys.exit(main())
