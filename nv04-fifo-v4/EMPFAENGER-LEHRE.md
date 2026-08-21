# Ben Skeggs: keine gueltige Adresse mehr (Stand 21.08.2026)

- `bskeggs@nvidia.com`: v3 am 12.08. dreimal unzustellbar ("Adresse nicht
  gefunden"). Letzte Commits mit dieser Adresse: November 2025.
- `bskeggs@redhat.com`: v4 am 21.08. viermal AutoResponse "This email inbox
  is no longer in use". Die Autoantworten landeten im Gmail-Papierkorb, der
  Inbox-Bot hat sie aussortiert.
- In MAINTAINERS steht er nicht mehr; `get_maintainer` lieferte ihn nur als
  `blamed_fixes` (Autor des Fixes:-Commits ea13e5abf807).

Folge: bei der naechsten Sendung weglassen, bis eine gueltige Adresse
auftaucht. Er ist kein Pflichtempfaenger, die drei Listen haben alles.
Lyude und Danilo sind die Maintainer.

Merke: `get_maintainer --nogit` nimmt blamed_fixes-Autoren mit, deren
Adresse Jahre alt sein kann. Vor dem Senden die Adresse gegen das Git-Log
der letzten Monate halten, nicht nur gegen MAINTAINERS.
