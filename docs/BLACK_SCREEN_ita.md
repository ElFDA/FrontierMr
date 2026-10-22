# Un gioco mostra lo schermo nero: riprendere il MiSTer

Un gioco può non mostrare niente: una modalità video che lo schermo non
accetta, un core che aspetta un BIOS mancante, un gioco che si blocca. Il
MiSTer (Linux e Main, sul processore ARM) continua però a funzionare, quindi
si può riprendere senza toccare la SD. In ordine, dal più semplice:

## 1. La combinazione anti-panico: L+R+Select+Start

Tieni premuti **L + R + Select + Start per 2 secondi** sul pad: torna
Frontier. Funziona anche quando il gioco si è bloccato, perché la legge Main,
non il core. Una pressione breve resta al gioco (in molti giochi del SNES è il
reset). Sono i tasti del pad come mappati per il menu. `panic_combo=0` in
`frontier/frontier.ini` la disattiva.

## 2. Con una tastiera: Alt+F12

**Alt+F12** torna a Frontier, come dall'OSD. Se l'OSD non si vede (nessuna
immagine), usa la combinazione qui sopra.

## 3. Il Coin-Op fa ripartire il gioco a ogni accensione

Se la modalità Coin-Op è attiva ([COINOP_ita.md](COINOP_ita.md)) e l'ultimo
gioco è proprio quello che non si vede, il MiSTer sembra bloccato a ogni
accensione:

* **Spegni e riaccendi entro un minuto**: un avvio automatico conta solo se
  il gioco è rimasto acceso per 60 secondi (`coinop_safe`), quindi alla
  riaccensione successiva resti in Frontier (*Coin-Op: last start did not
  complete, skipped*).
* Oppure, con la SD su un PC: un file vuoto `frontier/coinop.off`, o
  `coinop=0` in `frontier/frontier.ini`.

## 4. Non risponde niente

Spegni e riaccendi il MiSTer. Con il Coin-Op attivo, vedi il punto 3.

Da un altro computer sulla stessa rete SSH funziona anche con lo schermo
nero: utente `root`, password `1` se non l'hai cambiata.

```sh
touch /media/fat/frontier/coinop.off   # Coin-Op spento
reboot
```

## 5. Non si vede Frontier

* **Solo CRT**, il menu mostra rumore: F12 (l'OSD si vede anche sul CRT) ->
  Scripts -> `frontier_crt`, oppure `direct_video=1` nella sezione `[Menu]`
  di `MiSTer.ini` (vedi il [README](../README.md#misterini)).
* In tutti gli altri casi: F12 -> Scripts -> `frontier_on_off` riporta il
  browser originale dei core; oppure, da un PC, un file vuoto
  `/media/fat/frontier.off`.

## Cause frequenti

| Cosa vedi | Di solito |
|---|---|
| La schermata di caricamento dei giochi perde il sincronismo | `vscale_mode` diverso da 0 o 1 in `[MiSTer]` di `MiSTer.ini` |
| Niente su un CRT a 15 kHz | `vga_scaler=1`: la VGA riceve l'uscita dello scaler (31 kHz o più) |
| Niente su una TV HDMI | `direct_video=1` in `[MiSTer]`: serve solo agli adattatori da HDMI a VGA |
| Solo un gioco o un core | le impostazioni di quel core o un BIOS mancante: provalo dal browser originale o dall'OSD del core |

Tieni una copia di `MiSTer.ini` prima di cambiarlo. Più file `MiSTer.ini`
(ad esempio `MiSTer.ini` e `MiSTer_TV.ini`) si scelgono dall'OSD.
