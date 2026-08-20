# drm_panic: was nach Jocelyns Angebot moeglich ist

Jocelyn Falempe, 19.08.2026, auf den Bericht vom 15.08.:

> "Yes the nouveau drm panic implementation is not perfect. The framebuffer is
> not accessible from the CPU, so the only way to display something is to
> ioremap it, and currently that is not possible safely in a panic context."
> "I still think that it works well enough, and that it's still better than a
> frozen display."
> "Regarding the design direction, I think it would be nice to have something
> similar to kmap_local_page() for iomem."
> "**I will review and help with testing any patch that can improve the current
> situation.**"

Alles Folgende gegen `c21bb4193868` geprueft, Datei und Zeile genannt.

## Der Sachstand in vier Punkten

1. **`ttm_bo_kmap_try_from_panic()` hilft bei VRAM nicht.** Der Kopfkommentar
   sagt es selbst (`ttm_bo_util.c:394`): "or NULL if the bo is in iomem". Der
   Rumpf prueft `!bo->resource->bus.is_iomem` (`:401`) und faellt sonst auf
   `return NULL` (`:404`). Einziger Nutzer im Baum ist `xe`.

2. **`drm_scanout_buffer.pages` ist der Systemspeicherweg.** Laut
   `include/drm/drm_panic.h:43-50` benutzt der Panic-Code darauf
   `kmap_local_page_try_from_panic()`. Fuer einen iomem-Puffer gibt es keine
   Entsprechung.

3. **Das naheliegende Gegenstueck existiert, taugt auf 64 Bit aber nicht.**
   `io_mapping_map_atomic_wc()` (`include/linux/io-mapping.h:65`) ist genau
   "kmap_local fuer iomem": es ruft `__iomap_local_pfn_prot()`, ohne
   Zuteilung. **Aber** die Fassung steht unter `CONFIG_HAVE_ATOMIC_IOMAP`
   (`:30`), und das haengt auf x86 an `X86_32` (`arch/x86/Kconfig:3130-3132`).
   Auf x86-64 greift die Ersatzfassung ab `:165`, und die ruft
   `io_mapping_map_wc()`, also `ioremap_wc()`. Im Panic-Kontext ist das genau
   das, was der Bericht beanstandet.

   **Jocelyns Wunsch beschreibt also etwas, das fuer 64 Bit nicht existiert.**

4. **Es gibt trotzdem ein Muster, das heute schon funktioniert.** VRAM-Treiber
   bilden im Panic-Callback gar nichts ab, sondern reichen eine laengst
   bestehende Abbildung durch. `ast` (`ast/ast_mode.c:625-639`):

       iosys_map_set_vaddr_iomem(&sb->map[0], ast_plane_vaddr(ast_plane));
       return 0;

   Kein `ioremap`, keine Sperre, kein Schlafen.

## Was nouveau stattdessen tut

`nv50_wndw_get_scanout_buffer()` (`dispnv50/wndw.c:671`) ruft im
Panic-Kontext `nouveau_bo_map(nvbo)`. Und `nouveau_bo_map()`
(`nouveau_bo.c:668-680`) prueft **nicht**, ob die Abbildung schon besteht:

    ret = ttm_bo_reserve(&nvbo->bo, false, false, NULL);   /* :672, schlaeft */
    ret = ttm_bo_kmap(..., &nvbo->kmap);                   /* :676, ioremap */

Eine vorab angelegte Abbildung allein wuerde also nichts retten, solange der
Callback diese Funktion ueberhaupt aufruft.

## Zwei moegliche Richtungen

### (a) nouveau-lokal, klein, hier testbar

Die Abbildung ausserhalb des Panic-Kontexts anlegen und den Callback
nicht mehr abbilden lassen:

- `nv50_wndw_prepare_fb()` pinnt den Puffer ohnehin schon nach VRAM
  (`wndw.c:554`, `nouveau_bo_pin(nvbo, NOUVEAU_GEM_DOMAIN_VRAM, true)`).
  Dort zusaetzlich `nouveau_bo_map()`, in `nv50_wndw_cleanup_fb()` wieder
  `nouveau_bo_unmap()`.
- `nv50_wndw_get_scanout_buffer()` benutzt nur noch `nvbo->kmap.virtual`,
  wenn vorhanden, und gibt sonst sauber auf.

Damit verschwinden `ioremap` und beide schlafenden Sperren aus dem Panic-Weg,
und der Callback sieht aus wie der von `ast`.

**Preis:** eine dauerhafte CPU-Abbildung des Scanout-Puffers, solange er
angezeigt wird. Genau das tut `ast` ohnehin permanent.

**Nutzen konkret hier:** auf NVAC funktioniert der Panic-Bildschirm derzeit
nicht "gut genug", sondern gar nicht: der Handler nimmt einen zweiten Oops
innerhalb von `panic()`. Das ist das Gegenargument zu Jocelyns "works well
enough", und es ist auf dieser Maschine belegt (02.06.2026, netconsole-
Mitschnitt liegt daneben).

### (b) Die von Jocelyn gewuenschte Infrastruktur

Ein echtes `kmap_local`-Gegenstueck fuer iomem auf 64 Bit, also
`HAVE_ATOMIC_IOMAP` fuer x86-64 oder ein neuer, panic-tauglicher Helfer.
Das ist Kern- und Architekturarbeit, weit ausserhalb von nouveau, und sollte
nicht nebenbei mitgemacht werden.

## Vorschlag fuer das weitere Vorgehen

(a) als eigenen Patch anbieten, mit ausdruecklichem Hinweis, dass er (b) nicht
ersetzt, sondern nur den nouveau-Weg auf das Muster bringt, das andere
VRAM-Treiber schon benutzen. Jocelyn hat Durchsicht und Test zugesagt.

**Offen und vor einem Patch zu klaeren:**
- Haelt die Abbildung ueber einen Moduswechsel? `prepare_fb`/`cleanup_fb`
  laufen paarweise, aber das ist zu belegen, nicht anzunehmen.
- Was passiert bei mehreren Fenstern und beim Fensterwechsel?
- Kostet die dauerhafte Abbildung auf kleinen Karten (NVAC hat 256 MB) etwas,
  das auffaellt?
- Gibt es Faelle, in denen der Scanout-Puffer im Systemspeicher liegt? Dann
  greift schon heute der `pages`-Weg und (a) darf ihn nicht kaputtmachen.

**Diese vier Fragen sind noch nicht beantwortet.** Sie gehoeren geprueft,
bevor irgendetwas an die Liste geht.

# ============================================================
# Die vier offenen Fragen, beantwortet (20.08.2026)
# ============================================================

Alles gegen `c21bb4193868` gelesen, plus eine Messung an der Karte.

## 1. Halten prepare_fb und cleanup_fb zusammen? JA

`drm_modeset_helper_vtables.h:1237-1238` schreibt es fest: cleanup_fb raeumt
"any resources allocated for the given framebuffer and plane configuration in
@prepare_fb" ab. `nv50_wndw_cleanup_fb()` (`wndw.c:524-535`) entpinnt schon
heute symmetrisch zu `nv50_wndw_prepare_fb()` (`:554`). Ein
`nouveau_bo_unmap()` dort waere dieselbe Symmetrie.

Zu beachten: prepare_fb bekommt den **neuen**, cleanup_fb den **alten**
Zustand. Waehrend eines Flips sind also kurz beide Puffer abgebildet. Das ist
korrekt, aber es verdoppelt kurzzeitig den BAR-Bedarf, siehe Punkt 3.

## 2. Mehrere Fenster? UNPROBLEMATISCH

`drm_panic_register()` (`drm_panic.c:1036-1041`) haengt an **jede** Plane mit
`get_scanout_buffer` einen eigenen kmsg_dumper. Im Panic werden also alle
gerufen. Mit Ansatz (a) traegt jede Plane, die ein prepare_fb hatte, ihre
eigene Abbildung. Planes ohne Framebuffer steigen schon heute bei
`wndw.c:661` mit `-EINVAL` aus. Skaliert also von selbst.

## 3. Kostet die dauerhafte Abbildung etwas? HIER NEIN, ALLGEMEIN JA, UND ES
##    IST KEINE KOSTENFRAGE, SONDERN EINE SICHERHEITSFRAGE

**Das ist der wichtigste Befund, und er stellt Ansatz (a) unter Vorbehalt.**

nouveau entzieht IO-Abbildungen wieder, wenn das BAR-Fenster knapp wird
(`nouveau_bo.c:1342-1355`): bei `-ENOSPC` nimmt es den aeltesten Eintrag der
`io_reserve_lru`, ruft `drm_vma_node_unmap()` und
`nouveau_ttm_io_mem_free_locked()`, und setzt `bus.offset = 0`,
`bus.addr = NULL`.

**Es gibt dabei keinen Refcount.** `nouveau_ttm_io_mem_free_locked()`
(`:1233-1246`) ruft `nvif_object_unmap_handle()` bedingungslos. Und
`ttm_bo_ioremap()` (`ttm_bo_util.c:325`) bildet genau auf
`mem->bus.offset + offset` ab.

Folge: wird ein Puffer verdraengt, waehrend der Kern eine `ttm_bo_kmap`-
Abbildung darauf haelt, zeigt der Kernzeiger anschliessend auf das, was jetzt
in diesem BAR-Fenster liegt. Das waere **stille Verfaelschung statt Absturz**,
also schlimmer als der gemeldete Fehler.

Wie kommt ein Puffer auf diese LRU? **Nur ueber den Userspace-mmap-
Fehlerpfad** (`nouveau_gem.c:57-60`), nicht durch eine reine Kernabbildung.
Ein Scanout-Puffer, in den der Compositor oder Plymouth per CPU zeichnet, ist
aber genau so ein Fall.

**Messung an dieser Karte (02:00.0, C79 / GeForce 9400):**

    Region 1 (BAR1): 256 MB, prefetchable
    VRAM laut Treiber: 256 MiB

BAR1 deckt hier den ganzen VRAM ab, `-ENOSPC` kann also gar nicht eintreten.
**Auf dieser Maschine ist Ansatz (a) sicher.** Auf nv50-Karten mit mehr VRAM
als BAR (verbreitet: 1 GB VRAM, 256 MB BAR) ist er es nicht.

**Konsequenz fuer einen Patch:** der Scanout-Puffer muss von dieser
Verdraengung ausgenommen werden, solange die Panic-Abbildung besteht. Zwei
Formen denkbar, beide noch nicht durchgerechnet:
- `nouveau_bo_del_io_reserve_lru()` fuer den Puffer, solange er abgebildet
  ist, und beim cleanup_fb wieder hinein; oder
- die Verdraengungsschleife ueberspringt Puffer mit gesetztem
  `kmap.virtual`.

Ohne eine solche Absicherung darf (a) nicht eingereicht werden.

## 4. Faelle im Systemspeicher? KEINE REGRESSION, ABER ZWEIG ERHALTEN

`nv50_wndw_prepare_fb()` pinnt nach `NOUVEAU_GEM_DOMAIN_VRAM` (`wndw.c:554`),
fuer nv50+ liegt der Scanout-Puffer also im VRAM. Der Callback behandelt
trotzdem beide Faelle (`wndw.c:676-679`, Verzweigung ueber
`TTM_BO_MAP_IOMEM_MASK`). nouveau setzt `sb->pages` **nirgends**, der
`pages`-Weg aus `drm_panic.h:43-50` ist bei nouveau also heute ungenutzt.

Ansatz (a) bricht damit nichts, muss aber die Nicht-iomem-Verzweigung
erhalten.

# Stand

Fragen 1, 2 und 4 sind unkritisch. Frage 3 hat einen echten Haken zutage
gefoerdert, der in der urspruenglichen Skizze nicht vorkam. **Der Patch ist
damit nicht mehr trivial**, und das ist genau der Grund, warum er vor dem
Schreiben untersucht wurde.

Fuer die Antwort an Jocelyn ist das eine gute Nachricht: es gibt etwas
Substanzielles zu berichten, naemlich dass der naheliegende Weg auf
BAR-begrenzten Karten in stille Verfaelschung laufen kann, und dass
`io_mapping_map_atomic_wc()` auf 64 Bit nicht das ist, wonach es aussieht.

**Noch nichts gesendet, kein Patch geschrieben.**
