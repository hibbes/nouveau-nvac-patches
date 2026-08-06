# Versand-Anleitung (Stand 2026-07-25)

Alles hier ist vorbereitet, aber **nichts ist gesendet**. Reihenfolge: erst die
Antwort im v1-Thread, dann (nach der Fault-Injektor-Validierung) die v2-Serie.

## Vorher einmalig: fehlende Perl-Module

`git send-email` lief im Trockenlauf sauber durch, weil `IO::Socket::SSL` und
`Authen::SASL` da sind. Zwei Module aus dem April-Setup fehlen inzwischen
(vermutlich depclean). Falls der echte Versand an TLS scheitert:

    sudo emerge -a dev-perl/Net-SMTP-SSL dev-perl/Email-Valid

## SICHERHEIT: Passwort im Klartext

`~/linux-nouveau-patches/.git/config` enthält `sendemail.smtppass` im Klartext
(Gmail-App-Passwort, Setup vom April). Empfehlung nach dem Versand:

    git config --unset sendemail.smtppass     # danach fragt git interaktiv
    # und das App-Passwort im Google-Konto rotieren

## Schritt 1: Antwort im v1-Thread (jetzt)

    cd ~/linux-nouveau-patches
    git send-email --no-chain-reply-to --suppress-cc=all \
      --to=nouveau@lists.freedesktop.org \
      --cc="Lyude Paul <lyude@redhat.com>" \
      --cc="Danilo Krummrich <dakr@kernel.org>" \
      --cc=dri-devel@lists.freedesktop.org \
      --cc=linux-kernel@vger.kernel.org \
      ~/outgoing-nouveau-v2/v1-thread-reply.txt

`sendemail.confirm=always` ist gesetzt, git fragt also vor dem Absenden noch
einmal. Zum Gegenlesen ohne Versand `--dry-run` anhängen (so getestet, Result OK).


## WICHTIG: Gmail schreibt die Absenderadresse um

Im Lore-Archiv der v1 steht:

    From:           Marek Czernohous <mczernohous@gmail.com>   <- von Gmail ersetzt
    Signed-off-by:  Marek Czernohous <marek@czernohous.de>

`git send-email` setzt korrekt `marek@czernohous.de`, aber der Gmail-SMTP
ersetzt den Header durch die Kontoadresse, weil die Domain-Adresse dort nicht
als verifizierter "Send mail as"-Alias hinterlegt ist. Beim `git am` wuerde die
Autorenschaft damit von der Signed-off-by-Adresse abweichen, was auf den Listen
und von patchwork/b4 angemeckert wird.

**Fix beim Erzeugen der Patches** (kein Gmail-Eingriff noetig): `--from` auf die
Gmail-Adresse setzen, dann schreibt git eine `From:`-Zeile in den Nachrichten-
KOERPER, und die hat beim Anwenden Vorrang:

    git format-patch -3 -o ~/outgoing-nouveau-v2 --cover-letter -v2 \
      --base=origin/master \
      --from="Marek Czernohous <mczernohous@gmail.com>"

Verifiziert: jeder Patch bekommt dann `From: Marek Czernohous <marek@czernohous.de>`
als erste Body-Zeile.

**Saubere Alternative (einmalig):** in Gmail unter Einstellungen, Konten und
Import, "Senden als" die Adresse `marek@czernohous.de` hinzufuegen und per Link
verifizieren. Danach bleibt der Header erhalten und `--from` wird ueberfluessig.

Die bereits gesendete Thread-Antwort ist davon NICHT betroffen: aus einer Antwort
wird nichts angewendet, die Umschreibung ist dort rein kosmetisch.

## Schritt 2: v2-Serie (ERST nach der Validierung)

### 2a) Signed-off-by setzen (nur du, nicht die KI)

    cd ~/linux-nouveau-patches
    git checkout nouveau-fifo-recovery-v2
    git rebase --exec 'git commit --amend --no-edit -s' origin/master

Prüfen, dass unter jedem Patch ein `Signed-off-by:` UND der
`Assisted-by: Claude:claude-opus-5` steht:

    git log -3 --format='%s%n%b' | grep -E 'Signed-off-by|Assisted-by'

### 2b) Patches neu erzeugen

    rm -f ~/outgoing-nouveau-v2/v2-000*.patch
    git format-patch -3 -o ~/outgoing-nouveau-v2 --cover-letter -v2 \
      --base=origin/master \
      --from="Marek Czernohous <mczernohous@gmail.com>"   # siehe Abschnitt oben

Danach den Cover-Letter-Text wieder einsetzen (Vorlage:
`~/outgoing-nouveau-v2/v2-cover-body.txt` bzw. der bereits befüllte
`v2-0000-cover-letter.patch`, der beim Neuerzeugen überschrieben wird, also
vorher wegkopieren) und das Testkapitel um die Injektionsergebnisse ergänzen.

### 2c) Senden

    git send-email --no-chain-reply-to --suppress-cc=all \
      --to=nouveau@lists.freedesktop.org \
      --cc="Lyude Paul <lyude@redhat.com>" \
      --cc="Danilo Krummrich <dakr@kernel.org>" \
      --cc=dri-devel@lists.freedesktop.org \
      --cc=linux-kernel@vger.kernel.org \
      ~/outgoing-nouveau-v2/v2-*.patch

Empfängerliste bewusst wie bei v1 (schlank). `get_maintainer.pl` schlägt
zusätzlich Ben Skeggs, David Airlie und Simona Vetter persönlich vor; die
bekommen es über dri-devel mit.

## Danach

Message-IDs aus dem Versand-Log in die Memory eintragen, damit das
Morgen-Briefing den neuen Thread mitpollt (Sektion "1b) Nouveau Kernel
Patches" in `~/.claude/morning-briefing.sh`).
