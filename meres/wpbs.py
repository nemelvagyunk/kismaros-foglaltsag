"""WP Booking System (wpbs) naptár.

Az oldalon lévő .wpbs-container data-* attribútumaival az admin-ajax.php-ról
(action=wpbs_refresh_calendar) havonta lekérhető a naptár HTML-je. Minden nap egy
wpbs-legend-item-<id> osztályt kap; az id jelentését a jelmagyarázat neve adja meg,
a ki- és bejelentkezési (changeover) id-ket a konténer attribútumai.
"""
import datetime as dt
import re
import unicodedata

from .kozos import FOGLALT, ISMERETLEN, SZABAD, ZARVA, Munkamenet, honapok

KONTENER = re.compile(r"<div[^>]*class=\"wpbs-container[^\"]*\"([^>]*)>")
NAP = re.compile(r"<div class=\"wpbs-date ([^\"]*)\"([^>]*)>")
JELMAGYARAZAT = re.compile(r"wpbs-legend-item-icon-(\d+)\"[^>]*>.*?wpbs-legend-item-name\"?>([^<]+)<", re.S)


def _ekezet_nelkul(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _jelentes(nev):
    n = _ekezet_nelkul(nev)
    if any(k in n for k in ("nem foglalhato", "nem elerheto", "zarva", "lezarva", "closed", "unavailable")):
        return ZARVA
    if any(k in n for k in ("foglalt", "booked", "lefoglal", "foglalas alatt", "fugg", "pending", "erkezes", "arrival", "check-in")):
        return FOGLALT
    if any(k in n for k in ("tavozas", "departure", "check-out")):
        return SZABAD
    if any(k in n for k in ("elerheto", "szabad", "available", "foglalhato")):
        return SZABAD
    return ISMERETLEN


def mer(url, kezdo, napok):
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    attr = None
    for k in KONTENER.findall(oldal):
        a = dict(re.findall(r"data-([a-z_]+)=\"([^\"]*)\"", k))
        if a.get("id"):
            attr = a
            break
    if not attr:
        raise RuntimeError("nem található WP Booking System naptár az oldalon")
    i = oldal.find("class=\"wpbs-legend\"")
    jelek = {k: v.strip() for k, v in JELMAGYARAZAT.findall(oldal[i:] if i >= 0 else oldal)}
    jelentes = {k: _jelentes(v) for k, v in jelek.items()}
    if attr.get("changeover_start"):
        jelentes[attr["changeover_start"]] = FOGLALT
    if attr.get("changeover_end"):
        jelentes[attr["changeover_end"]] = SZABAD
    alap = re.match(r"(https?://[^/]+)", url).group(1).replace("http://", "https://")
    nyers = {}
    for y, m in honapok(kezdo, napok):
        adat = dict(attr)
        adat.update({"action": "wpbs_refresh_calendar", "current_month": str(m),
                     "current_year": str(y), "months_to_show": "1"})
        html = s.post(alap + "/wp-admin/admin-ajax.php", adat, referer=url)
        for cls, a in NAP.findall(html):
            if "wpbs-gap" in cls:
                continue
            d = dict(re.findall(r"data-([a-z]+)=\"([^\"]*)\"", a))
            try:
                nap = dt.date(int(d["year"]), int(d["month"]), int(d["day"]))
            except (KeyError, ValueError):
                continue
            nyers[nap] = re.findall(r"wpbs-legend-item-(\d+)", cls)
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        ids = nyers.get(nap)
        if not ids:
            eredmeny.append((nap, ISMERETLEN, "nincs adat"))
            continue
        # osztott napnál (két jel) az éjre a második (délutáni) fél számít
        a = jelentes.get(ids[-1], ISMERETLEN)
        nevek = "+".join(f"{x}:{jelek.get(x, '?')}" for x in ids)
        eredmeny.append((nap, a, nevek))
    return eredmeny
