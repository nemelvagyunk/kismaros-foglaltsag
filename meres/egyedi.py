"""Egyedi (szállásonként eltérő) naptárak.

- ahazxml:  A Ház / A Hely – a naptár egy XML-fájlból (foglalasok/foglalasok.xml) rajzol.
            Az XML vendégneveket is tartalmaz: ezekből SEMMIT nem mentünk, csak a dátumokat.
- cozystay: CozyStay (WooCommerce) – a napi ár- és foglaltsági lista (priceList) az oldalba ágyazva.
- vadlesen: a /foglaltsag oldal reservedDates / temporaryReservedDates JS-tömbje. A lista a
            távozás napját is tartalmazza, ezért egy összefüggő szakasz utolsó napja nem foglalt éj.
- mesebeli: az oldalba ágyazott unavailableRanges (checkIn–checkOut) házanként (accommodationId).
- dopbsp:   Pinpoint Booking System – admin-ajax, action=dopbsp_calendar_schedule_get, évenként.
"""
import datetime as dt
import json
import re

from .kozos import FOGLALT, ISMERETLEN, RESZBEN, SZABAD, ZARVA, Munkamenet


def _napok(kezdo, napok):
    return [kezdo + dt.timedelta(days=i) for i in range(napok)]


def ahazxml(xml_url, kezdo, napok):
    s = Munkamenet()
    t = s.get(xml_url)
    foglalt = set()
    for blokk in re.findall(r"<erkezesev>.*?<statusz>[^<]*</statusz>", t, re.S):
        try:
            g = lambda n: int(re.search(rf"<{n}>(\d+)</{n}>", blokk).group(1))
            k = dt.date(g("erkezesev"), g("erkezesho"), g("erkezesnap"))
            v = dt.date(g("tavozasev"), g("tavozasho"), g("tavozasnap"))
        except (AttributeError, ValueError):
            continue
        d = k
        while d < v:
            foglalt.add(d)
            d += dt.timedelta(days=1)
    # egyetlen fájl minden évre: ami nincs benne, azt az oldal szabadnak mutatja
    return [(nap, FOGLALT, "xml") if nap in foglalt else (nap, SZABAD, "") for nap in _napok(kezdo, napok)]


def cozystay(url, kezdo, napok):
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    m = re.search(r"\"priceList\"\s*:\s*\{", oldal)
    if not m:
        raise RuntimeError("nem található priceList az oldalon")
    lista, _ = json.JSONDecoder().raw_decode(oldal[m.end() - 1:])
    napi = {}
    for v in lista.values():
        try:
            napi[dt.date.fromisoformat(v["start"])] = v
        except (KeyError, ValueError):
            continue
    eredmeny = []
    for nap in _napok(kezdo, napok):
        v = napi.get(nap)
        if not v:
            eredmeny.append((nap, ISMERETLEN, "nincs adat"))
            continue
        st, orig = v.get("status"), v.get("original_status")
        ossz, szabad = int(v.get("number") or 1), int(v.get("available_number") or 0)
        if st == "available" and szabad >= ossz:
            a = SZABAD
        elif st == "available" and szabad > 0:
            a = RESZBEN
        elif orig == "unavailable":
            a = ZARVA
        else:
            a = FOGLALT
        eredmeny.append((nap, a, f"{st}/{orig} szabad:{szabad}/{ossz}"))
    return eredmeny


def vadlesen(url, kezdo, napok):
    # A lista foglalásonként sorolja fel a napokat az érkezéstől a TÁVOZÁS
    # napjáig (min. 2 éj = 3 dátum; nincs 2 dátumos blokk). A blokkokat a
    # tömb sorrendje adja: a következő elem nem a előző+1 nap → új foglalás.
    # Minden blokk utolsó napja távozás, annak az éjszakája nem foglalt.
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    ejek, tavozas, talalt = set(), set(), False
    for nev, cimke in (("reservedDates", "lista"), ("temporaryReservedDates", "ideiglenes")):
        m = re.search(nev + r"\s*=\s*(\[[^\]]*\])", oldal)
        if not m:
            continue
        talalt = True
        datumok = []
        for x in json.loads(m.group(1)):
            try:
                datumok.append(dt.date.fromisoformat(x))
            except ValueError:
                pass
        blokk = []
        for d in datumok + [None]:
            if blokk and (d is None or d != blokk[-1] + dt.timedelta(days=1)):
                ejek.update((n, cimke) for n in blokk[:-1])
                tavozas.add(blokk[-1])
                blokk = []
            if d is not None:
                blokk.append(d)
    if not talalt:
        raise RuntimeError("nem található reservedDates az oldalon")
    ej_cimke = {}
    for n, c in ejek:
        ej_cimke.setdefault(n, c)
    eredmeny = []
    for nap in _napok(kezdo, napok):
        if nap in ej_cimke:
            eredmeny.append((nap, FOGLALT, ej_cimke[nap]))
        elif nap in tavozas:
            eredmeny.append((nap, SZABAD, "távozás napja"))
        else:
            eredmeny.append((nap, SZABAD, ""))
    return eredmeny


def mesebeli(url, kezdo, napok, haz=None):
    """haz: accommodationId (1 = Gálhegyi út 71., 2 = Harangvirág u. 13.); None = összevont."""
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    m = re.search(r"\"unavailableRanges\"\s*:\s*\[", oldal)
    if not m:
        raise RuntimeError("nem található unavailableRanges az oldalon")
    tartomanyok, _ = json.JSONDecoder().raw_decode(oldal[m.end() - 1:])
    hazak = sorted({str(t.get("accommodationId")) for t in tartomanyok}) or ["1"]
    for a in re.findall(r"\"accommodationId\"\s*:\s*(\d+)", oldal) + re.findall(r"data-accommodation-card=\"(\d+)\"", oldal):
        if a not in hazak:
            hazak.append(a)
    if haz is not None:
        haz = str(haz)
        if haz not in hazak:
            raise RuntimeError(f"nincs {haz}. ház az oldalon (talált: {', '.join(hazak)})")
    foglalt = {h: set() for h in hazak}
    for t in tartomanyok:
        try:
            k = dt.date.fromisoformat(t["checkIn"])
            v = dt.date.fromisoformat(t["checkOut"])
        except (KeyError, ValueError):
            continue
        d = k
        while d < v:
            foglalt.setdefault(str(t.get("accommodationId")), set()).add(d)
            d += dt.timedelta(days=1)
    if haz is not None:
        return [(nap, FOGLALT, f"ház{haz}") if nap in foglalt.get(haz, ()) else (nap, SZABAD, "")
                for nap in _napok(kezdo, napok)]
    eredmeny = []
    for nap in _napok(kezdo, napok):
        db = sum(1 for h in hazak if nap in foglalt.get(h, ()))
        a = FOGLALT if db == len(hazak) else (RESZBEN if db else SZABAD)
        nyers = " ".join(f"ház{h}:{'F' if nap in foglalt.get(h, ()) else 'S'}" for h in hazak)
        eredmeny.append((nap, a, nyers))
    return eredmeny


def dopbsp(url, kezdo, napok, naptar_id="1"):
    s = Munkamenet(referer=url)
    alap = re.match(r"(https?://[^/]+)", url).group(1)
    napi = {}
    for ev in sorted({d.year for d in _napok(kezdo, napok)}):
        t = s.post(alap + "/wp-admin/admin-ajax.php",
                   {"action": "dopbsp_calendar_schedule_get", "dopbsp_frontend_ajax_request": "true",
                    "id": str(naptar_id), "year": str(ev)}, referer=url)
        j = json.loads(t) if t.strip().startswith("{") else {}
        for k, v in j.items():
            try:
                napi[dt.date.fromisoformat(k)] = json.loads(v) if isinstance(v, str) else v
            except (ValueError, TypeError):
                continue
    eredmeny = []
    for nap in _napok(kezdo, napok):
        v = napi.get(nap)
        if v is None:
            eredmeny.append((nap, SZABAD, "alapértelmezett"))
            continue
        st = v.get("status") or ""
        if st == "booked":
            a = FOGLALT
        elif st == "unavailable":
            a = ZARVA
        elif st in ("available", "special", "none", ""):
            a = SZABAD if int(v.get("available") or 0) > 0 or st != "none" else ZARVA
        else:
            a = ISMERETLEN
        eredmeny.append((nap, a, f"{st} avail:{v.get('available')}"))
    return eredmeny
