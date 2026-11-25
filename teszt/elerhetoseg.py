"""Egyszeri elérhetőségi teszt: a GitHub szerveréről lekérhetők-e a szállások foglalási oldalai.

Minden szállásnál lekéri a foglalási oldalt, és a benne talált beágyazott foglalómotor-oldalakat
(iframe / link: nethotelbooking, previo, appartman stb.). Oldalanként rögzíti:
- HTTP-státusz, végső URL, méret
- tiltó / robotellenőrző oldal jelei
- foglalómotor- és naptárjelek a HTML-ben
Kimenet: teszt/eredmeny.json, teszt/eredmeny.md (és a GitHub job summary).
"""
import csv
import json
import os
import re
import time
from urllib.parse import urljoin

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
}

TILTAS = {
    "Cloudflare-ellenőrzés": [r"cf-chl", r"challenge-platform", r"Just a moment\.\.\.", r"Attention Required"],
    "SiteGround-captcha": [r"sgcaptcha", r"/.well-known/sgcaptcha"],
    "Wordfence-tiltás": [r"Your access to this site has been limited"],
    "Imunify360": [r"imunify360"],
    "Access denied": [r"<title>\s*Access denied", r"<title>\s*403 Forbidden"],
}

MOTOR = {
    "RESnWEB": [r"nethotelbooking\.net", r"resnweb"],
    "WP Booking Calendar": [r"cal4date", r"wpbc_", r"booking_calendar"],
    "WP Booking System": [r"wpbs-", r"wp-booking-system"],
    "Previo": [r"previo\.(?:cz|app|hu)", r"booking\.previo"],
    "Appartman": [r"appartman\.hu"],
    "Barion": [r"barion"],
    "Szallas.hu widget": [r"szallas\.hu/.*widget", r"szallas\.hu/[^\"']*/foglal"],
    "naptár (általános)": [r"fullcalendar", r"flatpickr", r"datepicker", r"naptar", r"calendar"],
}

BEAGYAZOTT = re.compile(
    r"""(?:src|href)=["']([^"']*(?:nethotelbooking\.net/hotels/[^"']+|previo\.[a-z]+/[^"']+|"""
    r"""appartman\.hu/[^"']+|booking\.[a-z0-9.-]+/[^"']+))["']""",
    re.I,
)


def jelek(html, minta):
    talalt = []
    for nev, regexek in minta.items():
        if any(re.search(r, html, re.I | re.S) for r in regexek):
            talalt.append(nev)
    return talalt


def lekeres(url):
    t0 = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        html = r.text or ""
        return {
            "url": url,
            "statusz": r.status_code,
            "vegso_url": r.url,
            "meret_kb": round(len(r.content) / 1024, 1),
            "ido_s": round(time.time() - t0, 1),
            "tiltas": jelek(html[:200000], TILTAS),
            "motor": jelek(html, MOTOR),
            "_html": html,
        }
    except requests.RequestException as e:
        return {"url": url, "statusz": None, "hiba": f"{type(e).__name__}: {e}"[:200],
                "ido_s": round(time.time() - t0, 1), "tiltas": [], "motor": [], "_html": ""}


def ertekel(f):
    if f.get("statusz") is None:
        return "NEM ÉRHETŐ EL"
    if f["tiltas"]:
        return "TILTÁS / ELLENŐRZÉS"
    if f["statusz"] >= 400:
        return f"HIBA {f['statusz']}"
    return "OK"


def main():
    sorok = list(csv.DictReader(open("szallasok.csv", encoding="utf-8"), delimiter=";"))
    eredmeny = []
    for s in sorok:
        fo = lekeres(s["url"])
        beagyazott = []
        for m in sorted(set(BEAGYAZOTT.findall(fo["_html"])))[:3]:
            u = urljoin(fo.get("vegso_url") or s["url"], m.replace("&amp;", "&"))
            b = lekeres(u)
            b.pop("_html", None)
            b["ertekeles"] = ertekel(b)
            beagyazott.append(b)
            time.sleep(1)
        fo.pop("_html", None)
        fo["ertekeles"] = ertekel(fo)
        eredmeny.append({"id": s["id"], "nev": s["nev"], "motor_lista": s["motor"],
                         "oldal": fo, "beagyazott": beagyazott})
        print(f"{s['id']:>3} {s['nev'][:34]:34} {fo['ertekeles']:20} {fo.get('statusz')} "
              f"{','.join(fo['motor'])} | beágyazott: "
              + "; ".join(f"{b['ertekeles']} {b['url'][:60]}" for b in beagyazott), flush=True)
        time.sleep(1)

    json.dump(eredmeny, open("teszt/eredmeny.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    md = ["| # | Szállás | Oldal | Státusz | Tiltás | Talált motor/naptár jel | Beágyazott foglalómotor |",
          "|---|---|---|---|---|---|---|"]
    for e in eredmeny:
        o = e["oldal"]
        bg = "<br>".join(f"{b['ertekeles']} ({b.get('statusz')}) {b['url'][:70]}" for b in e["beagyazott"]) or "–"
        md.append(f"| {e['id']} | {e['nev']} | {o['ertekeles']} | {o.get('statusz')} | "
                  f"{', '.join(o['tiltas']) or '–'} | {', '.join(o['motor']) or '–'} | {bg} |")
    ok = sum(1 for e in eredmeny if e["oldal"]["ertekeles"] == "OK")
    osszeg = f"**{ok} / {len(eredmeny)} oldal érhető el tiltás nélkül a GitHub szerveréről.**\n\n"
    szoveg = osszeg + "\n".join(md) + "\n"
    open("teszt/eredmeny.md", "w", encoding="utf-8").write(szoveg)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(szoveg)
    print(osszeg)


if __name__ == "__main__":
    main()
