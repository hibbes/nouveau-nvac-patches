# v4 der nv04-FIFO-Serie: Stand der Vorbereitung, NICHTS GESENDET

Stand 21.08.2026, 04:00. Serie neu aufgebaut im Arbeitsbaum
`scratchpad/v4wt` (Branch `v4-respin`) auf `c21bb4193868`.

## Ausgangslage nach Lyudes Durchsicht vom 20.08.2026

| Patch | Rueckmeldung | Stand |
|---|---|---|
| 1/4 unsubscribe kill-event | **Reviewed-by Lyude**, 15:10 -0400 | unveraendert, Tag nachgetragen |
| 2/4 fence-context-Handschlag | Entwurfsvorschlag Lyude, 16:01 -0400 | **neu gebaut** |
| 3/4 CACHE_ERROR-Filter | drei Umbauwuensche, 17:07 -0400 | umgebaut, plus `(benign)` |
| 4/4 kill-events auf NV50+ | **Rueckfrage Lyude, 17:56 -0400** | **offen, siehe unten** |

## 2/4: zweimal korrigiert, beide Male gegen mich selbst

### Erste Fehllesung (20.08. abends)

Ein frueherer Stand behauptete, Lyude schlage vor, dass **beide** Seiten
`fctx->lock` nehmen, und verwarf den Entwurf deshalb. Das steht so nicht in
seiner Mail. Die Sperre nimmt nur die Init-Seite.

### Zweite Fehllesung (21.08. nachts, durch die adversariale Pruefung gefunden)

Der daraufhin gebaute Patch war "sein Entwurf plus eine Schranke". Der
Ordnungsbeweis dazu hatte einen Pfeil verkehrt herum. Nachgerechnet mit
`sc-interleavings.py`, alle Verschraenkungen unter sequentieller Konsistenz:

    arm: LOAD killed, dann STORE ready   ->  6 Verschraenkungen, 1 verliert den Kill
    arm: STORE ready, dann LOAD killed   ->  6 Verschraenkungen, 0 verlieren ihn

Der Zeuge: `arm()` liest `killed`==0, `kill()` setzt `killed` und liest
`ready`==0, `arm()` setzt `ready`. Beide steigen aus. Das ist unter SC
erreichbar, also auf jeder Maschine. **Keine Schranke kann das verbieten**,
Schranken ordnen Zugriffe, sie vertauschen sie nicht.

Die Reihenfolge stammt aus Lyudes Skizze ("Check the killed atomic ... Set
the atomic indicating that the fence is ready"). Der Patch benennt das
sachlich, ohne Vorwurf.

### Warum die Sperre ganz verschwindet

Die Kill-Seite darf `fctx->lock` gar nicht anfassen, bevor der Kontext fertig
ist, denn genau das ist der behobene Fehler:

    nv50_fence.c:45   fctx = chan->fence = kzalloc_obj(*fctx);
    nouveau_fence.c   nouveau_fence_context_new() -> spin_lock_init(&fctx->lock)

`chan->fence` wird bei der Allokation veroeffentlicht, `spin_lock_init()`
laeuft erst danach. `->ready` muss also **ohne** Sperre lesbar sein. Damit
beantwortet sich auch Lyudes offene Frage ("might not need to be an atomic"):
ein `bool` reicht, aber es braucht `smp_store_release` beim Setzen und
`smp_load_acquire` beim Lesen, damit ein Leser, der es gesetzt sieht, auch die
initialisierte Sperre und Liste sieht.

Es sind also zwei Schrankenpaare mit zwei verschiedenen Aufgaben:

- **release/acquire** veroeffentlicht den fertigen Kontext (Message-Passing)
- **`smp_mb()` auf beiden Seiten** schliesst das Store-Buffering-Rennen
  (`tools/memory-model/litmus-tests/SB+fencembonceonces.litmus`)

## 3/4

Alle drei Wuensche umgesetzt (`subc`/`addr`/`name` vorab, Kommentar zum
Mesa-Probe, Debug- statt Fehlerstufe). Zusaetzlich traegt die Debug-Zeile jetzt
`(benign)`, damit die beiden Formatzeichenketten nicht identisch sind.
Belegt statt vermutet: `nvkm_debug` ist von der 100-Spalten-Pruefung
ausgenommen, `nvkm_error` nicht (`checkpatch.pl` `$logFunctions` kennt `err`,
nicht `error`). Eine Fassung mit waehlbarer Stufe geht nicht: `nvkm_printk`
kopiert den Stufennamen als Token in den Aufruf.

## 4/4: OFFEN, Rueckfrage unbeantwortet

Lyude hat am 20.08. um 17:56 -0400 geantwortet, Message-ID
`9414b8d122b9489056d72ee1605787ee038e62b7.camel@redhat.com`:

> This one is going to need some input from others I believe [...] I'd want
> to really make sure we know what the implications of enabling an event like
> this on Tesla are [...] What kind of testing have you done with this so far
> in terms of workload [...] Tried running any games, anything graphics
> intensive, etc.?

**Das ist zu beantworten, bevor 4/4 mitgeht.** Empfehlung der Pruefung: 4/4
herausnehmen, die Frage ehrlich beantworten (auch wenn es keine Spiele gab),
und den Klassen-Schalter spaeter zusammen mit einem Tesla-Erholungspfad
einreichen. Beim Herausnehmen ist 1/4 anzupassen: sein reviewter Text verweist
auf "The last patch in this series subscribes Tesla channels as well".

## Pruefstand

- checkpatch `--strict` auf alle vier: 0 Fehler, 0 Warnungen, 0 Anmerkungen
- Serie wendet in Reihenfolge auf `c21bb4193868` an
- Uebersetzung mit `W=1`: laeuft

## Offen

- Antwort auf Lyudes 4/4-Rueckfrage
- Soak-Aussage im Cover: die Maschine laeuft die **alte** v3-Fassung von 2/4,
  nicht den Handschlag. Der Satz "equivalent to 2/4 since 2026-08-06" gilt
  nicht mehr und muss raus.
- Entscheidung: `Assisted-by: Claude:claude-opus-5` stehen lassen? Lyude
  schrieb "consider trying to write the respin without using claude!". Das Tag
  ist die ehrliche Angabe; es zu entfernen waere die Unwahrheit.
