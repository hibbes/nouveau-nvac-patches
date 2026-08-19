# Rueckmeldungen vom 18./19.08.2026, ausgewertet

Zehn neue Fremdmails seit dem 16.08., von vier Personen. Quelle: lore
(`t.mbox.gz`) plus Posteingang, entdoppelt ueber Message-ID.

## Kurzfassung

| Serie | Ergebnis |
|---|---|
| **forcedeth 1/2 und 2/2** | **2x Reviewed-by je Patch**, nichts zu tun |
| **Spur 1 v4, 1/2 (MSI rearm)** | **Reviewed-by: Lyude Paul**, "will push in a moment" |
| **Spur 1 v4, 2/2 (NULL-Guard)** | **abgelehnt** als Pflaster, Lyude schrieb selbst eine Sechserserie |
| **teardown 1/3-3/3** | Durchsicht fuer "morgen" zugesagt (18.08.), noch nicht da |
| **drm_panic-Bericht** | bestaetigt, aber bewusst kein Fix; **Angebot: Patches werden gereviewt und getestet** |

## forcedeth (netdev): beide Patches durch

- **Simon Horman** (netdev-Reviewer), 19.08. 09:55: `Reviewed-by:` auf 1/2 und 2/2.
- **Zhu Yanjun** (Autor grosser Teile von forcedeth), 19.08.: "Thanks a lot."
  plus `Reviewed-by:` auf beide.

Zwei unabhaengige Reviewed-by je Patch, keine Einwaende, keine Nachfrage zum
allyesconfig-Punkt aus dem Cover. Warten auf Aufnahme durch netdev.

## Spur 1 v4, Patch 1/2: angenommen

`Reviewed-by: Lyude Paul <lyude@redhat.com>`, ohne jede Anmerkung.
Im Cover-Reply: "First patch looks fine ... Will push the first patch in just
a moment."

## Spur 1 v4, Patch 2/2: abgelehnt, aber der Befund traegt

Lyude, 18.08. 16:44, sieben Anmerkungen im Patch:

1. "This isn't correct" (zur Praemisse des Commit-Texts)
2. "In the future you should probably put a backtrace if you've seen this in
   the wild" (Verfahrenshinweis, gilt fuer kuenftige Einreichungen)
3. "It's actually an outdated variable from the pre-atomic days"
4. "We don't set nv_encoder->crtc at the boot-time hardware state readback"
   **-> spaeter selbst zurueckgezogen: "...this was wrong, oops!" (18:32).**
   Der Kommentar im Patch war an dieser Stelle also richtig.
5. **"this is way too verbose"** (zum Kommentarblock)
6. "this isn't the bug, the bug is that we're reading nv_encoder->crtc at all
   here"
7. "This doesn't need changing either if we just fix where the encoder came
   from" (zur `&nv_connector->aux`-Umstellung)

**Wichtig fuer die Einordnung:** der Fehler wurde nicht bestritten, nur die
Reparatur. Lyudes eigener Fix in 3/6 behaelt `WARN` plus `return` bei, holt
die CRTC aber aus dem Atomic-State statt aus dem Schattenzeiger:

    nv_crtc = nv50_outp_get_old_crtc(state, nv_encoder);
    if (drm_WARN_ON(state->dev, !nv_crtc))
            return;
    head = nv50_head(&nv_crtc->base);

Die gewaehlte Form war also brauchbar, falsch war die Quelle des Zeigers.

## Lyudes Sechserserie "Obliterate nouveau_encoder->crtc"

v1 am 18.08. 23:48, **v2 am 19.08. 15:43** (base `0e118b936dc5`).
Marek steht in To und Cc.

- 1/6 DPCD-Backlight-Disable in eigene Funktion
- 2/6 `nv50_outp_get_old_crtc()` neu
- 3/6 **`Reported-by: Marek Czernohous`, `Cc: stable # v5.12+`**, behebt den
  gemeldeten Fehler in `nv50_sor_atomic_disable()`
- 4/6 **`Reported-by: Marek Czernohous`**, dasselbe in
  `nv50_disp_atomic_commit_core()`
- 5/6 `nouveau_encoder->audio.crtc`
- 6/6 Variable ganz entfernt

Cover: "this patch series does fix an actual bug (patches 1-3)".

Lyude hat sein eigenes 4/6 am 19.08. 00:10 korrigiert ("whether we need to use
the new or old state depends on if we're enabling or disabling"), daher die v2.

**Der Fehler geht mit Nennung in die Kernel-Historie, und `stable # v5.12+`
reicht deutlich weiter zurueck als selbst angenommen.**

## drm_panic: Jocelyn Falempe, 19.08. 11:12

Bestaetigt den Bericht in der Sache:

> "Yes the nouveau drm panic implementation is not perfect. The framebuffer is
> not accessible from the CPU, so the only way to display something is to
> ioremap it, and currently that is not possible safely in a panic context."

Aber ausdruecklich kein Fix geplant:

> "I still think that it works well enough, and that it's still better than a
> frozen display."

Richtung fuer eine Loesung, und ein offenes Angebot:

> "I think it would be nice to have something similar to kmap_local_page() for
> iomem."
> "**I will review and help with testing any patch that can improve the
> current situation.**"

## teardown-Serie

Lyude, 18.08. 19:58, zum Cover:

> "Thank you for all of the submissions! JFYI - I should be able to get to
> reviewing this one tomorrow"

Stand 19.08. abends: noch keine Durchsicht im Faden. Der Bot-Befund vom 15.08.
und die v2 von 1/3 liegen unwidersprochen.

## Was daraus folgt

1. **Nichts ist dringend.** Kein Patch wartet auf eine Korrektur.
2. **Naheliegende Gelegenheit:** Lyudes v2 3/6 behebt einen Fehler, der auf
   *dieser* Maschine auftritt (MCP79, Wayland-Sitzungswechsel). Ein
   `Tested-by:` von hier waere fuer die Serie wertvoll und ist mit dem
   vorhandenen Aufbau leicht zu erbringen.
3. Jocelyns Angebot ist eine offene Tuer fuer einen drm_panic-Patch, aber die
   Richtung (iomem-Variante von `kmap_local_page()`) ist Kernarbeit, nicht
   nouveau-lokal.
4. Verfahrenslehre fuer kuenftige Einreichungen: **bei einem beobachteten
   Absturz gehoert der Backtrace in den Commit-Text.**
