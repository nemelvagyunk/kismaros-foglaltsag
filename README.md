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

- `szallasok.csv` – a szállások, foglalómotorjuk és paraméterük (`motor`: resnweb, wpbc,
  wpbs; `kesobb` = még nincs bekötve)
- `futtat.py` – a mérés (csak Python standard könyvtár, nincs függőség)
- `meres/` – foglalómotoronkénti adapterek
  - `resnweb.py` – RESnWEB / nethotelbooking.net (get_events)
  - `wpbc.py` – WP Booking Calendar (új: WPBC_AJX_CALENDAR_LOAD; régi: inline tömbök)
  - `wpbs.py` – WP Booking System (wpbs_refresh_calendar)
- `teszt/` – egyszeri elérhetőségi teszt (2026. 11. 26.)

## Korlátok

- A foglalt nap nem mindig valódi foglalás: lehet a tulajdonos zárolása is. A napi
  adatokból ez részben kiszűrhető (ha egy éj röviddel előtte telik be, az foglalás).
- A Maroska RESnWEB-naptára a 3 házra együtt szól: `foglalt` = mindhárom ház foglalt,
  `reszben` = legalább egy foglalt.

Kihagyva a mérésből: Redibo erdei vendégház (a GitHub szerveréről 403-mal tilt; Attila döntése, 2026. 11. 26.).
