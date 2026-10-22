# Quale versione di un gioco parte

Nei sistemi (Computer, Console, Handheld, Other) Frontier mostra **una voce
per titolo**: "Altered Beast" una volta sola, anche quando la cartella ha i
file USA, Europa e Giappone, revisioni e prototipi. A ne avvia uno, la
**versione predefinita**; le altre sono nei dettagli.

## La versione predefinita

Frontier legge i nomi dei file in stile [No-Intro](https://no-intro.org), ad
esempio `Altered Beast (USA, Europe) (Rev 1).md`, e sceglie in questo ordine:

1. **Uscite prima delle non uscite**: beta, prototipi, sample e demo vengono
   dopo le versioni uscite, anche di un'altra regione.
2. **La regione preferita**: la prima di `regions=` in
   `/media/fat/frontier/frontier.ini` che il file ha. Predefinito:
   `regions=USA,World,Europe,Japan`. Un file con più regioni,
   `(USA, Europe)`, vale come la migliore delle due; le regioni che non sono
   nella lista vengono dopo tutte quelle che ci sono.
3. **Originali prima delle riedizioni**: Virtual Console, Switch Online,
   console mini, raccolte, Evercade... vengono dopo.
4. **L'ultima revisione**: `(Rev 2)` prima di `(Rev 1)` prima di nessuna;
   `(v1.1)` prima di `(v1.0)`.
5. Una versione senza `(Alt)` prima di un dump alternativo.

Ad esempio, con `regions=` predefinito:

| File nella cartella | Parte |
|---|---|
| `Sonic (Japan)`, `Sonic (USA, Europe)` | `Sonic (USA, Europe)` |
| `Game (USA) (Beta)`, `Game (Japan)` | `Game (Japan)`: l'uscita prima della beta |
| `Game (USA)`, `Game (USA) (Rev 1)` | `Game (USA) (Rev 1)` |
| `Game (Europe)`, `Game (USA) (Virtual Console)` | `Game (Europe)`: prima l'originale |

## Un'altra regione per prima

Cambia l'ordine in `frontier.ini`, ad esempio l'Europa per prima:

```ini
regions=Europe,World,USA,Japan
```

oppure prima le versioni giapponesi: `regions=Japan,World,USA,Europe`. Si può
usare qualsiasi regione dei nomi No-Intro (France, Germany, Italy, Spain,
Korea, Brazil, Asia...). Poi premi F5 in Frontier (o riavvialo).

Lo stesso ordine dice anche allo scraper da quale regione prendere nomi e
immagini (vedi [SCRAPER_ita.md](SCRAPER_ita.md)).

## Le altre versioni

Su un gioco premi **X**: i dettagli elencano tutte le sue versioni (regioni,
revisioni, prototipi) e anche gli altri titoli dello stesso gioco, ad esempio
*Thunder Force IV* e *Lightening Force*, collegati dalle liste di MAME. A su
una versione avvia quella.

Per collegare i titoli diversi dello stesso gioco, una volta per sistema, da
SSH:

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --groups --system MegaDrive
```

poi F5.

Favorites e Recent tengono il titolo: anche loro avviano la versione
predefinita.

## File che non sono nella lista per titolo

Hack, traduzioni, copie pirata, file con altro testo dopo i tag e raccolte
senza nomi No-Intro sono solo in **Folders**, in cima alla lista del sistema,
dove le cartelle vere di `games/` si vedono come sono (uno zip si apre come
una cartella). Le cartelle chiamate `Extra` (giochi senza licenza, prototipi,
hack...) vengono saltate dalla lista e dallo scraper; altri nomi si
aggiungono con `exclude_dirs=` in `frontier.ini`.

## Arcade e Neo Geo

* **Arcade**: ogni `.mra` di `_Arcade` è una voce, come nel browser
  originale; le versioni in `_Arcade/_alternatives` sono nei dettagli (X).
* **Neo Geo**: i romset si usano come fa il core (file `.neo` con il setname,
  gli zip di `games/NEOGEO/romsets.xml`); lo stesso titolo è una voce sola,
  parte il `.neo`, gli altri sono nei dettagli.
