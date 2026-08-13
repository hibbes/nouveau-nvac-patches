# Aufwach-Wedge 13.08.2026 12:40, erstmals instrumentiert

Erster Mitschnitt eines Aufwach-Wedges mit aktivem `nouveau.debug=disp=debug`.
Der Wedge war echt, der S3-Wächter hat ihn geheilt (rtcwake, dt=42.3s).

## Ablauf

| Zeit | Ereignis |
|---|---|
| 12:35:32 | DPMS aus, soft-dpms blank-suppression eingerastet |
| 12:40:36 | Wächter: WEDGE, core=8f0e001b base1=8e07001b (beide Bit31), streak=3 |
| 12:40:55 | Aufwachversuch: SV1.0, SV2.0, SV2.2. **SV3 kommt nie.** |
| 12:40:57 | `core notifier timeout`, sv-rescue, pending bleibt 00000020 |
| 12:41:00-10 | 5x `base-1: timeout` |
| 12:41:09 | Wächter löst S3 aus |
| 12:41:19 | zurück, Supervisor läuft vollständig bis SV3.0, geheilt |

## Der harte Befund: Fetch-Park, kein Methodenfehler

```
core_put=000001fc core_get=0000019c      GET klebt hinter PUT
base1_put=000003c4 base1_get=000002c4    dito
intr0=00000000                           keine EVO-Ausnahme eingerastet
supervisor=00000150 pending=00000020     steht in SV2
core_err_m=00000080 core_err_d=00000200
```

Über 0,7 s in 100-ms-Abständen unverändert. Der Kanal hört auf zu holen, ohne
dass Hardware oder Treiber einen Fehler melden.

## WIDERLEGTE Hypothese, hier festgehalten damit sie nicht wiederkehrt

Beim Nebeneinanderlegen der verkeilten (12:40:55) und der gesunden Kette
(12:41:19) fiel auf, dass links die Phase **2.1** (Pixeltakt, "2.1 - 148500
khz") fehlt. Naheliegender Schluss: fehlendes 2.1 verhindert SV3.

**Falsch.** Auszählung über 52 Supervisor-Sequenzen aus den Kernel-Logs:

| 2.1 da | 3.0 erreicht | Wedge | n |
|---|---|---|---|
| nein | ja | nein | 29 |
| nein | nein | nein | 14 |
| nein | nein | ja | 5 |
| ja | ja | nein | 3 |
| ja | nein | ja | 1 |

29 Sequenzen ohne 2.1 erreichten 3.0 problemlos, und eine **mit** 2.1 verkeilte
trotzdem. 2.1 ist also weder notwendig noch hinreichend.

Belastbar bleibt nur: **alle 6 Wedges erreichen 3.0 nicht.** Notwendige, keine
hinreichende Bedingung, denn 14 Sequenzen ohne 3.0 liefen ohne Wedge.

Methodenhinweis: die Auszählung stammt aus einem groben Parser über
`/var/log/kernel/*`; die 14 Fälle "kein 3.0, kein Wedge" können teilweise
abgeschnittene Sequenzen sein. Vor weiteren Schlüssen den Parser härten.

## Rohdaten

`state.txt`, `supervisor-trace.txt`, `wedge-20260813T124036-watchdog.txt`,
`kernlog-snapshot.txt` in diesem Verzeichnis.
