# PGRAPH-Hänger nach CCACHE-VM-Fault, ohne jede Erholung

**Datum:** 2026-08-13, Kernel 7.1.8-gentoo-dist-bin, gentoo-neo (MCP79/NVAC)
**Symptom:** Oberfläche hängt, Sitzung seit 22 h auf, EVO frei (kein Wedge)

## Kette

| Zeit | Ereignis |
|---|---|
| 10:36:19 | `Loading firmware: nouveau/nvac_fuc084` |
| 10:36:25 | `gr: TRAP_CCACHE 00000001 [FAULT]`, ch 5 `chrome[1174869]`, subc 3, class 8397, mthd 0f04 |
| 10:36:25 | `fb: trapped read at 00201b0000 ... client 05 [CCACHE] subclient 00 [CB] reason 2 [PAGE_NOT_PRESENT]` |
| 10:37:55 | `failed to idle channel 5` (erstes Symptom, +90 s) |
| 10:37:57 | `WARNING nvkm/engine/fifo/g84.c:132 g84_ectx_bind` timeout |
| 10:37:58 | Firmware erneut geladen, hilft nicht |
| bis 10:40:35 | 10x `failed to idle`, 6x `g84_ectx_bind`-Timeout über vier Chrome-PIDs |

## Zustand danach (stabil über Minuten gemessen)

```
PGRAPH_STATUS        00000503     unverändert über 4 s
PGRAPH_TRAPPED_ADDR  80030f04     Bit31 = Trap noch eingerastet, mthd 0f04 subc 3
PGRAPH_CTXCTL_STAT   30004001
PGRAPH_INTR          00000000     kein anstehender Interrupt
PFIFO_INTR           00000000     kein anstehender Interrupt
PFIFO_CACHE1_GET     00000000     steht
PFIFO_CACHE1_PUT     00000244     Arbeit liegt an, wird nicht geholt
PFIFO_CACHE1_CHID    ffffffff
PTIMER_LOW           läuft        GPU-Takt lebt, die Engine nicht
EVO core/base1       2d0b001b / 0c05001b   kein Bit31, also KEIN EVO-Park
```

Folgeschaden: `labwc` in `nouveau_gem_ioctl_cpu_prep` -> `dma_fence_default_wait`,
13 `kworker/uN+ttm` in D-State. Beide warten auf Fences des toten Kanals.

## Der Punkt

Der Fault wird **gemeldet und dann fallengelassen**. Kein `nvkm_chan_error()`,
kein Kanal-Kill, kein Fence-Signal. Auf Tesla gibt es keinen Erholungspfad, also
bleibt PGRAPH stehen, bis die Maschine neu startet.

## Verhältnis zur Patchserie, nüchtern

Das ist **nicht** der Fall, den der zurückgestellte Tesla-Recovery-Patch abfängt.
Der hängt sich an `cache_error` und `dma_pusher` in `nv04_fifo_intr`. Hier kommt
der Fehler aus **PGRAPH** (TRAP_CCACHE / VM-Fault), einer anderen Quelle. Der
Patch hätte diesen Hänger nicht gefangen.

Was der Fall sehr wohl belegt, erstmals mit Messwerten von echter Hardware:

1. Ein fataler Kanalfehler auf Tesla führt zu **dauerhaftem** Stillstand der
   Engine. Nichts im Treiber holt die GPU zurück.
2. Die Fences des betroffenen Kanals signalisieren **nie**. Genau die Annahme,
   auf der 4/4 der gesendeten Serie argumentiert (Dead-Letter = Vertragsbruch
   gegenüber dma-fence), ist damit am lebenden Objekt bestätigt: hier gab es
   gar keinen Abnehmer, und die Folge ist exakt die vorhergesagte.
3. Für die v4-Überarbeitung heißt das: der Erholungspfad darf nicht nur die
   FIFO-Quellen abdecken, sondern muss die PGRAPH-Traps mitnehmen.

## Offen

- Warum PAGE_NOT_PRESENT auf 00201b0000? Chrome-GPU-Prozess, class 8397.
  Chrome läuft auf dieser Maschine bewusst wieder mit GPU-Beschleunigung, die
  frühere Gegenmaßnahme `--disable-gpu` ist absichtlich nicht mehr gesetzt
  (Entscheidung vom 13.08.2026). Der Hänger wird dafür in Kauf genommen, also
  ist mit weiteren Vorfällen dieser Art zu rechnen. Umso wichtiger ist ein
  Erholungspfad, der PGRAPH-Traps abdeckt.
- Ob ein PMC_ENABLE-Toggle auf das PGRAPH-Bit die Engine zurückholt, ist nicht
  probiert worden (Treiberzustand wüsste nichts davon).
