# v5, vorbereitet 22.08.2026, NICHT GESENDET

Antwort auf den Sashiko-Befund zur v4 (chan->fence plain veroeffentlicht,
Acquire auf ready deckt das kzalloc-Nullen nicht).

Loesung b: die Marke wandert aus dem Fence-Kontext in den Kanal, als
Zeiger `chan->fence_armed`, den NUR nouveau_fence_context_arm() schreibt
(release) und NUR nouveau_channel_kill() liest (acquire). Das bool ready
entfaellt. Kein Backend beruehrt. 42 Zeilen in vier Dateien.

Verschraenkungsbeweis identisch zur v4 (Struktur unveraendert, nur die
Marke ist ein Zeiger). Ein Schreiber, ein Leser, kein Plain-Store
dazwischen.

Branch: v5-respin in ~/linux-nouveau-patches, auf 1/3 der v4 aufgesetzt,
3/3 per cherry-pick unveraendert.

Warten auf Lyudes Review der v4. Moeglich ist auch, dass sie a) (Release
in den Backends, eigener Patch) oder "Nachtrag" bevorzugt. Dann faellt
diese v5 anders aus.

## Stand 22.08. vormittags

Fertig gebaut: checkpatch --strict 0/0/0 auf allen dreien, W=1 ohne
Warnung. Gegenueber dem ersten Wurf ergaenzt: `chan->fence_armed = NULL`
im Abbau (nach nvif_event_dtor(&chan->kill), vor context_del), damit kein
Zeiger auf den freigegebenen Kontext stehen bleibt.

Was zum Senden noch fehlt: Cover (Changes since v4, Bot-Verweis), und
Lyudes Review der v4. Erst dann entscheidet sich, ob diese v5, eine
andere Form, oder ein Nachtrag.

Und: die Antwort an den Bot (nv04-fifo-v4/ANTWORT-BOT-ENTWURF.txt) kann
dann "v5 is prepared" statt "I will take one" sagen.
