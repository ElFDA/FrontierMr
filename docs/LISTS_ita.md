# Favorites, Recent e My Lists

La prima schermata di Frontier ha tre liste di giochi che mescolano tutti i
sistemi, ogni gioco con il suo sistema a destra.

| Lista | Cos'è | Come si riempie |
|---|---|---|
| **Favorites** | i tuoi giochi preferiti | X tenuto premuto un secondo su un gioco (o F sulla tastiera); di nuovo per toglierlo |
| **Recent** | gli ultimi giochi avviati, dal più recente | da sola, ogni volta che parte un gioco |
| **My Lists** | liste fatte da te, quante ne vuoi | a mano oppure da un filtro sui dati dei giochi |

## Favorites

Su qualsiasi gioco (in un sistema, in Arcade, in My Lists...) tieni premuto
**X** per un secondo: compare una stella e il gioco è nei preferiti. Rifallo
per toglierlo; funziona anche nei dettagli. X premuto e rilasciato subito apre
i dettagli.

In Favorites c'è un'unica lista con tutti i preferiti e, sopra, una cartella
per ogni sistema con solo i suoi. Sono salvati in
`/media/fat/frontier/favorites.txt`.

## Recent

Gli ultimi giochi avviati da Frontier, dal più recente. Quanti:
Frontier Settings -> **Recent games** (OFF, 10 ... 200, 50 all'inizio).
Salvati in `/media/fat/frontier/recent.txt`: cancellalo per svuotare la lista.

## My Lists

### Una lista a mano

1. Su un gioco premi **X** per i dettagli.
2. Scendi fino ad **Add to list...** (sotto le versioni) e premi A: compaiono
   le tue liste, con "in list" accanto a quelle che hanno già il gioco.
3. A su una lista aggiunge il gioco (o lo toglie, se c'è già). A su
   **+ New list** crea una lista nuova con il gioco ("List 1", "List 2"...).
   B torna indietro.

Per togliere un gioco apri i suoi dettagli dall'interno della lista e premi A
su **Remove from this list**.

### Una lista da un filtro

In My Lists, **+ New list from filter...** mostra una riga per ogni dato dei
giochi, con a destra quello che è scelto:

| Riga | Valori |
|---|---|
| System | Arcade, Mega Drive, SNES... |
| Core | le schede arcade: CPS1, CPS2, Neo Geo MVS, Sega System 16B... |
| Publisher | Capcom, Konami, Sega... |
| Developer | chi ha fatto il gioco (arcade: il produttore) |
| Genre | Shoot'em up, Platform, Fighting, Beat'em up, Run and gun, RPG, Sports... |
| Subgenre | Shoot'em up / Vertical, Sports / Soccer... |
| Decade, Year | 1980s, 1990s... / 1991... |
| Series | Street Fighter, Castlevania, Thunder Force... |
| Players | 1 player ... 5+ players (quanti insieme) |

A su una riga mostra i suoi valori con il numero di giochi; A spunta o toglie
la spunta a un valore, **Any** le toglie tutte, B torna indietro. Più valori
nella stessa riga = uno qualsiasi; più righe = tutte insieme. Ad esempio i
platform di Capcom e Konami sul SNES:

```
System = SNES
Publisher = Capcom + Konami
Genre = Platform
```

Poi, in fondo alle righe:

| Voce | Cosa fa |
|---|---|
| Show the N games | i giochi del filtro, per avviarli o aprirne i dettagli |
| Create a list with the N games... | una lista nuova: **Name it "..."** usa un nome fatto dal filtro ("SNES - Capcom, Konami - Platform"), **Type a name on the keyboard...** un nome tuo (tastiera USB; Invio crea, Esc o B annullano) |
| Add the N games to a list... | li aggiunge a una delle tue liste (i giochi già presenti restano una volta sola): filtri diversi possono finire nella stessa lista |
| Clear the filter | riparte da zero |

Una lista creata da un filtro è una lista come le altre: si aggiungono o
tolgono giochi a mano come sopra.

**I filtri hanno bisogno dei dati dei giochi**, che arrivano dallo scraper
([SCRAPER_ita.md](SCRAPER_ita.md), con Texts ON). I giochi arcade hanno sempre
almeno core, produttore e anno (dal loro `.mra`); i giochi delle console
hanno dati solo dopo lo scraping con un account ScreenScraper.

### Rinominare o cancellare una lista

In fondo a ogni lista:

* **Rename this list (keyboard)**: scrivi il nome nuovo su una tastiera USB
  (Invio salva; Esc o B annullano).
* **Delete this list**: A la cancella; una lista con dei giochi chiede A una
  seconda volta.

### Il file

Le liste sono in `/media/fat/frontier/mylists.ini`: una sezione per lista,
il nome tra parentesi quadre, poi una riga per gioco (percorso, un tab, il
nome mostrato). Si può modificare da un PC; poi F5 in Frontier.

```ini
[Shoot'em ups]
@sys/MegaDrive/Thunder Force IV	Thunder Force IV
_Arcade/1943 The Battle of Midway (Euro).mra	1943 The Battle of Midway (Euro)
```
