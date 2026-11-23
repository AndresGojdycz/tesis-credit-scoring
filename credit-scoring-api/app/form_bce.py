"""Importador del formulario de estados contables del BROU (FORM_BCE, versión 08/08/2018).

`leer` toma el .xlsx completado por el cliente (con los valores calculados que guarda Excel) y devuelve las variables
del modelo tal como las declaró el cliente, sin convertir montos. Los estados se leen de la columna que el cliente
completó. Las hojas de detalle se usan para separar moneda nacional y extranjera, y BROU de otros bancos; como vienen
siempre en la columna en $, si los estados se completaron en la otra columna se llevan a esa escala con el tipo de
cambio de cierre de INFORMACIÓN GENERAL, para que sumen con los estados. Los signos se llevan a la convención de los
datos de entrenamiento: costos, gastos y pérdidas en positivo; ganancias financieras en negativo.

`importar` arma, a partir de eso, los campos del formulario del dashboard (mismos nombres que las columnas del CSV)
y la lista de avisos para revisar antes de evaluar. La correspondencia celda por celda está en mapeo_form_bce.md.
"""
import io
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import openpyxl

AC, ANC, PC, PNC, PAT, ER = ('ACTIVO CORRIENTE', 'ACTIVO NO CORRIENTE', 'PASIVO CORRIENTE', 'PASIVO NO CORRIENTE',
                             'PATRIMONIO', 'ESTADO DEL RESULTADO INTEGRAL')
DA, DP, DF, IG = 'DETALLE DEL ACTIVO', 'DETALLE DEL PASIVO', 'DETALLE DE PASIVOS FINANCIEROS', 'INFORMACIÓN GENERAL'
HOJAS = (IG, AC, ANC, PC, PNC, PAT, ER, DA, DP, DF)


class FormularioInvalido(ValueError):
    """El archivo no es un FORM_BCE 2018 que se pueda leer."""


def _n(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0


def _sin_centavos(x):
    """Un residuo de menos de una unidad es redondeo (moneda extranjera traducida en el detalle), no una deuda."""
    return 0.0 if abs(x) < 1 else x


def _abrir(fuente):
    if isinstance(fuente, (bytes, bytearray)):
        fuente = io.BytesIO(fuente)
    try:
        wb = openpyxl.load_workbook(fuente, data_only=True)
    except Exception as e:
        raise FormularioInvalido('No se pudo abrir el archivo como planilla de Excel (.xlsx).') from e
    faltan = [h for h in HOJAS if h not in wb.sheetnames]
    if faltan:
        raise FormularioInvalido('El archivo no es el formulario de estados contables del BROU, versión 2018: '
                                 f'faltan las hojas {", ".join(faltan)}.')
    return wb


def leer(fuente):
    """Variables del modelo de un FORM_BCE 2018 (ruta, bytes o archivo abierto)."""
    wb = _abrir(fuente)
    c = lambda hoja, ref: _n(wb[hoja][ref].value)
    ig = wb[IG]
    tc = _n(ig['F17'].value) or 1.0
    moneda = str(ig['F16'].value or '').upper()
    en_dolares = 'U' in moneda and 'S' in moneda

    def lector(col_usd, col_pesos):
        # Usa la columna que tiene datos; si el formulario dice US$, prioriza esa
        usd = any(_n(wb[h][f'{col_usd}{f}'].value) for h, f in ((AC, 72), (ANC, 58), (PAT, 35)))
        pes = any(_n(wb[h][f'{col_pesos}{f}'].value) for h, f in ((AC, 72), (ANC, 58), (PAT, 35)))
        if usd and (en_dolares or not pes):
            return (lambda h, f: c(h, f'{col_usd}{f}')), 'US$'
        return (lambda h, f: c(h, f'{col_pesos}{f}')), '$'

    def totales(S):
        R = lambda f: S(ER, f)
        ingresos = R(9) + R(10) + R(12) + sum(R(f) for f in range(13, 21))
        neto = R(67)
        return {
            'Total Activo Corriente': S(AC, 72), 'TOTAL ACTIVO': S(ANC, 58), 'TOTAL PASIVO': S(PNC, 52),
            'TOTAL PATRIMONIO': S(PAT, 35), 'TOTAL PASIVO Y PATRIMONIO': S(PAT, 37),
            '+(gan) -(pérd) Res Periodo': S(PAT, 30),
            'Total Ingresos Operativos': ingresos, 'Total Ingresos Operativos Netos': R(23),
            'Resultado Bruto': R(29), 'Resultado Operativo': R(44), 'Resultado Neto': neto,
            'Resultado Sin Amortizaciones': neto + R(33),
        }

    S, moneda_leida = lector('F', 'G')
    R = lambda f: S(ER, f)
    # Las hojas de detalle vienen en la columna en $: si los estados se completaron en la otra, se llevan a su escala
    a_moneda = 1.0 / tc if moneda_leida == 'US$' else 1.0
    e = totales(S)
    if not (e['TOTAL ACTIVO'] or e['TOTAL PATRIMONIO'] or e['Total Ingresos Operativos Netos']):
        raise FormularioInvalido('El formulario no tiene montos del ejercicio actual. Si está completo, puede que '
                                 'se haya guardado sin calcular las fórmulas: abrilo en Excel, guardalo y volvé a '
                                 'subirlo.')

    # Detalle de pasivos financieros: se clasifica por el nombre de la institución, no por la fila
    def deudas(filas_me, filas_mn):
        out = {'BROU_MN': 0.0, 'BROU_ME': 0.0, 'BCO_MN': 0.0, 'BCO_ME': 0.0, 'OTRAS': 0.0}
        hoja = wb[DF]
        for filas, mon in ((filas_me, 'ME'), (filas_mn, 'MN')):
            for f in filas:
                inst = str(hoja[f'B{f}'].value or '').upper()
                monto = _n(hoja[f'L{f}'].value)
                if not monto:
                    tot = _n(hoja[f'J{f}'].value) or (_n(hoja[f'G{f}'].value) + _n(hoja[f'H{f}'].value) - _n(hoja[f'I{f}'].value))
                    monto = tot * (_n(hoja[f'K{f}'].value) or 1.0) if mon == 'ME' else tot
                if not monto:
                    continue
                monto *= a_moneda
                if 'OTRAS' in inst:
                    out['OTRAS'] += monto
                elif 'BROU' in inst or 'REPUBLICA' in inst or 'REPÚBLICA' in inst:
                    out[f'BROU_{mon}'] += monto
                else:
                    out[f'BCO_{mon}'] += monto
        return out

    cp = deudas(range(9, 18), range(20, 29))
    lp = deudas(range(31, 40), range(42, 51))
    da = wb[DA]; dp = wb[DP]
    d = lambda hoja, ref: _n(hoja[ref].value) * a_moneda

    bancos_mn = d(da, 'F9') + d(da, 'F10')
    bancos_me = d(da, 'D9') + d(da, 'D10')
    disponib = S(AC, 13)
    caja = disponib - bancos_mn - bancos_me if (bancos_mn or bancos_me) else S(AC, 9)
    com_me = d(dp, 'D15') + d(dp, 'D22')
    com_mn = d(dp, 'F15') + d(dp, 'F22')
    if not (com_me or com_mn):
        com_mn = S(PC, 17)
    directores_p = (d(dp, 'D24') + d(dp, 'F24')) or S(PC, 40)
    fin_cp_total = S(PC, 30)
    fin_cp_detalle = sum(cp.values())
    fin_lp_total = S(PNC, 29)
    bienes_uso, amort_acum, imp_dif = S(ANC, 43), S(ANC, 45), S(ANC, 10)

    e.update({
        'Caja': caja, 'Bancos': bancos_mn, 'Bancos M/E': bancos_me, 'Sub-total - Disponibilidades': disponib,
        'Inversiones Temporarias': S(AC, 22), 'Depositos en Garantia': S(AC, 37),
        'Creditos Vtas.Plaza': S(AC, 25) + S(AC, 29) + S(AC, 31) + S(AC, 32), 'Creditos Vtas.Exp.': S(AC, 26),
        'Documentos a cobrar': S(AC, 27),
        'Otros Creditos': S(AC, 36) + S(AC, 38) + S(AC, 40) + S(AC, 41) + S(AC, 43) + S(AC, 44),
        'Ctas. de Directores(6)': S(AC, 39), 'Bienes de Cambio': S(AC, 56) + S(AC, 70),
        'Bienes de Uso': bienes_uso, 'Amort. Acumuladas': amort_acum, 'Impuesto Diferido': imp_dif,
        'Otros Activos No Corrientes': S(ANC, 56) - bienes_uso - amort_acum - imp_dif,
        'Total Activo no Corriente': S(ANC, 56),
        'Deudas Comercs': com_mn, 'Deudas Coms. MExt.': com_me,
        'Deudas BROU MNal.': cp['BROU_MN'], 'Deudas BROU MExt.': cp['BROU_ME'],
        'Acreeds. Bancarios MNal.': cp['BCO_MN'], 'Acreeds. Bancarios MExt.': cp['BCO_ME'],
        # Lo que el detalle no explica del total de pasivos financieros va a otras deudas financieras
        'otras deudas financieras': _sin_centavos(fin_cp_total - fin_cp_detalle) + cp['OTRAS'],
        'Deudas Diversas': S(PC, 42) - directores_p, 'Previsiones y Provisiones': S(PC, 49),
        'Ctas. de Directores (6)': directores_p, 'Total Pasivo Corriente': S(PC, 51),
        'Deudas BROU MNal..1': lp['BROU_MN'], 'Deudas BROU MExt..1': lp['BROU_ME'],
        'Acreeds. Bancarios': lp['BCO_MN'] + lp['BCO_ME'],
        'Ctras Deudas Largo Plazo': _sin_centavos(S(PNC, 50) - lp['BROU_MN'] - lp['BROU_ME'] - lp['BCO_MN'] - lp['BCO_ME']),
        'Total Pasivo No Corriente': S(PNC, 50),
        'Capital': sum(S(PAT, f) for f in (9, 10, 11, 12)), 'Adelantos Irrevocs.': S(PAT, 14) + S(PAT, 15),
        'Revaluaciones': S(PAT, 18) + S(PAT, 19) + S(PAT, 20), 'Reservas': S(PAT, 24) + S(PAT, 25) + S(PAT, 26),
        '+(gan) -(pérd) Aj por Infl': 0.0, '+(gan) -(pérd) Res Acums.': S(PAT, 29),
        '- Dividendo Provisorio': S(PAT, 32), 'Ajustes al Patrim.': 0.0,
        'Ventas Plaza': R(9) + R(10) + sum(R(f) for f in range(13, 21)), 'Exportaciones': R(12),
        'Resultado por Tenencia - NIC 41 -': 0.0,
        'Ajustes/Bonificaciones s/Ventas': -R(22),
        'Costo de lo Vendido': R(27), 'Amortizaciones': R(33), 'Gastos  Ad.y Ventas.': R(37) - R(33),
        '- Otros Gastos + Otros Ingresos': R(42),
        'Intereses Perdidos.': -R(47), 'Intereses Ganados': -R(48), 'Otros Gastos(+)/Ingresos(-) Financieros': -(R(49) + R(50)),
        'Diferencia de Cambio Perdida.': -R(51), 'Diferencia de Cambio Ganada': -R(52), '+(pérd) -(gan) RDM': -R(53),
        '- Otros Resultados- Extraordinarios.': -(R(63) + R(64) + R(65)), 'Impto. a la Renta': R(58),
        '- Otros Resultados No Operativos.': 0.0,
    })

    S_ant, _ = lector('C', 'D')   # ejercicio anterior
    e.update({f'{k} (anterior)': x for k, x in totales(S_ant).items()})

    fecha = ig['C9'].value
    if isinstance(fecha, (datetime, date)):
        if fecha.day == 1:      # como en el notebook: un balance fechado el día 1 cierra el mes anterior
            fecha = fecha - timedelta(days=1)
        e['FECHA_CIERRE'] = f'{fecha.year}-{fecha.month:02d}'
    e['NUMERO_EMPLEADOS'] = _n(ig['E13'].value) + _n(ig['I13'].value)
    e['GRUPO_ECONOMICO'] = 1.0 if str(ig['E37'].value or '').strip() else 0.0
    e['TIPO_SOCIEDAD_TEXTO'] = str(ig['C5'].value or '')
    e['GIRO_TEXTO'] = str(ig['C10'].value or '')

    # Controles
    e['_moneda'] = moneda_leida
    e['_tipo_cambio'] = tc
    e['_cuadre_actual'] = S(ANC, 58) - S(PAT, 37)
    e['_cuadre_anterior'] = S_ant(ANC, 58) - S_ant(PAT, 37)
    e['_cuadre_disponib'] = caja + bancos_mn + bancos_me - disponib
    e['_fin_cp_sin_detalle'] = fin_cp_total - fin_cp_detalle
    e['_fin_lp_sin_detalle'] = fin_lp_total - sum(lp.values())
    e['_cuadre_comerciales'] = com_mn + com_me - S(PC, 17)
    e['_neto_vs_partidas'] = (e['Resultado Operativo'] - sum(e[k] for k in (
        'Intereses Perdidos.', 'Intereses Ganados', 'Otros Gastos(+)/Ingresos(-) Financieros',
        'Diferencia de Cambio Perdida.', 'Diferencia de Cambio Ganada', '+(pérd) -(gan) RDM',
        '- Otros Resultados- Extraordinarios.', 'Impto. a la Renta', '- Otros Resultados No Operativos.'))
        - e['Resultado Neto'])
    e['_operativo_vs_partidas'] = (e['Total Ingresos Operativos Netos'] - e['Costo de lo Vendido'] - e['Amortizaciones']
                                   - e['Gastos  Ad.y Ventas.'] + e['- Otros Gastos + Otros Ingresos'] - e['Resultado Operativo'])
    return e


# Del formulario al dashboard

AGRO = 'Agropecuario, Pesca y Minería'
_VACIAS = {'DE', 'DEL', 'Y', 'LA', 'LAS', 'EL', 'LOS', 'EN', 'POR', 'AL', 'PARA', 'CON', 'A', 'O', 'X', 'N', 'C', 'P',
           'E', 'S', 'U', 'NCP', 'EXC', 'EXCEPTO', 'OTROS', 'OTRAS', 'OTRO', 'OTRA', 'TIPOS', 'ACT', 'ACTIVIDADES',
           'ACTIVIDAD', 'SERV', 'SERVICIOS', 'PROD', 'PRODUCTOS', 'VTA', 'VENTA', 'VENTAS', 'MAYOR', 'MENOR', 'FAB',
           'FABRICACION', 'ELAB', 'ELABORACION', 'EMPRESA', 'COMERCIAL', 'GENERAL', 'GENERALES', 'COMERCIO',
           'COMERC', 'COMERCIALIZACION'}


def _normalizar(texto):
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+', ' ', t).strip()


def _palabras(texto):
    return [p for p in _normalizar(texto).split() if p not in _VACIAS and len(p) >= 3]


def _parecido(a, b):
    """0 a 1: misma palabra, abreviatura de la otra (EDIF / EDIFICIOS), misma raíz (ALMACENAJE / ALMACENAMIENTO)
    o la misma con un error de tipeo (DESPOSITO / DEPOSITO)."""
    if a == b:
        return 1.0
    r = SequenceMatcher(None, a, b).ratio()
    corta, larga = sorted((a, b), key=len)
    abreviatura = len(corta) >= 4 and larga.startswith(corta)
    raiz = len(os.path.commonprefix([a, b])) >= 5 and r >= 0.7
    if abreviatura or raiz or (len(corta) >= 5 and r >= 0.8):
        return r
    return 0.0


def actividad_mas_parecida(giro, actividades):
    """Actividad de la lista del BCU que mejor coincide con el giro declarado, o None si ninguna convence.

    Primero busca la actividad escrita igual. Si no, cada palabra con contenido del giro se compara con la más
    parecida de cada actividad, y se promedia; a igual promedio gana la actividad con menos palabras de más. Pide
    un promedio de 0,6 o más y que la mejor no empate con otra: ante la duda, la actividad se elige a mano.
    """
    actividades = list(actividades)
    exacta = {_normalizar(a): a for a in actividades}.get(_normalizar(giro))
    if exacta:
        return exacta
    pg = _palabras(giro)
    if not pg:
        return None
    puntajes = []
    for act in actividades:
        pa = _palabras(act)
        if not pa:
            continue
        mejores = [max(_parecido(p, q) for q in pa) for p in pg]
        sobran = sum(1 for q in pa if not any(_parecido(p, q) for p in pg))
        puntajes.append((round(sum(mejores) / len(pg), 3), -sobran, act))
    puntajes.sort(reverse=True)
    if not puntajes or puntajes[0][0] < 0.6 or (len(puntajes) > 1 and puntajes[1][:2] == puntajes[0][:2]):
        return None
    return puntajes[0][2]


def tipo_de_sociedad(texto):
    """Tipo de sociedad de la lista del formulario, tolerando abreviaturas y errores de tipeo."""
    t = _normalizar(texto)
    if not t:
        return None
    palabras = t.split()
    tiene = lambda clave: any(SequenceMatcher(None, p, clave).ratio() >= 0.7 for p in palabras)
    compacto = t.replace(' ', '')
    if tiene('ANONIMA') or compacto == 'SA' or re.search(r'\bS A\b', t):
        return 'Sociedad Anonima'
    if tiene('LIMITADA') or compacto == 'SRL' or re.search(r'\bS R L\b|\bSRL\b', t):
        return 'Sociedad de Resp. Limitada'
    if tiene('COMANDITA'):
        return 'Sociedad en Comandita Simple'
    if tiene('UNIPERSONAL'):
        return 'Unipersonal'
    if 'HECHO' in palabras:
        return 'Sociedad de Hecho'
    return 'Otros'


def _monto(x):
    return f'{x:,.0f}'.replace(',', '.')


def importar(fuente, actividad_a_sector=None):
    """Campos del formulario del dashboard y avisos para revisar, a partir de un FORM_BCE 2018.

    `campos` usa los mismos nombres que las columnas del CSV de carga: partidas con el nombre del modelo, el año
    anterior con el sufijo " (anterior)", FECHA_CIERRE (YYYY-MM) y las cualitativas con los valores de las listas
    del formulario. `actividad_a_sector` es la tabla actividad -> industria del PIB (artifacts/macro.json).
    """
    e = leer(fuente)
    tolerancia = max(1.0, abs(e['TOTAL ACTIVO']) * 1e-4)
    campos, avisos = {}, []

    for k, x in e.items():
        if not k.startswith('_') and isinstance(x, float) and k not in ('NUMERO_EMPLEADOS', 'GRUPO_ECONOMICO'):
            campos[k] = round(x, 2)

    if e.get('FECHA_CIERRE'):
        campos['FECHA_CIERRE'] = e['FECHA_CIERRE']
    else:
        avisos.append('No se encontró la fecha de cierre (INFORMACIÓN GENERAL, C9): sin ella no se completan las '
                      'variables macroeconómicas.')
    if e['NUMERO_EMPLEADOS']:
        campos['NUMERO_EMPLEADOS'] = e['NUMERO_EMPLEADOS']
    campos['GRUPO_ECONOMICO'] = '1' if e['GRUPO_ECONOMICO'] else '0'

    tipo = tipo_de_sociedad(e['TIPO_SOCIEDAD_TEXTO'])
    if tipo:
        campos['TIPO_SOCIEDAD'] = tipo
        if tipo == 'Otros':
            avisos.append(f'Tipo de sociedad "{e["TIPO_SOCIEDAD_TEXTO"].strip()}": no se reconoció, quedó como Otros.')

    giro = e['GIRO_TEXTO'].strip()
    tabla = actividad_a_sector or {}
    actividad = actividad_mas_parecida(giro, tabla.keys()) if giro else None
    if actividad:
        campos['ACTIVIDAD_ECONOMICA'] = actividad
        industria = tabla.get(actividad)
        if industria:
            campos['SECTOR_PIB'] = industria
            campos['SECTOR'] = 'Agro' if industria == AGRO else 'Empresas'
        avisos.append(f'Giro declarado "{giro}": se propuso la actividad "{actividad}". Revisala.')
    elif giro:
        avisos.append(f'Giro declarado "{giro}": no se encontró una actividad parecida en la lista. Elegila a mano.')

    if not e['TOTAL ACTIVO (anterior)']:
        avisos.append('El formulario no trae el ejercicio anterior: las variaciones quedan sin informar y el modelo '
                      'las imputa.')

    controles = [
        ('_cuadre_actual', 'El balance no cuadra: activo menos pasivo y patrimonio da {}.'),
        ('_cuadre_anterior', 'El balance del ejercicio anterior no cuadra: activo menos pasivo y patrimonio da {}.'),
        ('_fin_cp_sin_detalle', 'Hay {} de pasivos financieros de corto plazo sin detalle por institución: se '
                                'cargaron en otras deudas financieras.'),
        ('_fin_lp_sin_detalle', 'Hay {} de pasivos financieros de largo plazo sin detalle por institución: se '
                                'cargaron en otras deudas de largo plazo.'),
        ('_cuadre_comerciales', 'El detalle de deudas comerciales difiere del estado en {}.'),
        ('_operativo_vs_partidas', 'El resultado operativo no cierra con sus partidas por {}.'),
        ('_neto_vs_partidas', 'El resultado neto no cierra con el operativo y las partidas financieras por {}.'),
    ]
    for clave, texto in controles:
        if abs(e[clave]) > tolerancia:
            avisos.append(texto.format(_monto(e[clave])))

    return {'campos': campos, 'avisos': avisos}


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        sys.exit('Uso: python app/form_bce.py <formulario .xlsx>')
    for k, x in leer(sys.argv[1]).items():
        print(f'{k:45s} {x:,.0f}' if isinstance(x, float) else f'{k:45s} {x}')
