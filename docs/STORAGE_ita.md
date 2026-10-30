# Giochi su più dischi e condivisioni di rete

I giochi di un sistema possono stare su più supporti: la PlayStation sulla SD e altri giochi
PlayStation su un secondo disco USB, un NAS, una condivisione CIFS... Frontier li legge tutti
e mostra **un solo elenco per sistema** (`merge_games=1` in `frontier.ini`, di base).

## Dove cerca

In quest'ordine; per lo stesso file in due posti vale il primo:

| Posto | Cos'è |
|---|---|
| `/media/fat/games` | la SD, oppure il disco a cui è collegata |
| `/media/usb0/games` ... `/media/usb7/games` e `/media/usb0` ... `/media/usb7` | i dischi USB: le cartelle dei sistemi in una cartella `games`, oppure direttamente sul disco (`/media/usb0/SNES`, come le legge anche il browser del MiSTer) |
| `/media/network/games` e `/media/network` | condivisioni di rete |
| `/media/fat/cifs/games` e `/media/fat/cifs` | condivisioni CIFS montate dallo script `cifs_mount.sh` (le sue condivisioni possono contenere direttamente le cartelle dei sistemi: `Amiga`, `C64`, `NES`...) |
| `/media/fat` | la vecchia disposizione con le cartelle dei sistemi direttamente sulla SD (`/media/fat/SNES`) |

Un disco a cui `games` è già collegata non si legge due volte. In ogni posto la cartella del
sistema è quella di sempre (`games/PSX`, `games/SNES`...); maiuscole e minuscole non contano
(`PSX` e `psx` sono la stessa). Anche un sistema trovato solo su un secondo disco compare.

## Cosa si unisce

* I giochi di un sistema stanno in un solo elenco (per titolo, oppure la vista a cartelle).
* Una cartella con lo stesso nome su due dischi mostra i file di tutte e due: con `games/PSX`
  sul primo disco USB e `games/PSX/Xenogears` sul secondo, l'elenco PlayStation ha tutti i
  giochi e `Xenogears` è un gioco solo che avvia il disco 1 (vedi
  [Quale versione di un gioco parte](VERSIONS_ita.md), *Giochi su più dischi*).
* Preferiti, Recent e My Lists ricordano un gioco col suo percorso dentro `games/` e lo ritrovano
  su qualunque disco sia.
* Lo scraper (`fe_scrape.py`) legge gli stessi posti.

## Da sapere

* Il browser dei file del MiSTer dentro un core **non** unisce: usa il primo posto che ha la
  cartella (dischi USB, poi la rete, poi la SD).
* Il disco o la condivisione devono esserci quando l'elenco viene letto. Dopo aver collegato un
  disco o montato una condivisione, rileggere gli elenchi: **X** tenuto su una categoria o su
  un sistema (vedi *AGGIORNARE GLI ELENCHI* in `LEGGIMI_ita.txt`).
* Una condivisione di rete lenta o spenta rallenta gli elenchi: smontarla (`cifs_umount.sh`)
  oppure `merge_games=0`, che legge solo `/media/fat/games`.
* **Storage: USB** nell'OSD del MiSTer (System Settings) fa del primo disco USB la radice:
  `/media/usb0` prende il posto di `/media/fat` nella tabella sopra e la SD si legge per ultima
  (`/media/fat/games`, poi `/media/fat`). La cartella di Frontier resta sulla SD
  (`/media/fat/frontier`, dove la mette l'installazione), a meno che il disco USB non abbia una
  sua cartella `frontier`.
