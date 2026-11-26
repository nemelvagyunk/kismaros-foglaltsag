"""MotoPress Hotel Booking (mphb) naptár – három változat.

- 6.x: REST API, GET {restApiUrl}/availability?start_date&end_date&room_type_ids[0]=<id>
- 5.x: admin-ajax, action=mphb_get_room_type_calendar_data (nonce a MPHB._data.nonces-ben)
- 3.x–4.x: a foglalt éjek az oldalba ágyazva: MPHB._data.roomTypesData[<id>].dates.booked
Az új változatoknál naponként roomTypeStatus: available / booked / not-available ...
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

from .kozos import FOGLALT, ISMERETLEN, RESZBEN, SZABAD, ZARVA, Munkamenet


def _mphb_adat(oldal):
    m = re.search(r"var MPHB\s*=\s*\{", oldal)
    if not m:
        return None
    j, _ = json.JSONDecoder().raw_decode(oldal[m.end() - 1:])
    return j.get("_data") or {}


def _statusz(allapotok):
    if not allapotok:
        return ISMERETLEN
    if all(a == "booked" for a in allapotok):
        return FOGLALT
    if all(a == "available" for a in allapotok):
        return SZABAD
    if any(a == "booked" for a in allapotok) and any(a == "available" for a in allapotok):
        return RESZBEN
    if any(a in ("blocked", "not-available", "unavailable") for a in allapotok):
        return ZARVA
    return ISMERETLEN


def _napi_statuszbol(adat_rt, ids, kezdo, napok):
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        allapotok, szabad_db = [], 0
        for rt in ids:
            d = (adat_rt.get(str(rt)) or {}).get(nap.isoformat())
            if d:
                allapotok.append(d.get("roomTypeStatus") or "")
                szabad_db += int(d.get("availableRoomsCount") or 0)
        eredmeny.append((nap, _statusz(allapotok), f"{'+'.join(allapotok)} szabad:{szabad_db}" if allapotok else "nincs adat"))
    return eredmeny


def mer(url, kezdo, napok, room_type=None):
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    d = _mphb_adat(oldal)
    if d is None:
        raise RuntimeError("nem található MotoPress (MPHB) adat az oldalon")
    vege = kezdo + dt.timedelta(days=napok)
    ids = [str(room_type)] if room_type else sorted(set(re.findall(r"data-room-type-id=\"(\d+)\"", oldal)))
    if not ids and d.get("roomTypeId"):
        ids = [str(d["roomTypeId"])]
    if not ids and d.get("roomTypesData"):
        ids = list(d["roomTypesData"].keys())

    # 6.x – REST
    if d.get("restApiUrl"):
        api = d["restApiUrl"].rstrip("/")
        hd = {"Accept": "application/json", "Referer": url}
        if d.get("restApiWpNonce"):
            hd["X-WP-Nonce"] = d["restApiWpNonce"]
        if not ids:
            t = json.loads(s._nyit(urllib.request.Request(api + "/accommodation_types?per_page=100", headers=hd), 60))
            ids = [str(x["id"]) for x in (t.get("data") if isinstance(t, dict) else t)]
        q = urllib.parse.urlencode([("start_date", kezdo.isoformat()), ("end_date", vege.isoformat())]
                                   + [(f"room_type_ids[{i}]", x) for i, x in enumerate(ids)])
        adat = json.loads(s._nyit(urllib.request.Request(api + "/availability?" + q, headers=hd), 60))
        return _napi_statuszbol(adat, ids, kezdo, napok)

    # 5.x – admin-ajax
    nonce = (d.get("nonces") or {}).get("mphb_get_room_type_calendar_data")
    if nonce and ids:
        adat_rt = {}
        for rt in ids:
            q = urllib.parse.urlencode({
                "action": "mphb_get_room_type_calendar_data", "mphb_nonce": nonce, "mphb_is_admin": "false",
                "mphb_locale": (d.get("settings") or {}).get("currentLanguage") or "hu",
                "start_date": kezdo.isoformat(), "end_date": vege.isoformat(), "room_type_id": rt,
                "is_show_prices": "false", "is_truncate_prices": "false", "is_show_prices_currency": "false"})
            j = json.loads(s.get(d["ajaxUrl"] + "?" + q))
            adat_rt[rt] = j.get("data") or {}
        return _napi_statuszbol(adat_rt, ids, kezdo, napok)

    # 3.x–4.x – beágyazott roomTypesData
    rtd = d.get("roomTypesData") or {}
    if rtd:
        eredmeny = []
        for i in range(napok):
            nap = kezdo + dt.timedelta(days=i)
            k = nap.isoformat()
            foglalt = osszes = 0
            zarva = False
            for rt in (ids or list(rtd.keys())):
                v = rtd.get(str(rt)) or {}
                osszes += int(v.get("activeRoomsCount") or 1)
                datumok = v.get("dates") or {}
                foglalt += int((datumok.get("booked") or {}).get(k, 0) or 0)
                bl = datumok.get("blocked") or {}
                if (isinstance(bl, dict) and k in bl) or (isinstance(bl, list) and k in bl):
                    zarva = True
            if foglalt >= osszes:
                a = FOGLALT
            elif foglalt > 0:
                a = RESZBEN
            elif zarva:
                a = ZARVA
            else:
                a = SZABAD
            eredmeny.append((nap, a, f"booked {foglalt}/{osszes}" + (" blocked" if zarva else "")))
        return eredmeny
    raise RuntimeError("ismeretlen MotoPress-változat")
