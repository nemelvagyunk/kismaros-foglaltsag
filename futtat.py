"""Napi foglaltságmérés.

Minden mérhető szállásnál lekéri a következő N éjszaka (alapból 60) állapotát, a mérés
napját követő éjtől kezdve (az aznapi éjt kihagyjuk: az aznapi foglalást van, ahol
engedik, van, ahol nem),
és egy napi pillanatképet ír: adatok/napi/ÉÉÉÉ-HH-NN.csv
  meres_nap;szallas_id;szallas;ej;allapot;nyers
ahol az "ej" az az éjszaka, amely azon a napon kezdődik.
A futás összesítője: adatok/naplo/ÉÉÉÉ-HH-NN.json és (GitHubon) a job summary.

Használat:  python futtat.py [--napok 60] [--csak 1,6,8]
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import traceback
from zoneinfo import ZoneInfo

from meres import appartman, egyedi, mphb, previo, resnweb, wpbc, wpbs
from meres.kozos import FOGLALT, ISMERETLEN, RESZBEN, SZABAD, ZARVA

ADAPTEREK = {
    "resnweb": lambda sor, kezdo, napok: resnweb.mer(sor["param"], kezdo, napok, int(sor["egysegek"] or 1)),
    "wpbc": lambda sor, kezdo, napok: wpbc.mer(sor["url"], kezdo, napok),
    "wpbs": lambda sor, kezdo, napok: wpbs.mer(sor["url"], kezdo, napok),
    "appartman": lambda sor, kezdo, napok: appartman.mer(sor["param"], kezdo, napok),
    "previo": lambda sor, kezdo, napok: previo.mer(sor["param"], kezdo, napok),
    "mphb": lambda sor, kezdo, napok: mphb.mer(sor["url"], kezdo, napok, sor["param"] or None),
    "ahazxml": lambda sor, kezdo, napok: egyedi.ahazxml(sor["param"], kezdo, napok),
    "cozystay": lambda sor, kezdo, napok: egyedi.cozystay(sor["url"], kezdo, napok),
    "vadlesen": lambda sor, kezdo, napok: egyedi.vadlesen(sor["param"], kezdo, napok),
    "mesebeli": lambda sor, kezdo, napok: egyedi.mesebeli(sor["url"], kezdo, napok, sor["param"] or None),
    "dopbsp": lambda sor, kezdo, napok: egyedi.dopbsp(sor["url"], kezdo, napok, sor["param"] or "1"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--napok", type=int, default=60)
    ap.add_argument("--csak", default="", help="vesszővel elválasztott szállás-id-k")
    ap.add_argument("--kimenet", default="adatok")
    args = ap.parse_args()

    ma = dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
    kezdo = ma + dt.timedelta(days=1)
    csak = {x.strip() for x in args.csak.split(",") if x.strip()}
    sorok = list(csv.DictReader(open("szallasok.csv", encoding="utf-8"), delimiter=";"))

    os.makedirs(os.path.join(args.kimenet, "napi"), exist_ok=True)
    os.makedirs(os.path.join(args.kimenet, "naplo"), exist_ok=True)
    kimenet = []
    naplo = []
    for sor in sorok:
        if csak and sor["id"] not in csak:
            continue
        motor = sor["motor"]
        if motor not in ADAPTEREK:
            naplo.append({"id": sor["id"], "szallas": sor["nev"], "motor": motor, "eredmeny": "nincs bekötve"})
            continue
        t0 = time.time()
        try:
            napok = ADAPTEREK[motor](sor, kezdo, args.napok)
            for nap, allapot, nyers in napok:
                kimenet.append([ma.isoformat(), sor["id"], sor["nev"], nap.isoformat(), allapot, nyers])
            db = {a: sum(1 for _, x, _ in napok if x == a) for a in (FOGLALT, SZABAD, ZARVA, RESZBEN, ISMERETLEN)}
            db14 = sum(1 for n, x, _ in napok if x == FOGLALT and (n - kezdo).days < 14)
            naplo.append({"id": sor["id"], "szallas": sor["nev"], "motor": motor, "eredmeny": "ok",
                          "napok": len(napok), "foglalt_14": db14, **db, "ido_s": round(time.time() - t0, 1)})
            print(f"OK   {sor['id']:>3} {sor['nev'][:32]:32} {motor:8} foglalt {db[FOGLALT]:>2}/{len(napok)} "
                  f"(14 nap: {db14}) részben {db[RESZBEN]} zárva {db[ZARVA]} ismeretlen {db[ISMERETLEN]}", flush=True)
        except Exception as e:
            naplo.append({"id": sor["id"], "szallas": sor["nev"], "motor": motor, "eredmeny": "hiba",
                          "hiba": f"{type(e).__name__}: {e}"[:300]})
            print(f"HIBA {sor['id']:>3} {sor['nev'][:32]:32} {motor:8} {type(e).__name__}: {e}", flush=True)
            traceback.print_exc(limit=1)
        time.sleep(1)

    fajl = os.path.join(args.kimenet, "napi", f"{ma.isoformat()}.csv")
    with open(fajl, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["meres_nap", "szallas_id", "szallas", "ej", "allapot", "nyers"])
        w.writerows(kimenet)
    json.dump({"meres_nap": ma.isoformat(), "elso_ej": kezdo.isoformat(), "napok": args.napok, "szallasok": naplo},
              open(os.path.join(args.kimenet, "naplo", f"{ma.isoformat()}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    ok = [n for n in naplo if n["eredmeny"] == "ok"]
    hiba = [n for n in naplo if n["eredmeny"] == "hiba"]
    sor_md = ["| Szállás | Motor | Foglalt éj (60 nap) | Foglalt éj (14 nap) | Részben | Zárva | Ismeretlen | Eredmény |",
              "|---|---|---|---|---|---|---|---|"]
    for n in naplo:
        if n["eredmeny"] == "nincs bekötve":
            continue
        if n["eredmeny"] == "ok":
            sor_md.append(f"| {n['szallas']} | {n['motor']} | {n[FOGLALT]}/{n['napok']} | {n['foglalt_14']}/14 | "
                          f"{n[RESZBEN]} | {n[ZARVA]} | {n[ISMERETLEN]} | ok |")
        else:
            sor_md.append(f"| {n['szallas']} | {n['motor']} | – | – | – | – | – | HIBA: {n['hiba'][:80]} |")
    osszeg = (f"**Mérés {ma.isoformat()}: {len(ok)} szállás rendben, {len(hiba)} hiba, "
              f"{sum(1 for n in naplo if n['eredmeny'] == 'nincs bekötve')} még nincs bekötve.**\n\n" + "\n".join(sor_md) + "\n")
    print(osszeg)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(osszeg)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
