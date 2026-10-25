# Scraper: dati, immagini e video dei giochi

Frontier mostra copertine, schermate, schermate del titolo, marquee, video e i
dati dei giochi (descrizione, anno, sviluppatore, editore, genere, giocatori).
Li scarica lo scraper, che si lancia da Frontier stesso:
**Frontier Settings -> Scraper**.

## 1. Un account ScreenScraper (consigliato)

[ScreenScraper](https://www.screenscraper.fr) ha dati, immagini e video di
tutti i sistemi. Serve un account gratuito:

1. Registrati su https://www.screenscraper.fr.
2. Collega una tastiera USB al MiSTer.
3. In Frontier: Frontier Settings -> Scraper -> **ScreenScraper user**,
   premi A, scrivi il nome utente, Invio. Poi **ScreenScraper password** allo
   stesso modo. Esc (o B) annulla; un valore vuoto lo cancella.

I due valori vengono salvati in `/media/fat/frontier/scraper/scraper.ini`
(oppure `/media/fat/frontier/scraper.ini`, se hai quello). Senza tastiera
scrivili lì da un PC, partendo da `scraper/scraper.ini.example`:

```ini
[screenscraper]
user = il_tuo_nome
password = la_tua_password
```

Lascia vuoti `devid` e `devpassword`: la chiave da sviluppatore di Frontier è
nel pacchetto.

## 2. Senza account

ScreenScraper viene saltato e si usano le altre fonti:

| | Arcade e Neo Geo | Console, computer, portatili |
|---|---|---|
| Fonte | ArcadeDB | libretro thumbnails |
| Dati (descrizione, genere...) | sì | no |
| Copertine, schermate, schermate del titolo | sì | sì, solo per i file con nome No-Intro esatto |
| Marquee, video | sì | no |

I dati dei sistemi (descrizione, produttore, anno, hardware) arrivano sempre
da Wikipedia. Senza i dati dei giochi delle console, i filtri di My Lists
(editore, genere, serie...) funzionano solo per gli arcade, e le console non
hanno video.

## 3. Cosa scaricare

Frontier Settings -> Scraper:

| Voce | Cosa fa |
|---|---|
| Start scraping | A avvia lo scraper in sottofondo; di nuovo A lo ferma. A destra l'avanzamento ("SNES 120/840 (2/5)", poi finished / stopped / error; "finished: 3 updated" = 3 giochi hanno avuto dati o immagini nuove, "finished: nothing new" = niente da aggiungere). Intanto puoi continuare a usare Frontier e giocare: lo scraper lavora sull'altro core del processore. |
| Get systems data only | solo i dati dei sistemi, da Wikipedia: pochi minuti, niente giochi |
| Systems | Arcade e le categorie; dentro una categoria "All" o un sistema alla volta, ON/OFF |
| Language | inglese (predefinito), italiano, francese, tedesco, spagnolo, portoghese, giapponese: descrizioni e generi (in inglese quando un testo manca in quella lingua) |
| Texts | nomi, descrizioni, generi, editori... ON/OFF |
| Box art, Screenshots, Title screens, Marquees and logos, Fanart, Videos | ciascuno ON/OFF; all'inizio tutti ON tranne Fanart |
| Games already scraped | salta (solo quello che manca, predefinito), di nuovo i testi (dati nella lingua scelta, immagini tenute), di nuovo tutto, retry not found (anche i giochi che nessuna fonte aveva negli ultimi 30 giorni) |

Le scelte restano in `frontier.ini`. Fermare è sicuro: quello che è stato
scaricato resta e il giro successivo riprende da lì. Gli errori di
ScreenScraper (la quota giornaliera, la rete) vengono riprovati al giro
successivo.

**Giochi non trovati.** Quando nessuna fonte ha un gioco, o non tutto quello
che hai chiesto (per esempio nessuna copertina da nessuna parte), lo scraper
se lo ricorda e lo salta per 30 giorni: il contatore mostra solo i giochi
davvero da fare, e hack, bootleg e homebrew non vengono richiesti a ogni giro.
Si ritentano dopo 30 giorni, quando chiedi altre immagini o aggiungi una fonte
(per esempio il tuo account ScreenScraper), oppure subito con "Games already
scraped" -> retry not found.

**Alternative dell'arcade.** I giochi di `_Arcade/_alternatives` prendono i
dati e le immagini del loro gioco principale (la `.mra` fuori da
`_alternatives` dello stesso set MAME: "Street Fighter II (USA 910522)" da
"Street Fighter II (World 910522)") e tengono il loro nome. Per loro non si
scarica né si copia niente; solo un'alternativa senza gioco principale viene
scaricata per conto suo.

**Versioni di un core.** Lo stesso vale per le `.mra` fuori da `_alternatives`
che sono versioni di un solo gioco, come le regioni di un core
(`_Decoryah/_HeavyUnit`: World, Japan, US...): usano lo stesso set MAME (il
setname di una è setname, parent o zip dell'altra, oppure hanno lo stesso
parent) e hanno un titolo simile ("Jackal", "Tokushu Butai Jackal"). Se ne
scarica una, le altre prendono i suoi dati e le sue immagini tenendo il loro
nome. Non si uniscono gli zip dei BIOS condivisi da molti giochi né i cloni con
un altro titolo (Space Invaders / Balloon Bomber, Pac-Man / Ms. Pac-Man). Sul
MiSTer di prova 443 giochi su 2784 non si chiedono più.

**Copie di passate vecchie.** Le versioni scaricate una per una prima hanno file
propri, molti identici a quelli del gioco principale. `python3 fe_scrape.py
--dedupe-media --dry-run` (da PC o ssh) dice quanto spazio occupano; senza
`--dry-run` le versioni usano i file del principale (prima si riscrive il
gamelist) e le copie identiche si cancellano. Le immagini diverse restano.
Niente rete, circa dieci minuti sul MiSTer. Sul MiSTer di prova: 7067 file,
8,2 GB. Poi premi F5 in Frontier.

Le immagini nuove di un sistema compaiono quando quel sistema è finito; per
vederle subito su un sistema già aperto tieni premuto X su di esso (o F5).

**Un gioco solo.** Apri i dettagli di un gioco (X) e scegli **Scrape this
game**, sotto "Add to list...": lo scraper richiede quel gioco alle fonti e
riscarica i suoi dati e le sue immagini, con il contenuto scelto in Frontier
Settings -> Scraper (si aggiornano anche le alternative arcade che prendono da
lui). Lavora in sottofondo, circa un minuto; le immagini nuove compaiono quando
ha finito. Utile per un gioco con un'immagine sbagliata o mancante.

## 4. Da quale regione arrivano le immagini

Ogni titolo viene cercato una volta, con la versione che parte dalla lista
(vedi [VERSIONS_ita.md](VERSIONS_ita.md)), e i suoi dati e immagini valgono
per tutte le versioni del titolo. Nomi e immagini si prendono in questo
ordine di regioni:

1. le regioni di quel file, ad esempio `(USA, Europe)`;
2. l'ordine di `regions=` in `frontier.ini` (predefinito USA, World, Europe,
   Japan);
3. poi quella di ScreenScraper, Europa, World, USA, Giappone.

Solo per le **copertine** può venire prima un'altra regione, ad esempio le
copertine giapponesi, in `scraper/scraper.ini`:

```ini
[scraper]
box_regions = jp
```

(più di una: `box_regions = jp,us`). Poi "Games already scraped" -> all
again, per i sistemi che vuoi.

## 5. Spazio e tempo

Le immagini occupano qualche centinaio di KB per gioco; i **video** qualche MB
ciascuno (uno scraping completo delle console con i video può richiedere
decine di GB e molto tempo: si può fermare e riprendere). I fanart sono
grandi e all'inizio sono spenti.

Tutto va in `/media/fat/frontier`:

| Cartella | Cosa |
|---|---|
| `gamelists/<sistema>/gamelist.xml` | i dati dei giochi (formato EmulationStation) |
| `media/<sistema>/<tipo>/` | immagini e video (`box`, `snap`, `title`, `marquee`, `fanart`, `video`) |
| `.scrape_cache/` | le risposte delle fonti, così un giro nuovo non chiede di nuovo; i giochi non trovati (`notfound_<sistema>.tsv`) e quello che lo scraper ha letto delle `.mra` (`mra_info.tsv`) |
| `.cache/scrape.log` | l'output dell'ultimo giro |

## 6. Da un terminale

Lo stesso scraper si lancia anche da SSH, con più opzioni (`--help`):

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --arcade
python3 /media/fat/frontier/scraper/fe_scrape.py --system NES --system SNES --video
python3 /media/fat/frontier/scraper/fe_scrape.py --all-systems --lang it
python3 /media/fat/frontier/scraper/fe_scrape.py --arcade --game "Bomb Jack"
```

Da un PC con la SD montata: aggiungi `--root /percorso/della/sd`.
L'elenco completo delle opzioni è nella guida, `frontier/LEGGIMI_ita.txt`
(sezione SCRAPER).
