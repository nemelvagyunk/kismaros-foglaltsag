# kismaros-foglaltsag

Börzsönyligeti konkurens szállások foglaltságának napi mérése (60 napra előre).

- `szallasok.csv` – a mért szállások és foglalási oldaluk
- `teszt/elerhetoseg.py` – egyszeri teszt: elérhetők-e az oldalak a GitHub szerveréről
- `.github/workflows/elerhetoseg-teszt.yml` – a teszt kézi indítása (Actions → Elérhetőségi teszt → Run workflow)

A napi mérés a teszt után kerül ide.
