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
