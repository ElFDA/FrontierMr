# Modalità Coin-Op

Come in un cabinato arcade: quando accendi il MiSTer riparte da solo l'ultimo
gioco avviato da Frontier.

## Attivarla

Frontier Settings -> **Coin-Op mode**, A: ON/OFF. Scrive `coinop=1` (o `0`)
in `/media/fat/frontier/frontier.ini`, che si può cambiare anche da un PC.

Il gioco che riparte è l'ultimo avviato **da Frontier**: arcade, console,
computer o portatile, anche da Favorites, Recent o My Lists. Una ROM caricata
dall'OSD dentro un core non conta.

## Quando parte

* A ogni **accensione** e a ogni **riavvio** (anche quello dopo update_all o
  dall'OSD).
* **Non** quando torni a Frontier da un gioco (Alt+F12 o la combinazione
  anti-panico): lì resti in Frontier.

## Un conto alla rovescia prima dell'avvio

Con `coinop_delay=N` in `frontier.ini`, per N secondi in basso compare
*Coin-Op: <gioco> - any button: menu*: un tasto qualsiasi annulla l'avvio
(*Coin-Op: cancelled*) e resti in Frontier. Con `coinop_delay=0`
(predefinito) il gioco parte subito.

Se `games/` sta su un disco USB che viene montato in ritardo, Frontier aspetta
il gioco fino a `games_wait` secondi (`games_wait=30`, ad esempio).

## Se il gioco non si vede o blocca il MiSTer

Il Coin-Op si protegge da solo (vedi anche [BLACK_SCREEN_ita.md](BLACK_SCREEN_ita.md)):

1. **Spegni e riaccendi entro un minuto.** Un avvio automatico conta solo se
   il gioco è rimasto acceso per `coinop_safe` secondi (60 di base);
   altrimenti alla riaccensione successiva non parte niente, Frontier mostra
   *Coin-Op: last start did not complete, skipped* e puoi scegliere un altro
   gioco.
2. **L+R+Select+Start tenuti premuti 2 secondi** sul pad: torni a Frontier.
3. Con il conto alla rovescia (`coinop_delay`), un tasto qualsiasi durante
   l'attesa.
4. Da un PC con la SD: `coinop=0` in `frontier/frontier.ini`, oppure un file
   vuoto `frontier/coinop.off` (il Coin-Op resta spento qualunque cosa dica
   `frontier.ini`, finché non cancelli il file).

## I file

| File | Cosa |
|---|---|
| `frontier/frontier.ini` | `coinop=`, `coinop_delay=`, `coinop_safe=`, `games_wait=` |
| `frontier/coinop_last.txt` | l'ultimo gioco: percorso, nome, file da aspettare |
| `frontier/coinop.pending` | c'è solo durante il primo minuto di un avvio automatico |
| `frontier/coinop.off` | se c'è, il Coin-Op è spento |
