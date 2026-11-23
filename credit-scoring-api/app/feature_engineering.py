"""Variables derivadas que el API calcula a partir de las partidas del balance.

Espeja `notebooks/funciones.py::apply_feature_engineering` (ratios con `safe_ratio`:
None si el numerador o el denominador faltan o el denominador es 0). Es la unica
fuente de las formulas en el API: la usa el predictor, de modo que el ingreso
manual, la carga de archivos y el batch calculan los ratios igual que el
entrenamiento.
"""

import math
from typing import Dict, List, Optional, Tuple


def _ratio(campos: Dict, num_key: str, den_key: str) -> Tuple[Optional[float], int]:
    num = campos.get(num_key)
    den = campos.get(den_key)
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)):
        return None, 1
    if math.isnan(num) or math.isnan(den) or den == 0:
        return None, 1
    return num / den, 0


def _get_ing_keys(campos: Dict) -> tuple:
    """Ingresos brutos vs netos, espejando funciones.apply_feature_engineering
    del entrenamiento: margen bruto/operativo, GAV, exportaciones y rotacion
    usan BRUTOS; margen neto usa NETOS (la cobertura de intereses es
    Resultado Operativo / Intereses Perdidos). Si solo hay
    una de las dos columnas, se usa para ambos roles (mismo fallback que train).
    """
    brutos = ('Total Ingresos Operativos'
              if isinstance(campos.get('Total Ingresos Operativos'), (int, float)) else None)
    netos = ('Total Ingresos Operativos Netos'
             if isinstance(campos.get('Total Ingresos Operativos Netos'), (int, float)) else None)
    return (brutos or netos or 'Total Ingresos Operativos',
            netos or brutos or 'Total Ingresos Operativos Netos')


def definir_ratios(campos: Dict) -> List[Tuple[str, str, str]]:
    """(numerador, denominador, nombre) de cada ratio, con brutos/netos segun train."""
    ing_brutos, ing_netos = _get_ing_keys(campos)
    return [
        ('Resultado Operativo', 'Intereses Perdidos.', 'Cobertura_de_intereses'),
        ('TOTAL PASIVO', 'TOTAL PATRIMONIO', 'Relacion_deuda_patrimonio'),
        ('TOTAL ACTIVO', 'TOTAL PATRIMONIO', 'Multiplicador'),
        ('Resultado Neto', 'TOTAL ACTIVO', 'ROA'),
        ('Resultado Neto', 'TOTAL PATRIMONIO', 'ROE'),
        ('Total Activo Corriente', 'Total Pasivo Corriente', 'Ratio_Corriente'),
        ('Sub-total - Disponibilidades', 'Total Pasivo Corriente', 'Ratio_Efectivo'),
        ('TOTAL PASIVO', 'TOTAL ACTIVO', 'Deuda_sobre_Activos'),
        ('Total Pasivo No Corriente', 'TOTAL ACTIVO', 'Deuda_LP_sobre_Activos'),
        ('TOTAL PATRIMONIO', 'TOTAL ACTIVO', 'Ratio_Patrimonio'),
        ('Bienes de Uso', 'TOTAL ACTIVO', 'Intensidad_Activo_Fijo'),
        ('Resultado Bruto', ing_brutos, 'Margen_Bruto'),
        ('Resultado Operativo', ing_brutos, 'Margen_Operativo'),
        ('Resultado Neto', ing_netos, 'Margen_Neto'),
        ('Resultado Sin Amortizaciones', ing_brutos, 'Margen_EBITDA'),
        ('Gastos  Ad.y Ventas.', ing_brutos, 'Ratio_GAV'),
        ('Exportaciones', ing_brutos, 'Ratio_Exportaciones'),
        (ing_brutos, 'TOTAL ACTIVO', 'Rotacion_Activos'),
        ('Amortizaciones', 'TOTAL ACTIVO', 'Intensidad_Depreciacion'),
    ]


def calcular_ratios(campos: Dict) -> Dict[str, float]:
    """Ratios calculables a partir de las partidas disponibles (los demas no se devuelven)."""
    ratios = {}
    for num, den, out in definir_ratios(campos):
        val, _ = _ratio(campos, num, den)
        if val is not None:
            ratios[out] = val

    # Prueba acida: (Activo Corriente - Bienes de Cambio) / Pasivo Corriente.
    # Como en train, si falta Bienes de Cambio el ratio queda sin calcular.
    ac, bc = campos.get('Total Activo Corriente'), campos.get('Bienes de Cambio')
    if isinstance(ac, (int, float)) and isinstance(bc, (int, float)):
        val, _ = _ratio({'num': ac - bc, 'den': campos.get('Total Pasivo Corriente')}, 'num', 'den')
        if val is not None:
            ratios['Prueba_Acida'] = val

    # Exposicion crediticia relativa (Central de Riesgos): sobre ventas brutas y patrimonio
    ing_brutos, _ = _get_ing_keys(campos)
    for den, out in [(ing_brutos, 'Importe_sobre_Ventas'), ('TOTAL PATRIMONIO', 'Importe_sobre_Patrimonio')]:
        val, _ = _ratio(campos, 'IMPORTE_MN', den)
        if val is not None:
            ratios[out] = val
    return ratios


def _vacio(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def completar_derivadas(features: Dict) -> Dict:
    """Completa las variables derivadas que el cliente no envio.

    - Ratios: se calculan desde las partidas del balance si no vienen informados
      (el formulario manual solo calcula algunos; el batch y otros clientes, ninguno).
    - primera_observacion: 1 si no llega ninguna variacion temporal (delta_*), como
      en train para la primera observacion de cada empresa; 0 si llega alguna.
    Los valores enviados por el cliente no se sobrescriben.
    """
    out = dict(features)
    for nombre, valor in calcular_ratios(out).items():
        if _vacio(out.get(nombre)):
            out[nombre] = valor
    if _vacio(out.get('primera_observacion')):
        hay_variaciones = any(k.startswith('delta_') and not _vacio(v) for k, v in out.items())
        out['primera_observacion'] = 0 if hay_variaciones else 1
    return out
