# kismaros-foglaltsag

Börzsönyligeti konkurens szállások foglaltságának napi mérése, 60 éjszakára előre.

## Mit csinál

A `Napi foglaltságmérés` workflow minden nap 03:17 UTC-kor lefut (kézzel is indítható:
Actions → Napi foglaltságmérés → Run workflow). Minden bekötött szállásnál lekéri a
foglalási naptárat, és egy napi pillanatképet ment:

- `adatok/napi/ÉÉÉÉ-HH-NN.csv` – `meres_nap;szallas_id;szallas;ej;allapot;nyers`
  - `ej`: az az éjszaka, amely azon a napon kezdődik
  - `allapot`: `foglalt` / `szabad` / `zarva` (a naptár lezártként jelöli) / `reszben`
    (több egységnél: van foglalt, de nem mind) / `ismeretlen`
  - `nyers`: a naptár eredeti jelölése (ellenőrzéshez)
- `adatok/naplo/ÉÉÉÉ-HH-NN.json` – a futás összesítője (szállásonként ok / hiba)

A napi pillanatképekből később kiszámolható a kihasználtság, és az is, hogy egy-egy
éjszaka hány nappal előre telt be.

## Felépítés

- `szallasok.csv` – a szállások, foglalómotorjuk és paraméterük
  (`nem_merheto` = csak űrlapos foglalás, nincs naptár)
- `futtat.py` – a mérés (csak Python standard könyvtár, nincs függőség);
  kapcsolók: `--napok 60`, `--csak 1,2,3`, `--kimenet mappa`
- `meres/` – foglalómotoronkénti adapterek
  - `resnweb.py` – RESnWEB / nethotelbooking.net (get_events)
  - `wpbc.py` – WP Booking Calendar (új: WPBC_AJX_CALENDAR_LOAD; régi: inline tömbök)
  - `wpbs.py` – WP Booking System (wpbs_refresh_calendar, jelmagyarázat alapján)
  - `appartman.py` – foglalas.appartman.hu (rooms + reservations)
  - `previo.py` – Previo (get-seasons)
  - `mphb.py` – MotoPress Hotel Booking (v6 REST, v5 ajax, v3/4 inline adat)
  - `egyedi.py` – egyedi naptárak: A Ház / A Hely (XML), CozyStay (Lombkabin),
    Vadlesen, Mesebeli (2 ház), Pinpoint / DOPBSP (Tölgy kabin)
- `teszt/` – egyszeri elérhetőségi teszt (2026. 11. 26.)

## Lefedettség

36 bejegyzés, a konkurencia-tábla 42 sorából 39-et fed le (a Maroska 3 háza és a
Mesebeli 2 háza egy-egy bejegyzés). Nem mérhető: Csuszka és Maja (csak űrlapos
foglalás).

## Korlátok

- A foglalt nap nem mindig valódi foglalás: lehet a tulajdonos zárolása is. A napi
  adatokból ez részben kiszűrhető (ha egy éj röviddel előtte telik be, az foglalás).
- A Maroska RESnWEB-naptára a 3 házra együtt szól: `foglalt` = mindhárom ház foglalt,
  `reszben` = legalább egy foglalt. A Mesebeli 2 házánál ugyanígy.
- Vadlesen: a lista foglalásonként az érkezéstől a távozás napjáig sorolja a napokat
  (min. 2 éj = 3 dátum). A blokk utolsó napja távozás, annak éjszakája `szabad`
  („távozás napja” a `nyers` oszlopban). A rendszer miatt erre a napra új vendég sem
  érkezhet, így ezek az éjek gyakorlatilag eladhatatlanok.
- A Ház / A Hely: kézzel vezetett XML-naptár; 2026 szeptembere óta alig van benne
  bejegyzés, 2027-re egy sem – lehet valódi visszaesés, de az is, hogy nem vezetik.
  A vendégneveket és e-mail-címeket a mérés nem tárolja, csak a dátumokat.
- Lombkabin (CozyStay): a naptár szinte minden napot tiltottnak mutat; ezt az élő
  oldallal ellenőriztük (2026. 11. 26.), egyezik.

Kihagyva a mérésből: Redibo erdei vendégház (a GitHub szerveréről 403-mal tilt; Attila döntése, 2026. 11. 26.).
