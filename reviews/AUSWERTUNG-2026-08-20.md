# Lyudes Durchsicht der Teardown-Serie, 20.08.2026

Sieben Mails, alle von Lyude Paul, alle heute zwischen 13:55 und 14:36.
Das ist die am 18.08. zugesagte Durchsicht.

## Ergebnis: die ganze Serie ist durch

| Patch | Ergebnis |
|---|---|
| **v2 von 1/3** (`disable_work_sync`) | **Reviewed-by + GEPUSHT** |
| **2/3** (DP-IRQ-Work drainen) | **Reviewed-by** |
| **3/3** (outp vor Zugriff pruefen) | **Reviewed-by** |

Zur v2 von 1/3, 13:55:

> "This makes sense to me.
>  Reviewed-by: Lyude Paul <lyude@redhat.com>
>  Will push to drm-misc-next-fixes in just a moment"

Und 13 Minuten spaeter die Korrektur, 14:08:

> "(I misspoke, this patch ended up in drm-misc-next instead as fixes is
>  currently closed)"

**Der Patch ist also im Baum**, in drm-misc-next statt drm-misc-next-fixes,
weil der Fixes-Zweig gerade geschlossen ist.

## Die hpd_work-Frage ist geschlossen, und zwar zu unseren Gunsten

Am 15.08. hatte Marek seine eigene Cover-Aussage zurueckgenommen ("It says
'there is no fourth patch here' ... my cover letter answered it too
confidently") und offen geschrieben, er koenne es nicht ausschliessen.

Lyude antwortete darauf zweimal. Erst, 14:26:

> "I wrote a lot of that code, so I can just send out a patch for it in a
>  moment and CC you."

Dann, zehn Minuten spaeter, nach nochmaligem Lesen, 14:36:

> "Actually - after rereading this again, nah - this isn't an issue. So
>  long as the connector IRQs are blocked at that point, it should be
>  good. MST connectors aren't, but that's also fine - they use the IRQ
>  notify thingies of the non-MST connectors, so they're indirectly
>  blocked by that."

**Kein Fehler an dieser Stelle.** Die MST-Connectoren haengen indirekt an den
Notify-Objekten der Nicht-MST-Connectoren und sind darueber mitgeblockt.

Bemerkenswert an der Reihenfolge: die ehrliche Selbstkorrektur vom 15.08. hat
genau das bewirkt, was sie sollte. Der Maintainer, der den Code geschrieben
hat, hat die Frage aufgenommen, zuerst einen Patch angeboten und dann
festgestellt, dass keiner noetig ist. Haette der Cover-Satz als Befund
dagestanden, waere daraus eine Korrektur an uns geworden.

## Gesamtstand der Einreichungen

| Serie | Stand |
|---|---|
| forcedeth 1/2 und 2/2 | je 2x Reviewed-by (Horman, Zhu Yanjun) |
| Spur 1 v4, 1/2 MSI rearm | Reviewed-by Lyude, "will push" |
| Spur 1 v4, 2/2 | ersetzt durch Lyudes Sechserserie, Reported-by Marek auf 3/6 und 4/6 |
| teardown v2 1/3 | **Reviewed-by + in drm-misc-next** |
| teardown 2/3 | Reviewed-by |
| teardown 3/3 | Reviewed-by |
| drm_panic-Bericht | bestaetigt, Patch in Arbeit, nicht eingereicht |

Nichts steht mehr offen und wartet auf eine Antwort von uns.
