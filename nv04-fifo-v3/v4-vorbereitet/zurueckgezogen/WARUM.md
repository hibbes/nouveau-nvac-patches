# Warum der CACHE_ERROR-Patch zurueckgezogen wurde, 21.08.2026

Er stand seit v2 in der Serie und stufte einen bestimmten CACHE_ERROR auf
Debug-Stufe herunter, mit der Begruendung, Mesa loese ihn durch einen
Bindungstest aus. Die vierte Pruefrunde hat diese Zuschreibung angegriffen,
und sie haelt nicht.

## Was belegt ist

| Beleg | Fundstelle |
|---|---|
| `0x0060` ist `NV826F_SET_CONTEXT_DMA_SEMAPHORE` | `include/nvhw/class/cl826f.h:38` |
| Die einzigen Schreiber im Baum | `nv84_fence_emit32()` und `nv84_fence_sync32()`, `nv84_fence.c:41` und `:64` |
| Beide auf Subkanal 0 | `include/nvif/push006c.h:11` |
| NVAC benutzt nv84_fence und nv04_fifo_intr | `nouveau_drm.c:500`, `g84.c:215`, `g98.c:54` |
| Alle 99 Belegzeilen | `subc 0 mthd 0060 data beef0201` |
| Andere CACHE_ERROR in denselben Logs | `subc 3` und `subc 4`, andere Methoden |
| `0xbeef` im Kernelbaum | kommt nur im zurueckgezogenen Patch selbst vor |

Mesa schreibt die Methode also nicht. Der Kernel schreibt sie, bei jedem
Emit und jedem Sync, mit einem Griff, den der Userspace beim Anlegen des
Kanals mitgibt (`nouveau_chan.c:416`).

## Was NICHT belegt ist

Dass genau diese beiden Schreibvorgaenge die 99 Meldungen erzeugen. Liefen
sie bei jedem Fence in den Fehler, waeren es Millionen.

**Korrektur 21.08. nachmittags:** eine fruehere Fassung dieser Datei
behauptete, `0xbeef0201` komme in Mesa 26.1.6 nicht vor. Das war falsch,
die lokale Mesa-Kopie war unvollstaendig (nur `src/mesa`). Im Tarball
steht es: `src/gallium/drivers/nouveau/nouveau_screen.c:299`,
`.vram = 0xbeef0201, .gart = 0xbeef0202`. Mesa WAEHLT den Griff, reicht
ihn ueber libdrm durch, der Kernel bindet ihn (`nouveau_chan.c:416`) und
schreibt ihn selbst in die Methode. Das schliesst die Kette, es schwaecht
sie nicht.

**Was die Gegenprobe vom Nachmittag ergab:** der Rueckzug war Vorsicht,
keine Notwendigkeit. Der einzige Fehlerpfad von 0x0060 auf G80+ ist ein
fehlgeschlagener RAMHT-Lookup, und der Griff steht nachweislich im RAMHT
(sonst gelaenge kein Fence). Die 99 Zeilen sind also ein sporadischer
Lookup-Aussetzer auf einen immer vorhandenen Griff. "Kernel ist Schreiber"
heisst nicht "Kernel ist Verursacher". Der Handler ueberspringt nur das
eine Wort, die Bindung des vorigen identischen Fence bleibt stehen, was
erklaert, warum 99 Faelle nie geschadet haben.

**Die entscheidende Messung** sitzt seit 21.08. im 7.2.0-Soakkernel, im
0x0060-Zweig von nv04.c: pull0 mit HASH_FAILED/HASH_BUSY, und ob der
Griff im RAMHT des Kanals steht ("0060-probe"). HASH_FAILED plus present
heisst Puller-Aussetzer, MISSING heisst Treiberfehler. Lokal bleibt 0004
aktiv, weil 0020 ueber den 0x0060-Zweig die Kill-Staffel freihaelt.

Eine falsche Zuschreibung durch eine zweite zu ersetzen waere schlimmer als
gar keine. Deshalb steht im Anschreiben nur das Belegte.

## Warum das den Patch kippt

"Harmloser Userspace-Test" ist ein Grund zum Daempfen. "Unser eigener
Fence-Pfad landet im CACHE_ERROR" ist ein Grund hinzusehen. Solange die
Ursache offen ist, darf eine Meldung, die der Treiber ueber seinen eigenen
Pushbuf macht, nicht heruntergestuft werden.

Der Fall wird getrennt untersucht. Belege: `/home/neo/fab-443-logs/` und
`/home/neo/fab-lag-log/`, 99 Treffer ueber drei Logs und zwei Kernel.

## Lastversuch 21.08., 16:42 bis 16:59

Versuch, den Fehler mit gezielter Last zu provozieren (`fence-storm.sh`):
viele kleine GLX-Fenster, die kommen, 5 bis 20 s laufen und gehen, auf
7.2.0-gentoo-nvac-soak mit scharfer 0060-probe.

| Lauf | Dauer | Fenster gleichzeitig | gestartet | CACHE_ERROR | 0060-probe |
|---|---|---|---|---|---|
| Probe | 120 s | 8 | 76 | 0 | 0 |
| voll | 600 s | 12 | 557 | 0 | 0 |

Jeder Pushbuf-Submit setzt einen Kernel-Fence (`nouveau_gem.c:950`), und
`nv84_fence_emit32/sync32` schreiben 0x0060 UNBEDINGT bei jedem Fence.
Bei 12 Fenstern ohne Vsync sind das grob 1,5 Millionen Schreibvorgaenge
in zehn Minuten. Kein Treffer. Die Menge loest es also nicht aus.

Die Fremdmaschine (dieselbe Karte, 0ac380b1) hatte ueber 30 Treffer am Tag
bei einem Bruchteil dieses Verkehrs. Besitzer der Kanaele dort: kwin_x11
58x, Xorg 22x, kwin_wayland 6x, plasmashell 6x, Renderer 6x, ksplashqml
1x. Kein normaler GL-Client. Mesa-Relnotes 25.0 bis 26.1 zeigen fuer
nouveau/nv50 nur Refactoring am Screen-Setup, nichts am Pushbuf-Pfad.

Staerkster verbliebener Unterschied: Xorg. Auf Xorg teilen sich alle
Clients den Kanal des X-Servers, der Compositor faehrt seine Komposition
darueber. Hier nicht installiert, also nicht nachstellbar.

Stand: Probe bleibt scharf und laeuft im Alltag mit. Ein Xorg-Nachbau
lohnt erst, wenn sie auch nach Tagen nichts zeigt.

## ERSTER TREFFER der 0060-probe, 21.08. 18:09:21

    CACHE_ERROR - ch 2 [labwc[8055]] subc 0 mthd 0060 data beef0201
    pull0 20000010 HASH_FAILED ramht MISSING (0060-probe)

Auf labwcs eigenem Kanal, 70 Minuten nach dem Fence-Sturm, bei normaler
Desktop-Arbeit. GPU danach gesund (PGRAPH_STATUS 0, labwc PID
unveraendert, kein D-State). Der Warner hat Klaus alarmiert, weil er die
Zeile als fifo-trap liest; er greift bei labwc nicht ein.

**Was davon gilt:** `pull0 20000010 HASH_FAILED` ist echt. Der Puller hat
den RAMHT-Lookup auf 0xbeef0201 abgelehnt. Das bestaetigt envytools: der
einzige Fehlerpfad von 0x0060 auf G80 ist ein fehlgeschlagener Lookup.

**Was davon NICHT gilt:** `ramht MISSING` ist ein Artefakt meiner Probe.
Auf NV50 ist das RAMHT pro Kanal, und nv50_eobj_ramht_add fuegt mit
chid 0 ein (nv50.c:44); chid geht in den Hash ein (ramht.c:36). Meine
Probe suchte mit dem FIFO-chid 2, also im falschen Eimer nach dem
falschen Eintrag, und haette fuer JEDEN Kanal MISSING gemeldet.

Die Frage "steht der Griff im RAMHT" ist also weiter offen. Probe v2 (seit
22.08. im 7.2.0-Quellbaum, Modul noch zu bauen): sucht mit chid 0 UND
gibt alle lebenden Eintraege des Kanals mit Griff/chid aus. Der naechste
Treffer erklaert sich selbst, unabhaengig von meiner Hash-Annahme.

Lehre: eine Probe, die ja/nein meldet, muss ihre Annahme mitliefern.
"MISSING" ohne die Liste der vorhandenen Eintraege war genau das nicht.
