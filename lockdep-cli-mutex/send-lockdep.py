#!/usr/bin/env python3
"""Sendet den lockdep-Bericht als eine Mail, neuer Faden. NUR mit --really."""
import os, sys, re, smtplib, ssl, time
from email.message import EmailMessage
from email.utils import make_msgid, formatdate

HERE = os.path.dirname(os.path.abspath(__file__))
TO = ["nouveau@lists.freedesktop.org", "dri-devel@lists.freedesktop.org"]
CC = ["linux-kernel@vger.kernel.org",
      "Lyude Paul <lyude@redhat.com>",
      "Danilo Krummrich <dakr@kernel.org>",
      "Simona Vetter <simona@ffwll.ch>",
      "Maarten Lankhorst <maarten.lankhorst@linux.intel.com>",
      "Maxime Ripard <mripard@kernel.org>",
      "Thomas Zimmermann <tzimmermann@suse.de>",
      "David Airlie <airlied@gmail.com>"]
ENVELOPE_FROM = "mczernohous@gmail.com"
HEADER_FROM = "Marek Czernohous <marek@czernohous.de>"

def load_env():
    env = {}
    for line in open(os.path.expanduser("~/.smtp-gmail.env")):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    return env["SMTP_USER"], env["SMTP_PASS"].replace(" ", "")

def main():
    really = "--really" in sys.argv
    raw = open(os.path.join(HERE, "bericht.txt"), encoding="utf-8").read()
    m = re.match(r'Subject: (.*)\n (.*)\n\n', raw)
    subject = m.group(1) + " " + m.group(2).strip()
    body = raw[m.end():]
    msg = EmailMessage()
    msg["From"] = HEADER_FROM; msg["To"] = ", ".join(TO); msg["Cc"] = ", ".join(CC)
    msg["Subject"] = subject
    mid = make_msgid(domain="gmail.com"); msg["Message-ID"] = mid
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body, charset="utf-8", cte="8bit")
    rcpts = TO + [re.sub(r'.*<([^>]+)>.*', r'\1', c) for c in CC]
    print("Betreff:", subject); print("Message-ID:", mid)
    print("Empfaenger (%d):" % len(rcpts), *rcpts, sep="\n  ")
    print("Koerper: %d Zeilen" % body.count("\n"))
    if not really:
        print("\nTROCKENLAUF. Nichts gesendet."); return 0
    user, pw = load_env()
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    s.starttls(context=ssl.create_default_context()); s.login(user, pw)
    refused = s.sendmail(ENVELOPE_FROM, rcpts, msg.as_bytes()); s.quit()
    line = "%s  bericht.txt  %s  refused=%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), mid, refused or "none")
    print(line)
    open(os.path.join(HERE, "SEND-LOG-%s.txt" % time.strftime("%Y-%m-%d")), "a").write(line + "\n")
    return 0

if __name__ == "__main__": sys.exit(main())
