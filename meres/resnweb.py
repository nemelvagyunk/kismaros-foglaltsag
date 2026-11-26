"""RESnWEB (nethotelbooking.net) naptár.

A szálláshely oldala (nethotelbooking.net/hotels/<slug>/) munkamenet-azonosítót (sid) és
szállodaazonosítót ad; a naptár havonta a /ajax/booking/index végpontról, a get_events
metódussal tölti a napokat. A "closed" listában lévő nap = az az éj nem foglalható.
Több egységes helynél (pl. Maroska) a naptár a hely egészére szól: "closed" = minden egység
foglalt; ha a nap szerepel a listán, de korlátozás nélkül, akkor van foglalt egység, de nem mind.
"""
import datetime as dt
import re
import time

from .kozos import FOGLALT, RESZBEN, SZABAD, Munkamenet, honapok

ALAP = "https://nethotelbooking.net"


def mer(slug, kezdo, napok, egysegek=1):
    # A szerver néha átmenetileg üres választ ad (2026. 11. 26. este: HTTP 202, 0 bájt),
    # ezért ha nincs meg a sid, kicsit később újrapróbáljuk, új munkamenettel.
    for kiserlet in range(3):
        if kiserlet:
            time.sleep(20 * kiserlet)
        s = Munkamenet()
        oldal = s.get(f"{ALAP}/hotels/{slug}/")
        sid = re.search(r"location\.hash\s*=\s*'([A-Z0-9]{20,})'", oldal)
        hid = re.search(r"images\.resnweb\.net/(\d+)/", oldal)
        if sid and hid:
            break
    else:
        raise RuntimeError(f"nem található sid vagy szállodaazonosító az oldalon "
                           f"(3 próbálkozás, utolsó válasz {len(oldal)} bájt)")
    sid, hid = sid.group(1), hid.group(1)
    nyers = {}
    for y, m in honapok(kezdo, napok):
        adat = {"sid": sid, "method[name]": "get_events", "method[params][hotelID]": hid,
                "method[params][lang]": "hu", "method[params][year]": str(y),
                "method[params][month]": f"{m:02d}"}
        j = s.post_json(f"{ALAP}/ajax/booking/index", adat, referer=f"{ALAP}/hotels/{slug}/")
        blokk = j.get("0") or {}
        for e in blokk.get("closed") or []:
            try:
                nap = dt.date(y, m, int(e["date"]))
            except (ValueError, KeyError):
                continue
            nyers[nap] = "+".join(e.get("restrictions") or []) or "jelolt"
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        r = nyers.get(nap)
        if r is None:
            allapot = SZABAD
        elif "closed" in r.split("+"):
            allapot = FOGLALT
        else:
            allapot = RESZBEN if egysegek > 1 else SZABAD
        eredmeny.append((nap, allapot, r or ""))
    return eredmeny
