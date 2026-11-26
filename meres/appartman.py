"""Appartman (foglalas.appartman.hu) naptár.

Nyilvános JSON-végpontok: /x/hotels/<slug>/rooms (egységek száma) és
/x/hotels/<slug>/reservations (foglalások: startAt, endAt, roomAllocation).
Egy éj (D) foglalt egység-száma: a D-t lefedő foglalások (startAt <= D < endAt) mennyisége.
"""
import datetime as dt
import json

from .kozos import FOGLALT, RESZBEN, SZABAD, Munkamenet

ALAP = "https://foglalas.appartman.hu/x/hotels/"


def mer(slug, kezdo, napok):
    s = Munkamenet(referer="https://foglalas.appartman.hu/")
    szobak = json.loads(s.get(ALAP + slug + "/rooms"))
    egysegek = sum(int(r.get("quantity") or 1) for r in szobak) or 1
    foglalasok = json.loads(s.get(ALAP + slug + "/reservations"))
    foglalt_db = {}
    azonositok = {}
    for f in foglalasok:
        try:
            k = dt.date.fromisoformat(f["startAt"][:10])
            v = dt.date.fromisoformat(f["endAt"][:10])
        except (KeyError, ValueError):
            continue
        db = sum(int(a.get("quantity") or 1) for a in (f.get("roomAllocation") or [])) or 1
        nap = k
        while nap < v:
            foglalt_db[nap] = foglalt_db.get(nap, 0) + db
            azonositok.setdefault(nap, []).append(str(f.get("id")))
            nap += dt.timedelta(days=1)
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        db = foglalt_db.get(nap, 0)
        if db == 0:
            a = SZABAD
        elif db >= egysegek:
            a = FOGLALT
        else:
            a = RESZBEN
        nyers = f"{db}/{egysegek} foglalás:{','.join(azonositok.get(nap, []))}" if db else ""
        eredmeny.append((nap, a, nyers))
    return eredmeny
