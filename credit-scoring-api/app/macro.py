"""Variables macroeconomicas a partir de la fecha de cierre del balance y la actividad de la empresa.

Usa artifacts/macro.json (generado por export_macro_for_api.py con los mismos pasos del notebook):
PIB de la industria de la empresa con 3 meses de rezago y desempleo con 1 mes, mas sus variaciones
trimestral e interanual, indexados por el mes de cierre del balance (YYYY-MM).
"""

import json
import logging
import math
from datetime import date
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

MACRO_PATH = settings.ARTIFACTS_DIR / "macro.json"
PIB_VARS = ("PIB", "PIB_var_trimestral", "PIB_var_interanual")
DESEMPLEO_VARS = ("Desempleo", "Desempleo_var_trimestral", "Desempleo_var_interanual")

_macro: Optional[Dict] = None


def _cargar() -> Optional[Dict]:
    global _macro
    if _macro is None and MACRO_PATH.exists():
        _macro = json.loads(MACRO_PATH.read_text(encoding="utf-8"))
        logger.info(f"Series macro cargadas: {len(_macro['pib'])} industrias con PIB, "
                    f"{len(_macro['actividad_a_sector'])} actividades")
    return _macro


def mes_de_cierre(fecha) -> Optional[str]:
    """Mes de cierre (YYYY-MM). Acepta 'YYYY-MM', 'YYYY-MM-DD' y 'DD/MM/YYYY'. Como en el notebook,
    un balance fechado el dia 1 es el cierre del ultimo dia del mes anterior."""
    if fecha is None:
        return None
    s = str(fecha).strip()
    try:
        if len(s) == 7 and s[4] == "-":                 # YYYY-MM
            return s
        if "/" in s:                                    # DD/MM/YYYY
            d, m, y = (int(p) for p in s.split("/"))
            y = y + 2000 if y < 100 else y
        else:                                           # YYYY-MM-DD
            y, m, d = (int(p) for p in s[:10].split("-"))
        dia = date(y, m, d)
    except (ValueError, TypeError):
        return None
    if dia.day == 1:
        y, m = (dia.year - 1, 12) if dia.month == 1 else (dia.year, dia.month - 1)
    else:
        y, m = dia.year, dia.month
    return f"{y:04d}-{m:02d}"


def _vacio(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def completar_macro(features: Dict) -> Dict:
    """Completa PIB, desempleo y sus variaciones si llega la fecha de cierre (FECHA_CIERRE).

    La industria del PIB sale de SECTOR_PIB, si viene, o de la actividad economica. Los valores
    que el cliente envio no se sobrescriben. Sin fecha, o fuera del rango de las series, las
    variables quedan sin informar y el modelo las imputa con la mediana de entrenamiento.
    """
    macro = _cargar()
    mes = mes_de_cierre(features.get("FECHA_CIERRE"))
    if macro is None or mes is None:
        return features
    out = dict(features)

    sector = out.get("SECTOR_PIB")
    if _vacio(sector) or str(sector).strip() == "":
        sector = macro["actividad_a_sector"].get(str(out.get("ACTIVIDAD_ECONOMICA") or "").strip())
    valores_pib = (macro["pib"].get(sector) or {}).get(mes) if sector else None
    if valores_pib:
        for nombre, v in zip(PIB_VARS, valores_pib):
            if _vacio(out.get(nombre)) and v is not None:
                out[nombre] = v

    valores_des = macro["desempleo"].get(mes)
    if valores_des:
        for nombre, v in zip(DESEMPLEO_VARS, valores_des):
            if _vacio(out.get(nombre)) and v is not None:
                out[nombre] = v
    return out
