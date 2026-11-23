"""
Genera los ejemplos de ejemplos/*.csv en el formato del formulario de estados contables del BROU
(FORM_BCE, version 08/08/2018, la que se usa hoy).

Para cada CSV llena una copia del formulario en blanco: informacion general, estados de los dos
ejercicios (en pesos), detalle del activo y del pasivo por moneda, detalle de pasivos financieros y
costo de ventas. El resultado se guarda como .xlsx en ejemplos/formulario_bce/, con las formulas ya
calculadas por LibreOffice.

La correspondencia entre las variables del modelo y las celdas del formulario es la de
mapeo_form_bce.md.

Del ejercicio anterior el CSV trae solo los totales que usan las variaciones (activo corriente, activo,
pasivo, patrimonio, ingresos y resultados). Las partidas de ese ejercicio se reparten en la misma
proporcion que en el ejercicio actual, de modo que los totales coincidan con los del CSV.

Uso (desde la raiz del proyecto; necesita openpyxl y LibreOffice):
    python ejemplos/generar_formularios.py <formulario 2018 en blanco .xlsx>
"""
import csv
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

CARPETA = Path(__file__).parent
SALIDA = CARPETA / "formulario_bce"
EJEMPLOS = {
    "empresa_bueno": "Bueno",
    "empresa_aceptable": "Aceptable",
    "empresa_comprometido": "Comprometido",
    "empresa_critico": "Critico",
}
# Tipo de cambio interbancario aproximado (pesos por dolar) al cierre de cada mes
TIPO_DE_CAMBIO = {"2021-06": 43.6, "2021-12": 44.7, "2022-06": 39.9, "2022-09": 41.3}

AC, ANC, PC, PNC, PAT, ER = ("ACTIVO CORRIENTE", "ACTIVO NO CORRIENTE", "PASIVO CORRIENTE",
                             "PASIVO NO CORRIENTE", "PATRIMONIO", "ESTADO DEL RESULTADO INTEGRAL")

FINANCIEROS = ["Intereses Perdidos.", "Intereses Ganados", "Otros Gastos(+)/Ingresos(-) Financieros",
               "Diferencia de Cambio Perdida.", "Diferencia de Cambio Ganada", "+(pérd) -(gan) RDM",
               "- Otros Resultados- Extraordinarios.", "Impto. a la Renta", "- Otros Resultados No Operativos."]
ACTIVO_CTE = ["Caja", "Bancos", "Bancos M/E", "Inversiones Temporarias", "Depositos en Garantia",
              "Creditos Vtas.Plaza", "Creditos Vtas.Exp.", "Documentos a cobrar", "Otros Creditos",
              "Ctas. de Directores(6)", "Bienes de Cambio"]
ACTIVO_NO_CTE = ["Bienes de Uso", "Amort. Acumuladas", "Impuesto Diferido", "Otros Activos No Corrientes"]
PASIVO = ["Deudas Comercs", "Deudas Coms. MExt.", "Deudas BROU MNal.", "Deudas BROU MExt.",
          "Acreeds. Bancarios MNal.", "Acreeds. Bancarios MExt.", "Deudas Diversas", "Previsiones y Provisiones",
          "Ctas. de Directores (6)", "otras deudas financieras", "Deudas BROU MNal..1", "Deudas BROU MExt..1",
          "Acreeds. Bancarios", "Ctras Deudas Largo Plazo"]
PATRIMONIO = ["Capital", "Adelantos Irrevocs.", "Revaluaciones", "Reservas", "+(gan) -(pérd) Res Acums.",
              "- Dividendo Provisorio"]


def leer_csv(path):
    with open(path, encoding="utf-8") as fh:
        fila = next(csv.DictReader(fh))
    out = {}
    for k, v in fila.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = v
    return out


def escalar(valores, claves, total):
    """Reparte 'total' entre 'claves' en la proporcion de 'valores'; el redondeo va a la partida mayor."""
    base = sum(valores[k] for k in claves)
    if base == 0:
        return {k: 0.0 for k in claves}
    out = {k: float(round(valores[k] * total / base)) for k in claves}
    mayor = max(claves, key=lambda k: abs(out[k]))
    out[mayor] += total - sum(out.values())
    return out


def ejercicio_anterior(e):
    """Partidas del ejercicio anterior que reproducen los totales '(anterior)' del CSV."""
    a = lambda k: e[f"{k} (anterior)"]
    p = {}
    p.update(escalar(e, ACTIVO_CTE, a("Total Activo Corriente")))
    p.update(escalar(e, ACTIVO_NO_CTE, a("TOTAL ACTIVO") - a("Total Activo Corriente")))
    p.update(escalar(e, PASIVO, a("TOTAL PASIVO")))
    p["+(gan) -(pérd) Res Periodo"] = a("+(gan) -(pérd) Res Periodo")
    p.update(escalar(e, PATRIMONIO, a("TOTAL PATRIMONIO") - p["+(gan) -(pérd) Res Periodo"]))

    ingresos, netos = a("Total Ingresos Operativos"), a("Total Ingresos Operativos Netos")
    bruto, operativo, neto = a("Resultado Bruto"), a("Resultado Operativo"), a("Resultado Neto")
    p.update(escalar(e, ["Ventas Plaza", "Exportaciones"], ingresos))
    p["Ajustes/Bonificaciones s/Ventas"] = ingresos - netos
    p["Costo de lo Vendido"] = netos - bruto
    p["Amortizaciones"] = a("Resultado Sin Amortizaciones") - neto   # Sin Amortizaciones = Neto + Amortizaciones
    p["- Otros Gastos + Otros Ingresos"] = float(round(e["- Otros Gastos + Otros Ingresos"] * ingresos
                                                       / e["Total Ingresos Operativos"]))
    p["Gastos  Ad.y Ventas."] = bruto - operativo - p["Amortizaciones"] + p["- Otros Gastos + Otros Ingresos"]
    p.update(escalar(e, FINANCIEROS, operativo - neto))
    p["Resultado Neto"] = neto
    for k in ("Gastos  Ad.y Ventas.", "Costo de lo Vendido", "Amortizaciones"):
        if p[k] < 0:
            raise ValueError(f"{k} del ejercicio anterior queda negativo ({p[k]})")
    return p


def fin_de_mes(anio_mes):
    y, m = (int(x) for x in anio_mes.split("-"))
    siguiente = date(y + (m == 12), m % 12 + 1, 1)
    return siguiente - timedelta(days=1)


def bancos_brou(e):
    """Parte de los bancos que esta en el BROU (supuesto del ejemplo: 60% en pesos, 50% en dolares)."""
    return round(e["Bancos"] * 0.6), round(e["Bancos M/E"] * 0.5)


def llenar_estados(wb, e, col):
    """Estados de un ejercicio en pesos. En el resultado los costos y gastos van en positivo; los demas
    resultados con su signo (perdidas en negativo). Las previsiones y amortizaciones del activo en negativo."""
    def poner(hoja, fila, valor):
        if valor:
            wb[hoja][f"{col}{fila}"] = valor

    brou_mn, brou_me = bancos_brou(e)
    poner(AC, 9, e["Caja"])
    poner(AC, 10, brou_mn + brou_me)
    poner(AC, 11, e["Bancos"] + e["Bancos M/E"] - brou_mn - brou_me)
    poner(AC, 16, e["Inversiones Temporarias"])
    poner(AC, 25, e["Creditos Vtas.Plaza"])
    poner(AC, 26, e["Creditos Vtas.Exp."])
    poner(AC, 27, e["Documentos a cobrar"])
    poner(AC, 37, e["Depositos en Garantia"])
    poner(AC, 39, e["Ctas. de Directores(6)"])
    poner(AC, 41, e["Otros Creditos"])
    poner(AC, 48, e["Bienes de Cambio"])

    poner(ANC, 10, e["Impuesto Diferido"])
    poner(ANC, 34, e["Otros Activos No Corrientes"])
    poner(ANC, 43, e["Bienes de Uso"])
    poner(ANC, 45, e["Amort. Acumuladas"])                 # ya viene en negativo

    poner(PC, 9, e["Deudas Coms. MExt."])
    poner(PC, 12, e["Deudas Comercs"])
    poner(PC, 20, e["Deudas BROU MNal."] + e["Deudas BROU MExt."])
    poner(PC, 21, e["Acreeds. Bancarios MNal."] + e["Acreeds. Bancarios MExt."])
    poner(PC, 22, e["otras deudas financieras"])
    poner(PC, 40, e["Ctas. de Directores (6)"])
    poner(PC, 41, e["Deudas Diversas"])
    poner(PC, 47, e["Previsiones y Provisiones"])
    poner(PNC, 19, e["Deudas BROU MNal..1"] + e["Deudas BROU MExt..1"])
    poner(PNC, 20, e["Acreeds. Bancarios"])
    poner(PNC, 40, e["Ctras Deudas Largo Plazo"])

    legal = min(e["Reservas"], round(0.2 * e["Capital"]))
    poner(PAT, 9, e["Capital"])
    poner(PAT, 15, e["Adelantos Irrevocs."])
    poner(PAT, 18, e["Revaluaciones"])
    poner(PAT, 24, legal)
    poner(PAT, 25, e["Reservas"] - legal)
    poner(PAT, 29, e["+(gan) -(pérd) Res Acums."])
    poner(PAT, 30, e["+(gan) -(pérd) Res Periodo"])
    poner(PAT, 32, e["- Dividendo Provisorio"])           # en los datos ya viene en negativo

    contado = round(0.2 * e["Ventas Plaza"])
    poner(ER, 9, contado)
    poner(ER, 10, e["Ventas Plaza"] - contado)
    poner(ER, 12, e["Exportaciones"])
    poner(ER, 22, -e["Ajustes/Bonificaciones s/Ventas"])
    poner(ER, 27, e["Costo de lo Vendido"])
    poner(ER, 32, e["Gastos  Ad.y Ventas."])
    poner(ER, 33, e["Amortizaciones"])
    otros = e["- Otros Gastos + Otros Ingresos"]           # positivo = ingreso neto
    poner(ER, 40 if otros < 0 else 41, otros)
    # En los datos los resultados financieros se guardan como perdidas (+) y ganancias (-);
    # en el formulario van al reves
    poner(ER, 47, -e["Intereses Perdidos."])
    poner(ER, 48, -e["Intereses Ganados"])
    otros_fin = e["Otros Gastos(+)/Ingresos(-) Financieros"]
    poner(ER, 49 if otros_fin > 0 else 50, -otros_fin)
    poner(ER, 51, -e["Diferencia de Cambio Perdida."])
    poner(ER, 52, -e["Diferencia de Cambio Ganada"])
    poner(ER, 53, -e["+(pérd) -(gan) RDM"])
    poner(ER, 58, e["Impto. a la Renta"])                  # positivo = impuesto a pagar
    poner(ER, 63, -(e["- Otros Resultados- Extraordinarios."] + e["- Otros Resultados No Operativos."]))


def llenar_detalles(wb, e, tc, fecha):
    """Detalle del ejercicio actual en pesos: D = moneda extranjera traducida, F = moneda nacional."""
    da, dp, df = wb["DETALLE DEL ACTIVO"], wb["DETALLE DEL PASIVO"], wb["DETALLE DE PASIVOS FINANCIEROS"]
    brou_mn, brou_me = bancos_brou(e)
    da["F8"] = e["Caja"]
    da["D9"], da["F9"] = brou_me, brou_mn
    da["D10"], da["F10"] = e["Bancos M/E"] - brou_me, e["Bancos"] - brou_mn
    da["F15"] = e["Inversiones Temporarias"] or None
    da["F29"] = e["Creditos Vtas.Plaza"] or None
    da["D36"] = e["Creditos Vtas.Exp."] or None
    da["F39"] = e["Ctas. de Directores(6)"] or None
    da["B43"], da["F43"] = "Otros créditos y depósitos en garantía", e["Otros Creditos"] + e["Depositos en Garantia"]

    dp["F14"] = e["Deudas Comercs"] or None
    dp["D21"] = e["Deudas Coms. MExt."] or None
    dp["F24"] = e["Ctas. de Directores (6)"] or None
    dp["B29"], dp["F29"] = "Sueldos, cargas sociales y acreedores fiscales", e["Deudas Diversas"]
    dp["F30"] = e["Previsiones y Provisiones"] or None
    dp["F41"] = e["Ctras Deudas Largo Plazo"] or None

    origen = datetime(fecha.year - 1, fecha.month, 1)
    def deuda(fila, pesos, moneda_extranjera, banco=None, largo=False):
        if not pesos:
            return
        if banco:
            df[f"B{fila}"] = banco
        df[f"C{fila}"] = "Préstamo amortizable" if largo else "Vale"
        df[f"D{fila}"] = origen
        df[f"E{fila}"] = "60 meses" if largo else "12 meses"
        if moneda_extranjera:
            df[f"F{fila}"] = "U$S"
            df[f"G{fila}"] = round(pesos / tc, 2)            # capital en dolares; la hoja lo pasa a pesos
        else:
            df[f"F{fila}"] = "MN"
            df[f"G{fila}"] = pesos
    deuda(9, e["Deudas BROU MExt."], True)
    deuda(20, e["Deudas BROU MNal."], False)
    deuda(12, e["Acreeds. Bancarios MExt."], True, "Banco privado")
    deuda(22, e["Acreeds. Bancarios MNal."], False, "Banco privado")
    deuda(27, e["otras deudas financieras"], False)
    deuda(31, e["Deudas BROU MExt..1"], True, largo=True)
    deuda(42, e["Deudas BROU MNal..1"], False, largo=True)
    deuda(44, e["Acreeds. Bancarios"], False, "Banco privado", largo=True)


def llenar_costo(wb, e, ant):
    """Costo de ventas como mercaderia de reventa: existencia inicial + compras - existencia final."""
    c = wb["ANEXO"]
    compras = e["Costo de lo Vendido"] - ant["Bienes de Cambio"] + e["Bienes de Cambio"]
    if compras < 0:
        raise ValueError("las compras del ejercicio quedan negativas")
    c["D18"], c["E18"], c["I18"] = ant["Bienes de Cambio"], compras, e["Bienes de Cambio"]


def generar(plantilla, nombre, banda):
    e = leer_csv(CARPETA / f"{nombre}.csv")
    ant = ejercicio_anterior(e)
    fecha = fin_de_mes(e["FECHA_CIERRE"])
    tc = TIPO_DE_CAMBIO[e["FECHA_CIERRE"]]

    wb = load_workbook(plantilla)
    ig = wb["INFORMACIÓN GENERAL"]
    ig["C4"] = f"EMPRESA DE EJEMPLO - {banda.upper()}"
    ig["C5"] = e["TIPO_SOCIEDAD"]
    ig["C9"] = datetime(fecha.year, fecha.month, fecha.day)
    ig["C10"] = e["ACTIVIDAD_ECONOMICA"]
    empleados = int(e["NUMERO_EMPLEADOS"])
    ig["E13"], ig["I13"] = empleados - empleados // 3, empleados // 3
    ig["C16"] = "X"                                       # libros certificados
    ig["F16"], ig["F17"] = "$", tc                        # moneda de los estados y tipo de cambio de cierre
    ig["G37"] = "X"                                       # no integra grupo economico

    llenar_estados(wb, e, "G")
    llenar_estados(wb, ant, "D")
    llenar_detalles(wb, e, tc, fecha)
    llenar_costo(wb, e, ant)

    SALIDA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        xlsx = Path(tmp) / f"{nombre}.xlsx"
        wb.save(xlsx)
        # LibreOffice recalcula las formulas y deja los valores guardados en el .xlsx
        subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx:Calc MS Excel 2007 XML",
                        "--outdir", str(SALIDA), str(xlsx)], check=True, capture_output=True)
    return SALIDA / f"{nombre}.xlsx"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for nombre, banda in EJEMPLOS.items():
        print(generar(sys.argv[1], nombre, banda))
