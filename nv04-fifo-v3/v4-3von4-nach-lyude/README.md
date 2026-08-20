# 3/4 nach Lyudes Durchsicht vom 20.08.2026, vorbereitet aber NICHT gesendet

## Lyudes drei Punkte (Mail vom 20.08. 21:21 MESZ)

> I think we should probably keep the print of the channel name even when
> demoting this to debug in case we have to investigate this someday. We
> should also move the nvkm_chan_get_chid(...) call and nvkm_chan_put(...)
> call out of the conditional, and probably move all of the printf
> arguments into their own local variables in this function so there's
> less to maintain for future changes.

| Wunsch | Umsetzung |
|---|---|
| Kanalname auch im Debug-Zweig | `name` steht in **beiden** Meldungen |
| `get_chid`/`put` aus der Bedingung | umschliessen jetzt beide Zweige |
| Argumente in lokale Variablen | `subc`, `addr`, `name` |

Nebeneffekt: beide Formatzeichenketten sind identisch. Wer die Meldung aendert,
aendert zwei gleiche Zeilen, und die Meldung ist ueber beide Loglevel greppbar.

## Zwei eigene Entscheidungen

**Zusatz "(benign, skipped)" gestrichen.** Er haette die Zeile auf 108 Spalten
getrieben, und `coding-style.rst` verlangt, Meldungstexte nicht zu umbrechen
(sonst nicht mehr greppbar). Der Loglevel unterscheidet die Faelle ohnehin. So
liegen beide Zeilen bei exakt 100 Spalten, innerhalb der checkpatch-Grenze.

**`nvkm_chan_get_chid()` laeuft jetzt auch im harmlosen Fall.** Kein Rueckschritt,
sondern Rueckkehr zum Mainline-Verhalten: dort steht der Aufruf ohnehin
unbedingt. Die alte Fassung hatte ihn zur Optimierung in den else-Zweig
gezogen, und genau das will Lyude nicht.

## Stand der Pruefung

- `checkpatch --strict`: 0 Warnungen, 0 Checks. Nur der erwartete fehlende
  `Signed-off-by`, den setzt Marek.
- Laengste neue Zeile: 100 Spalten (Tabs expandiert).
- `nvkm_debug` ist bei `subdev.h:90` definiert, `nvkm_error` aus derselben
  Quelle wird in der Datei bereits benutzt.
- **Bautest steht aus**, der 7.2.0-Baum baut gerade. Gelesen ist nicht gebaut.

## Offene Entscheidung

Ob das eine v4 der ganzen Viererserie wird oder ein Neuversand nur von 3/4.
Lyude hat sich bisher nur zu 3/4 geaeussert. Kommt zu den anderen dreien noch
etwas, ist eine gesammelte v4 sinnvoller als vier Einzelversaende. Deshalb
warten.
