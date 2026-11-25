"""WP Booking Calendar (wpbc) naptár.

Újabb változat (9.9+): a naptár az admin-ajax.php-ról tölt (action=WPBC_AJX_CALENDAR_LOAD),
a nonce és a paraméterek az oldal HTML-jében vannak. Naponként summary.status_for_day:
  full_day_booking, change_over, check_in -> az éj foglalt
  available, check_out                    -> az éj szabad
  resource_availability / season_filter   -> lezárva
Régebbi változat: a foglalt napok JavaScript-tömbökben (date_approved_par, date2approve)
vannak az oldalban; az utolsó szám 0 = egész nap, 1 = érkezés (éj foglalt), 2 = távozás.
"""
import datetime as dt
import json
import re
from collections import defaultdict

from .kozos import FOGLALT, ISMERETLEN, SZABAD, ZARVA, Munkamenet

UJ_FOGLALT = {"full_day_booking", "change_over", "check_in"}
UJ_SZABAD = {"available", "check_out"}
UJ_ZARVA = {"resource_availability", "season_filter", "unavailable", "weekdays_unavailable"}

REGI = re.compile(
    r"(date_approved_par|date_approved|date2approve)(?:\[\s*\d+\s*\])?\s*\[\s*'(\d{1,2})-(\d{1,2})-(\d{4})'\s*\]"
    r"\s*\[[^=;]*?\.length\s*\]\s*=\s*\[\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)\s*\]")


def _uj(s, url, oldal, kezdo, napok):
    nonce = re.search(r"set_secure_param\(\s*['\"]nonce['\"]\s*,\s*['\"]([0-9a-f]+)['\"]", oldal)
    user = re.search(r"set_secure_param\(\s*['\"]user_id['\"]\s*,\s*['\"](\d+)['\"]", oldal)
    loc = re.search(r"set_secure_param\(\s*['\"]locale['\"]\s*,\s*['\"]([A-Za-z_]+)['\"]", oldal)
    param = re.search(r"wpbc_calendar__load_data__ajx\(\s*(\{.*?\})\s*\)", oldal)
    if not nonce or not param:
        return None
    p = json.loads(param.group(1))
    adat = {"action": "WPBC_AJX_CALENDAR_LOAD", "wpbc_ajx_user_id": user.group(1) if user else "0",
            "nonce": nonce.group(1), "wpbc_ajx_locale": loc.group(1) if loc else "hu_HU"}
    for k, v in p.items():
        adat[f"calendar_request_params[{k}]"] = v
    alap = re.match(r"(https?://[^/]+)", url).group(1)
    j = s.post_json(alap + "/wp-admin/admin-ajax.php", adat, referer=url)
    napok_adat = (j.get("ajx_data") or {}).get("dates") or {}
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        d = napok_adat.get(nap.isoformat())
        if d is None:
            eredmeny.append((nap, ISMERETLEN, "nincs adat"))
            continue
        st = (d.get("summary") or {}).get("status_for_day") or ""
        if st in UJ_FOGLALT:
            a = FOGLALT
        elif st in UJ_SZABAD:
            a = SZABAD
        elif st in UJ_ZARVA:
            a = ZARVA
        else:
            a = ISMERETLEN
        eredmeny.append((nap, a, st))
    return eredmeny


def _regi(oldal, kezdo, napok):
    jel = defaultdict(set)
    for m in REGI.finditer(oldal):
        nap = dt.date(int(m.group(4)), int(m.group(2)), int(m.group(3)))
        jel[nap].add((m.group(1), int(m.group(5))))
    if not jel and "calendar_booking" not in oldal:
        return None
    eredmeny = []
    for i in range(napok):
        nap = kezdo + dt.timedelta(days=i)
        jelek = jel.get(nap, set())
        foglalt = any(f in (0, 1) for _, f in jelek)
        nyers = ",".join(sorted(f"{k}:{f}" for k, f in jelek))
        eredmeny.append((nap, FOGLALT if foglalt else SZABAD, nyers))
    return eredmeny


def mer(url, kezdo, napok):
    s = Munkamenet(referer=url)
    oldal = s.get(url)
    e = _uj(s, url, oldal, kezdo, napok)
    if e is None:
        e = _regi(oldal, kezdo, napok)
    if e is None:
        raise RuntimeError("nem található WP Booking Calendar naptár az oldalon")
    return e
