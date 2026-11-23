"""
Exportar las series macroeconomicas que usa el API para completar las variables macro.

Reproduce los pasos del notebook (scoring.ipynb):
  - PIB trimestral por industria (BCU), mensualizado repitiendo el valor del trimestre, con
    3 meses de rezago de publicacion; variaciones trimestral (3 meses) e interanual (12 meses)
    dentro de cada industria.
  - Desempleo mensual con 1 mes de rezago; variaciones trimestral e interanual.
  - Correspondencia entre actividad economica e industria del PIB (celda 4950ef4e del notebook).
Las series se indexan por el mes de cierre del balance (YYYY-MM), igual que en el notebook.

Ejecutar desde la raiz del proyecto:
    uv run python export_macro_for_api.py
"""
import json
import math
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).parent
MACRO_DIR = ROOT_DIR / "datos macro"
NOTEBOOK = ROOT_DIR / "notebooks" / "scoring.ipynb"
SALIDA = ROOT_DIR / "credit-scoring-api" / "artifacts" / "macro.json"
CELDA_MAPEO = "4950ef4e"   # celda del notebook con actividad_a_sector


def _pib_mensual() -> pd.DataFrame:
    df_pib_raw = pd.read_excel(MACRO_DIR / "Pib.xlsx", sheet_name="Valores_K", header=7)
    df_pib_raw = df_pib_raw.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
    df_pib = df_pib_raw.drop(columns="Sectores").rename(columns={"Unnamed: 1": "Sector"})
    df_pib.columns = [str(c).replace("*", "").strip() for c in df_pib.columns]

    import re
    trim_cols = [c for c in df_pib.columns if re.match(r"^(I|II|III|IV)\s+\d{4}$", c)]
    largo = df_pib.melt(id_vars="Sector", value_vars=trim_cols, var_name="Trimestre", value_name="PIB")
    roman = {"I": 1, "II": 4, "III": 7, "IV": 10}
    largo[["t", "Anio"]] = largo["Trimestre"].str.split(" ", expand=True)
    largo["Fecha"] = pd.to_datetime(dict(year=largo["Anio"].astype(int), month=largo["t"].map(roman), day=1))
    largo = largo[["Fecha", "Sector", "PIB"]].sort_values(["Sector", "Fecha"]).reset_index(drop=True)

    mensual = (largo.set_index("Fecha").groupby("Sector")[["PIB"]]
               .apply(lambda g: g.asfreq("MS").ffill()).reset_index())
    # Rezago de publicacion de 3 meses
    mensual["YEAR_MONTH"] = (mensual["Fecha"] + pd.DateOffset(months=3)).dt.strftime("%Y-%m")
    mensual = mensual.sort_values(["Sector", "YEAR_MONTH"])
    g = mensual.groupby("Sector")["PIB"]
    mensual["PIB_var_trimestral"] = g.pct_change(3)
    mensual["PIB_var_interanual"] = g.pct_change(12)
    return mensual


def _desempleo_mensual() -> pd.DataFrame:
    d = pd.read_csv(MACRO_DIR / "Csvs" / "Desempleo_limpio.csv")
    # Rezago de publicacion de 1 mes
    d["YEAR_MONTH"] = (pd.to_datetime(d["Fecha"]) + pd.DateOffset(months=1)).dt.strftime("%Y-%m")
    d = d.sort_values("YEAR_MONTH")
    d["Desempleo_var_trimestral"] = d["Desempleo"].pct_change(3)
    d["Desempleo_var_interanual"] = d["Desempleo"].pct_change(12)
    return d


def _actividad_a_sector() -> dict:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    celda = next(c for c in nb["cells"] if c.get("id") == CELDA_MAPEO)
    ns: dict = {}
    exec("".join(celda["source"]), ns)   # la celda solo define constantes
    # Sin normalizar: el notebook cruza el nombre de la industria tal cual con la serie del PIB
    return dict(ns["actividad_a_sector"])


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def main():
    pib = _pib_mensual()
    des = _desempleo_mensual()
    mapeo = _actividad_a_sector()
    sectores = sorted(set(mapeo.values()))

    # Igual que el merge del notebook: solo las industrias cuyo nombre coincide exactamente con el de la
    # serie del PIB reciben PIB. Las demas quedaron sin PIB en el entrenamiento (imputado con la mediana).
    salida = {
        "descripcion": "Series macro por mes de cierre del balance (YYYY-MM), con los rezagos del entrenamiento",
        "pib": {
            s: {r.YEAR_MONTH: [_num(r.PIB), _num(r.PIB_var_trimestral), _num(r.PIB_var_interanual)]
                for r in sub.itertuples()}
            for s, sub in pib.groupby("Sector") if s in sectores
        },
        "desempleo": {r.YEAR_MONTH: [_num(r.Desempleo), _num(r.Desempleo_var_trimestral),
                                     _num(r.Desempleo_var_interanual)] for r in des.itertuples()},
        "actividad_a_sector": mapeo,
    }
    salida["industrias_sin_pib"] = [s for s in sectores if s not in salida["pib"]]
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    meses_pib = sorted({m for v in salida["pib"].values() for m in v})
    print(f"macro.json: {len(salida['pib'])} industrias con PIB, PIB {meses_pib[0]} a {meses_pib[-1]}, "
          f"desempleo {min(salida['desempleo'])} a {max(salida['desempleo'])}, {len(mapeo)} actividades")
    print(f"Industrias sin PIB (como en el entrenamiento): {salida['industrias_sin_pib']}")


if __name__ == "__main__":
    main()
