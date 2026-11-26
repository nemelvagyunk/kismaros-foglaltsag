"""Previo (booking.previo.app) naptár.

A foglalási oldal (index/step-1/?hotId=...) munkamenetet nyit, majd az /index/get-seasons/
végpont a kért napokra visszaadja, hogy az éj foglalható-e (available).
"""
import datetime as dt
import json

from .kozos import FOGLALT, ISMERETLEN, SZABAD, Munkamenet

ALAP = "https://booking.previo.app"


def mer(hot_id, kezdo, napok):
    kezdo_url = f"{ALAP}/index/step-1/?hotId={hot_id}&currency=HUF&lang=hu"
    s = Munkamenet(referer=kezdo_url)
    s.get(kezdo_url)
    adat = {}
    napok_lista = [kezdo + dt.timedelta(days=i) for i in range(napok)]
    for i in range(0, len(napok_lista), 31):
        resz = napok_lista[i:i + 31]
        parok = [("daysToBeLoaded[]", d.isoformat()) for d in resz] + [("hotId", str(hot_id))]
        valasz = json.loads(s.post(f"{ALAP}/index/get-seasons/", parok, referer=kezdo_url))
        adat.update(valasz.get("seasons") or {})
    eredmeny = []
    for nap in napok_lista:
        d = adat.get(nap.isoformat())
        if d is None or "available" not in d:
            eredmeny.append((nap, ISMERETLEN, "nincs adat"))
            continue
        a = SZABAD if d["available"] else FOGLALT
        nyers = f"available={d['available']} minStay={d.get('minStay')} arrivals={d.get('arrivals')}"
        eredmeny.append((nap, a, nyers))
    return eredmeny
