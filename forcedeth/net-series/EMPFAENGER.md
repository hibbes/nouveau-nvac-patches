# Empfängerliste für die netdev-Einreichung

Ermittelt am 13.08.2026 mit `scripts/get_maintainer.pl` gegen beide Patches,
danach **von Hand geprüft**, weil `get_maintainer` seine Adressen aus
MAINTAINERS und alten Sign-offs zieht und damit genau die Quellenart ist, die
beim nouveau-Versand in der Nacht zuvor einen Bounce erzeugt hat.

```
To:  netdev@vger.kernel.org
Cc:  Rain River <rain.1986.08.12@gmail.com>
     Zhu Yanjun <zyjzyj2000@gmail.com>
     Andrew Lunn <andrew+netdev@lunn.ch>
     "David S. Miller" <davem@davemloft.net>
     Eric Dumazet <edumazet@google.com>
     Jakub Kicinski <kuba@kernel.org>
     Paolo Abeni <pabeni@redhat.com>
     Tobias Diedrich <tobiasdiedrich@gmail.com>
     linux-kernel@vger.kernel.org
```

## Begründungen

- **Rain River und Zhu Yanjun** sind laut MAINTAINERS (Zeile 10168 ff.,
  "FORCEDETH GIGABIT ETHERNET DRIVER", S: Maintained) die Zuständigen.
- **Andrew Lunn, Miller, Dumazet, Kicinski, Abeni**: die netdev-Runde.
- **Tobias Diedrich** ist der Autor von `1a1ca86158ee`, dem `Fixes:`-Commit
  von 1/2. Adresse bewusst **nicht** die aus dem Commit
  (`ranma+kernel@tdiedrich.de`, zuletzt 2009 gesehen), sondern
  `tobiasdiedrich@gmail.com`, mit der derselbe Name **2020** noch committet
  hat. Einschränkung: dass es dieselbe Person ist, folgt aus dem Namen, es
  ist nicht bewiesen.

## Bewusst NICHT im Verteiler

- **Jeff Garzik `<jgarzik@redhat.com>`**, von `get_maintainer` vorgeschlagen.
  Seine letzten Commits im Baum stammen von **2016** und tragen
  `jeff@garzik.org`, nicht die Red-Hat-Adresse. Die stammt aus alten
  Sign-offs. Dieselbe Falle wie `bskeggs@nvidia.com`.
- **Ayaz Abdulla `<aabdulla@nvidia.com>`**, Autor von `86a0f04387bf`, dem
  `Fixes:`-Commit von 2/2. Seit **2006** nichts mehr im Baum, und NVIDIAs
  Exchange weist externe Absender ab, wie der Bounce vom 13.08. zeigte. Die
  späteren "Ayaz"-Treffer im Log sind ein anderer Mensch (Ayaz Siddiqui,
  Intel).

## Formregeln, gegen die Quelle geprüft

`Documentation/process/maintainer-netdev.rst`:

- Betreff muss den Zielbaum nennen, hier `[PATCH net]` (Fehlerkorrektur).
- `Fixes:` ist für Korrekturen Pflicht, unabhängig vom Baum. Beide haben ihn.
- `Cc: stable` ist bei netdev **erlaubt** ("While it used to be the case that
  netdev submissions were not supposed to carry explicit CC: stable ... that
  is no longer the case today"). 1/2 trägt ihn, 2/2 nicht, weil dessen Pfad
  hinter einem Debug-Modulparameter liegt.
- "reverse xmas tree" ist nicht betroffen, beide Patches ändern nur
  Schleifenbedingungen, keine Deklarationsblöcke.
- Nicht innerhalb von 24 Stunden erneut posten.
