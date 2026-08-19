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
