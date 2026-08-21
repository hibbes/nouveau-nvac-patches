# v4 der nv04-FIFO-Serie: Stand der Vorbereitung, NICHTS GESENDET

Stand 21.08.2026, 04:00. Serie neu aufgebaut im Arbeitsbaum
`scratchpad/v4wt` (Branch `v4-respin`) auf `c21bb4193868`.

## Ausgangslage nach Lyudes Durchsicht vom 20.08.2026

| Patch | Rueckmeldung | Stand |
|---|---|---|
| 1/4 unsubscribe kill-event | **Reviewed-by Lyude**, 15:10 -0400 | unveraendert, Tag nachgetragen |
| 2/4 fence-context-Handschlag | Entwurfsvorschlag Lyude, 16:01 -0400 | **neu gebaut** |
| 3/4 CACHE_ERROR-Filter | drei Umbauwuensche, 15:21 -0400 | umgebaut, plus `(benign)` |
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

**Korrektur meiner eigenen Beschreibung.** Ein frueherer Stand nannte als
Lyudes drei Wuensche "subc/addr/name vorab, Kommentar zum Mesa-Probe,
Debug- statt Fehlerstufe". Falsch: Kommentar und Debug-Stufe waren in der
v3 schon drin. Seine drei Wuensche sind woertlich:

1. "keep the print of the channel name even when demoting this to debug"
2. "move the nvkm_chan_get_chid(...) call and nvkm_chan_put(...) call out
   of the conditional"
3. "move all of the printf arguments into their own local variables"

Zu 2. gehoert eine Klarstellung, weil es beim Nachlesen zunaechst wie ein
Versaeumnis aussah: gemeint ist die **innere** Bedingung. In der v3 lagen
`get_chid`/`put` im `else`-Zweig des Benign-Tests, weshalb die Debug-Zeile
keinen Kanalnamen hatte. Sie stehen jetzt vor dem `if`/`else`
beziehungsweise dahinter. Aus der aeusseren Bedingung
(`if (!(pull0 ...) || !nv04_fifo_swmthd(...))`) herauszuziehen war nicht
gemeint und waere auch falsch, das wuerde bei jedem CACHE_ERROR eine
Kanalreferenz nehmen.

Alle drei sind umgesetzt. Zusaetzlich traegt die Debug-Zeile jetzt
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

## Nachtrag 06:50: zwei empirische Befunde

- **checkpatch verlangt den Parameternamen.** Ich hatte
  `nouveau_fence_context_arm(struct nouveau_channel *)` an die unbenannten
  Nachbarn im Header angeglichen. checkpatch meldet daraufhin "function
  definition argument [...] should also have an identifier name". Die
  Nachbarn sind Altbestand, den checkpatch nicht prueft. Zurueckgenommen,
  die benannte Form bleibt.
- **Uebersetzung belegt**: `nouveau_chan.o`, `nouveau_fence.o` und
  `nvkm/engine/fifo/nv04.o` mit `W=1` ohne jede Warnung, dazu ein voller
  `make drivers/gpu/drm/nouveau/` mit `rc=0` (773 Objekte, `nouveau.o`
  gelinkt). Diesmal wirklich mit `W=1`, nicht nur behauptet.
- **Vollstaendigkeit geprueft**: `->context_new` wird nur an einer Stelle
  aufgerufen (`nouveau_chan.c:516`), `arm()` steht in :520 direkt dahinter,
  und `nouveau_channel_init()` hat genau einen Aufrufer. Es gibt keinen Weg,
  auf dem ein Fence-Kontext unbewaffnet bleibt.

## Nachtrag 07:45: Abgleich mit ALLEN Lyude-Mails

Auf Wunsch alle 16 Lyude-Mails gelesen, auch ausserhalb des v3-Fadens. Zwei
Befunde, die die v4 betreffen, standen nicht im Fifo-Faden:

**"this is way too verbose"** (18.08., zur Spur-1-v4 2/2). Das ist das
"to verbose", an das die Erinnerung hing. Es galt einem neunzeiligen
Kommentarblock. Unser neues 2/4 hatte 28 Kommentarzeilen auf 30 Zeilen Code
und haette denselben Einwand geerntet. Gekuerzt auf 14, je Schranke ein
Einzeiler, das Warum steht in der Commit-Botschaft. checkpatch verlangt an
jeder Schranke einen Kommentar, ein Sammelkommentar reicht nicht (empirisch
geprueft, nicht angenommen).

**"nah - this isn't an issue"** (20.08. 18:36, Teardown-Faden). Lyude
schliesst den `hpd_work`-Punkt selbst: "So long as the connector IRQs are
blocked at that point, it should be good. MST connectors aren't, but that's
also fine - they use the IRQ notify thingies of the non-MST connectors, so
they're indirectly blocked by that." Zehn Minuten zuvor hatten sie noch
angeboten, selbst einen Patch zu schicken. Der Punkt stand bei uns als offen
und ist erledigt.

Weiteres, ohne Handlungsbedarf fuer die v4:

- "In the future you should probably put a backtrace if you've seen this in
  the wild" (Spur-1-v4 2/2). Fuer die Fifo-Serie gibt es keinen Oops, das
  Anschreiben zitiert stattdessen den Injektionslauf.
- "this isn't the bug, the bug is that we're reading nv_encoder->crtc at all
  here" (Spur-1-v4 2/2), gefolgt von der eigenen 6-Patch-Serie. Erledigt.
- "We don't set nv_encoder->crtc at the boot-time hardware state readback"
  wurde 108 Minuten spaeter selbst zurueckgenommen: "...this was wrong,
  oops!"
- Lyudes eigene v1 4/6 traegt `Reported-by: Marek Czernohous`.
- Vier reine `Reviewed-by` (Teardown 2/3 und 3/3, Spur-1-v4 1/2,
  fence-uevent-v2), letzteres mit "Will push to drm-misc-next-fixes",
  13 Minuten spaeter korrigiert auf drm-misc-next.

Nichts in den Mails widerspricht der v4.

**Anrede:** in keiner Mail und in keiner Signatur steht eine Pronomenangabe.
Ohne Beleg wird they/them verwendet.
