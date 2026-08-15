# Empfängerliste für den drm_panic-Bericht

Aus `get_maintainer.pl` für **beide** betroffenen Dateien, danach jede Adresse
einzeln auf Aktualität geprüft (Stand 15.08.2026, gegen `c21bb4193868`).

```
To:  Jocelyn Falempe <jfalempe@redhat.com>
     Javier Martinez Canillas <javierm@redhat.com>
     Lyude Paul <lyude@redhat.com>
     Danilo Krummrich <dakr@kernel.org>
Cc:  nouveau@lists.freedesktop.org
     dri-devel@lists.freedesktop.org
     Maarten Lankhorst <maarten.lankhorst@linux.intel.com>
     Maxime Ripard <mripard@kernel.org>
     Thomas Zimmermann <tzimmermann@suse.de>
     David Airlie <airlied@gmail.com>
     Simona Vetter <simona@ffwll.ch>
     linux-kernel@vger.kernel.org
```

## Begründungen

- **Falempe und Martinez Canillas** sind die DRM-PANIC-Maintainer
  (MAINTAINERS, Abschnitt "DRM PANIC", `S: Supported`). Falempe ist zusätzlich
  die Autorin von `1d26c846f3ff`, also des betroffenen nouveau-Codes selbst.
  Beide Adressen aktiv (Commits 02/2026 und 05/2026).
- **Lyude Paul und Danilo Krummrich** sind die nouveau-Maintainer, beide aktiv.
  Lyude hat `1d26c846f3ff` seinerzeit reviewt.
- Der Rest ist die drm-misc-Runde plus die Listen, wie `get_maintainer` sie
  ausgibt.

## Adressprüfung, weil das schon zweimal schiefging

Beim nouveau-Versand am 13.08. gab es einen Bounce von `bskeggs@nvidia.com`,
und bei forcedeth wären zwei tote Adressen aus alten Sign-offs mitgegangen.
Deshalb diesmal jede Adresse gegen die Historie geprüft:

| Adresse | Autor zuletzt | Committer zuletzt | in Trailern (letzte 800) |
|---|---|---|---|
| jfalempe@redhat.com | 2026-02-12 | 2026-02-17 | 0 |
| javierm@redhat.com | 2026-05-23 | 2026-05-26 | 0 |
| lyude@redhat.com | 2026-05-07 | 2026-06-02 | 0 |
| dakr@kernel.org | 2026-05-29 | 2026-06-21 | 0 |
| maarten.lankhorst@linux.intel.com | 2025-06-06 | 2024-11-04 | **3** |
| airlied@gmail.com | 2024-04-08 | 2015-12-05 | **1** |
| simona@ffwll.ch | nie | nie | **1** |

**Wichtig, und eine Korrektur meiner ersten Einschätzung:** die drei unteren
Adressen sehen in der Autor- und Committer-Spalte tot aus, erscheinen aber in
Trailern laufender Commits. Sie werden also angeschrieben und empfangen. Sie
bleiben in der Liste. Aus "committet nicht mehr unter dieser Adresse" folgt
nicht "nimmt keine Post an", das ist genau die Verwechslung, die beim
Skeggs-Bounce in die andere Richtung passiert ist.

Nebenbefund ohne Handlungsbedarf: Lankhorst committet inzwischen als
`dev@lankhorst.se` (zuletzt 2026-07-27), MAINTAINERS nennt weiterhin die
Intel-Adresse, und die kommt in den Trailern häufiger vor. Deshalb bleibt es
bei der Fassung aus `get_maintainer.pl`.

## Form

**Prosa-Bericht, kein Patch.** Nicht aus Prozessdogma, sondern weil die
fertigen panik-sicheren Helfer (`ttm_bo_kmap_try_from_panic()`,
`drm_scanout_buffer.pages`) den iomem-Fall ausdrücklich nicht abdecken, und
genau der liegt hier vor. Welcher der beiden möglichen Wege richtig ist, ist
eine Maintainer-Entscheidung, nicht unsere.
