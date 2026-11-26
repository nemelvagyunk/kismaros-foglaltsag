# kismaros-foglaltsag

Börzsönyligeti konkurens szállások foglaltságának napi mérése, 60 éjszakára előre,
a mérés napját követő éjtől (az aznapi éjt kihagyjuk, mert az aznapi foglalást van,
ahol engedik, van, ahol nem).

## Mit csinál

A `Napi foglaltságmérés` workflow minden nap 03:17 UTC-kor lefut (kézzel is indítható:
Actions → Napi foglaltságmérés → Run workflow). Tesztként van egy tartalék indítás is
06:47 UTC-kor: ez csak akkor mér, ha a fő mérés aznap kimaradt (a GitHub ütemezett
indításai néha késnek vagy elmaradnak). Minden indítás egy sort ír az
`adatok/inditasok.csv`-be (nap, típus: fo / tartalek / kezi, indulás UTC, mit csinált). Minden bekötött szállásnál lekéri a
foglalási naptárat, és egy napi pillanatképet ment:

- `adatok/napi/ÉÉÉÉ-HH-NN.csv` – `meres_nap;szallas_id;szallas;ej;allapot;nyers`
  - `ej`: az az éjszaka, amely azon a napon kezdődik (első: a mérés másnapja)
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
  - `egyedi.py` – egyedi naptárak: CozyStay (Lombkabin), Vadlesen, Mesebeli (házanként:
    param = accommodationId), Pinpoint / DOPBSP (Tölgy kabin); az `ahazxml` adapter
    megmaradt, de nincs használatban
- `teszt/` – egyszeri elérhetőségi teszt (2026. 11. 26.)

## Lefedettség

34 bejegyzés, a konkurencia-tábla 42 sorából 34-et fed le. Nem mérhető: Csuszka és Maja (csak űrlapos
foglalás).

## Korlátok

- A foglalt nap nem mindig valódi foglalás: lehet a tulajdonos zárolása is. A napi
  adatokból ez részben kiszűrhető (ha egy éj röviddel előtte telik be, az foglalás).
- Vadlesen: a lista foglalásonként az érkezéstől a távozás napjáig sorolja a napokat
  (min. 2 éj = 3 dátum). A blokk utolsó napja távozás, annak éjszakája `szabad`
  („távozás napja” a `nyers` oszlopban). Távozás 15:00-ig, érkezés 12:00-tól, ezért
  távozási napra nem fogadnak új vendéget; ezek az éjek gyakorlatilag eladhatatlanok.
- Lombkabin (CozyStay): a naptár szinte minden napot tiltottnak mutat; ezt az élő
  oldallal ellenőriztük (2026. 11. 26.), egyezik.

Kihagyva a mérésből (Attila döntései, 2026. 11. 26.):
- Redibo erdei vendégház: a GitHub szerveréről 403-mal tilt.
- Maroska (3 ház): a közös naptárból nem derül ki, melyik ház foglalt, így a foglaltsága
  nem összevethető. Az első napi mérésben (2026-11-26.csv) még benne van.
- A Ház és A Hely: kézzel vezetett XML-naptár, 2026 szeptembere óta alig van benne
  bejegyzés, 2027-re egy sem – nyilvánvalóan nem vezetik, a foglaltságuk nem mérhető.
  Az első napi mérésben még benne vannak.

A Mesebeli 2 háza 2026. 11. 27-től két külön bejegyzés (16, 17); az első napi mérésben
még összevonva szerepelnek 16-os azonosítóval (`nyers`: ház1 / ház2).
