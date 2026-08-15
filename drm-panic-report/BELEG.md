# Primaerbeleg: drm_panic ioremapt im Panik-Kontext (2026-06-02)

Geholt am 15.08.2026 von `lorawan-gw:/var/log/netconsole-gentoo-neo.log`
(10,9 MB, letzte Aenderung 03.06.2026 19:33). Roh gesichert in
`netconsole-2026-06-02-roh.txt`, Zeilen 100 bis 190 der Quelldatei.

## Wichtig zur Lesbarkeit: die Zeilen kamen in falscher Reihenfolge an

netconsole verschickt per UDP, und hier schrieben zwei CPUs gleichzeitig in
den Puffer. Die Rohdatei mischt deshalb Oops 1 und Oops 2 zeilenweise
durcheinander, und selbst innerhalb eines Traces stimmt die Reihenfolge nicht.
Die Zeilen selbst sind unveraendert, nur ihre Abfolge ist unbrauchbar.

**Wer daraus zitiert, muss das dazusagen.** Unten steht die geordnete Fassung,
jede Zeile ist woertlich aus der Rohdatei, nur die Reihenfolge ist
wiederhergestellt.

## Der Ausloeser (Oops 1, nicht Gegenstand des Berichts)

    nouveau 0000:02:00.0: fifo: CACHE_ERROR - ch 2 [labwc[3950]] subc 3 mthd 0f00 data 0000007b
    nouveau 0000:02:00.0: fifo:000000:0002:0002:[labwc[3950]] errored - disabling channel
    BUG: kernel NULL pointer dereference, address: 0000000000000000
    #PF: supervisor instruction fetch in kernel mode
    Oops: Oops: 0010 [#1] SMP PTI
    RIP: 0010:0x0
    Call Trace:
     <IRQ>
     nvkm_chan_error+0x99/0xa0 [nouveau]
     nv04_fifo_recover+0x80/0x350 [nouveau]
     nv04_fifo_intr_cache_error+0x111/0x350 [nouveau]
     nv04_fifo_intr+0x222/0x250 [nouveau]
     nvkm_intr+0x13a/0x250 [nouveau]
     __handle_irq_event_percpu+0x54/0x220
     handle_irq_event+0x38/0x90
     handle_edge_irq+0xc5/0x190
     __common_interrupt+0x4c/0xd0
     common_interrupt+0x80/0xa0
     </IRQ>

Das war ein **eigener** Fehler in einem eigenen Patch (0006 rief
`nvkm_chan_error(chan, true)`, und `g84_chan` hat kein `.preempt`), inzwischen
behoben. Er gehoert in den Bericht nur als Erklaerung, wie die Oops entstand,
nicht als Mainline-Defekt.

## Der Bericht selbst (Oops 2): drm_panic ioremapt

Beim Zeichnen der Oops-Meldung:

    Call Trace:
     draw_panic_plane+0x9e/0x170
     nv50_wndw_get_scanout_buffer+0x9b/0x1b0 [nouveau]
     nouveau_bo_map+0x4b/0xa0 [nouveau]
     ttm_bo_kmap+0x2b2/0x310 [ttm]
     __ioremap_caller+0x235/0x340
    RIP: 0010:__get_vm_area_node+0x15a/0x160
    kernel BUG at mm/vmalloc.c:3212!
    Oops: invalid opcode: 0000 [#2] SMP PTI
    Kernel panic - not syncing: Fatal exception in interrupt

`mm/vmalloc.c:3212` ist in dieser Version buchstaeblich
`BUG_ON(in_interrupt());` als erste Anweisung von `__get_vm_area_node()`.

## Umstaende

    Kernel:     7.0.10-p1-gentoo-dist, PREEMPT(lazy)
    Hardware:   Apple Inc. Macmini3,1/Mac-F22C86C8, MCP79 / GeForce 9400M (NVAC)
    Tainted:    [S]=CPU_OUT_OF_SPEC, [D]=DIE, [O]=OOT_MODULE, [E]=UNSIGNED_MODULE
    Zeitpunkt:  2026-06-02 22:17:18, Uptime 39189 s
    Danach:     nv_tco-Hardware-Watchdog rebootete die Maschine nach etwa 30 s

Das `[O]`/`[E]` im Taint kommt daher, dass nouveau als Out-of-Tree-Modul mit
lokalen Patches lief. Der drm_panic-Pfad selbst ist davon unberuehrt, keiner
der lokalen Patches fasst `dispnv50/wndw.c`, `nouveau_bo.c` oder ttm an.
Das gehoert trotzdem in den Bericht, damit niemand daran haengenbleibt.

## Was dieser Beleg NICHT ist

Eine Reproduktionsanleitung. Es ist **eine** Beobachtung, auf einem inzwischen
alten Kernel, ausgeloest durch einen eigenen Fehler. Die Codeanalyse gegen
aktuellen Mainline traegt den Bericht, der Trace belegt nur, dass der Pfad in
der Praxis wirklich erreicht wird.
