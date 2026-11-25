"""Közös segédfüggvények: HTTP-lekérés (csak standard könyvtár), állapotok."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Egy éjszaka állapota (a dátum az az éjszaka, amely aznap este kezdődik)
FOGLALT = "foglalt"      # az éj foglalt (vagy a tulajdonos zárta, ha nem megkülönböztethető)
SZABAD = "szabad"
ZARVA = "zarva"          # a naptár kifejezetten lezártként / nem foglalhatóként jelöli
RESZBEN = "reszben"      # több egységnél: van foglalt egység, de nem mind
ISMERETLEN = "ismeretlen"


class Munkamenet:
    """Sütiket megtartó, újrapróbálkozó HTTP-kliens."""

    def __init__(self, referer=None):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.op.addheaders = [("User-Agent", UA), ("Accept-Language", "hu-HU,hu;q=0.9,en;q=0.8")]
        self.referer = referer

    def _nyit(self, req, timeout):
        utolso = None
        for proba in range(3):
            try:
                with self.op.open(req, timeout=timeout) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    raise
                utolso = e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                utolso = e
            time.sleep(3 * (proba + 1))
        raise utolso

    def get(self, url, timeout=40):
        return self._nyit(urllib.request.Request(url), timeout)

    def post(self, url, adat, referer=None, timeout=60):
        hd = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
              "X-Requested-With": "XMLHttpRequest"}
        if referer or self.referer:
            hd["Referer"] = referer or self.referer
        req = urllib.request.Request(url, data=urllib.parse.urlencode(adat).encode(), headers=hd)
        return self._nyit(req, timeout)

    def post_json(self, url, adat, referer=None, timeout=60):
        return json.loads(self.post(url, adat, referer, timeout))


def honapok(kezdo, napok):
    """A [kezdo, kezdo+napok) időszakot lefedő (év, hónap) párok."""
    import datetime as dt
    vege = kezdo + dt.timedelta(days=napok - 1)
    y, m = kezdo.year, kezdo.month
    out = []
    while (y, m) <= (vege.year, vege.month):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out
