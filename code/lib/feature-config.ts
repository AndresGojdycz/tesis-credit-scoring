/**
 * Feature configuration for the credit scoring model.
 * Maps form fields to the exact feature names expected by the trained model
 * (as listed in credit-scoring-api/artifacts/feature_names.txt).
 */

export type FeatureCategory =
  | "activo_corriente"
  | "activo_no_corriente"
  | "pasivo_corriente"
  | "pasivo_no_corriente"
  | "patrimonio"
  | "resultados"

export interface FieldConfig {
  key: string
  apiName: string
  label: string
  category: FeatureCategory
}

export const CATEGORY_LABELS: Record<FeatureCategory, string> = {
  activo_corriente: "Activo Corriente",
  activo_no_corriente: "Activo No Corriente",
  pasivo_corriente: "Pasivo Corriente",
  pasivo_no_corriente: "Pasivo No Corriente",
  patrimonio: "Patrimonio",
  resultados: "Estado de Resultados",
}

export const CATEGORY_ORDER: FeatureCategory[] = [
  "activo_corriente",
  "activo_no_corriente",
  "pasivo_corriente",
  "pasivo_no_corriente",
  "patrimonio",
  "resultados",
]

/**
 * Raw balance-sheet features used by the model, organized by category.
 * apiName must match feature_names.txt EXACTLY (same spelling, accents, spacing).
 * Los campos `+(gan) -(pérd) ...` van con tilde: en el notebook, agro se renombra
 * igual que empresas, asi que el modelo tiene una sola columna por concepto.
 */
export const RAW_FEATURES: FieldConfig[] = [
  // ── Activo Corriente (features 1-13) ──
  { key: "caja", apiName: "Caja", label: "Caja", category: "activo_corriente" },
  { key: "bancos", apiName: "Bancos", label: "Bancos", category: "activo_corriente" },
  { key: "bancos_me", apiName: "Bancos M/E", label: "Bancos M/E", category: "activo_corriente" },
  { key: "subtotal_disponibilidades", apiName: "Sub-total - Disponibilidades", label: "Sub-total Disponibilidades", category: "activo_corriente" },
  { key: "inversiones_temporarias", apiName: "Inversiones Temporarias", label: "Inversiones Temporarias", category: "activo_corriente" },
  { key: "depositos_garantia", apiName: "Depositos en Garantia", label: "Depositos en Garantia", category: "activo_corriente" },
  { key: "creditos_vtas_plaza", apiName: "Creditos Vtas.Plaza", label: "Creditos Vtas. Plaza", category: "activo_corriente" },
  { key: "creditos_vtas_exp", apiName: "Creditos Vtas.Exp.", label: "Creditos Vtas. Exp.", category: "activo_corriente" },
  { key: "documentos_cobrar", apiName: "Documentos a cobrar", label: "Documentos a cobrar", category: "activo_corriente" },
  { key: "otros_creditos", apiName: "Otros Creditos", label: "Otros Creditos", category: "activo_corriente" },
  { key: "ctas_directores_activo", apiName: "Ctas. de Directores(6)", label: "Ctas. de Directores (Activo)", category: "activo_corriente" },
  { key: "impuestos_adelantados", apiName: "Impuestos Adelantados", label: "Impuestos Adelantados", category: "activo_corriente" },
  { key: "bienes_cambio", apiName: "Bienes de Cambio", label: "Bienes de Cambio", category: "activo_corriente" },
  { key: "total_activo_corriente", apiName: "Total Activo Corriente", label: "Total Activo Corriente", category: "activo_corriente" },

  // ── Activo No Corriente (features 14-19) ──
  { key: "bienes_uso", apiName: "Bienes de Uso", label: "Bienes de Uso", category: "activo_no_corriente" },
  { key: "amort_acumuladas", apiName: "Amort. Acumuladas", label: "Amort. Acumuladas", category: "activo_no_corriente" },
  { key: "impuesto_diferido", apiName: "Impuesto Diferido", label: "Impuesto Diferido", category: "activo_no_corriente" },
  { key: "intangibles", apiName: "Intangibles", label: "Intangibles", category: "activo_no_corriente" },
  { key: "bienes_cambio_lp", apiName: "Bienes de Cambio L/P", label: "Bienes de Cambio (LP)", category: "activo_no_corriente" },
  { key: "otros_activos_no_corrientes", apiName: "Otros Activos No Corrientes", label: "Otros Activos No Corrientes", category: "activo_no_corriente" },
  { key: "total_activo_no_corriente", apiName: "Total Activo no Corriente", label: "Total Activo No Corriente", category: "activo_no_corriente" },
  { key: "total_activo", apiName: "TOTAL ACTIVO", label: "TOTAL ACTIVO", category: "activo_no_corriente" },

  // ── Pasivo Corriente (features 20-30) ──
  { key: "deudas_comercs", apiName: "Deudas Comercs", label: "Deudas Comerciales", category: "pasivo_corriente" },
  { key: "deudas_coms_mext", apiName: "Deudas Coms. MExt.", label: "Deudas Comerciales M/E", category: "pasivo_corriente" },
  { key: "deudas_brou_mnal", apiName: "Deudas BROU MNal.", label: "Deudas BROU M/N", category: "pasivo_corriente" },
  { key: "deudas_brou_mext", apiName: "Deudas BROU MExt.", label: "Deudas BROU M/E", category: "pasivo_corriente" },
  { key: "acreeds_bancarios_mnal", apiName: "Acreeds. Bancarios MNal.", label: "Acreedores Bancarios M/N", category: "pasivo_corriente" },
  { key: "acreeds_bancarios_mext", apiName: "Acreeds. Bancarios MExt.", label: "Acreedores Bancarios M/E", category: "pasivo_corriente" },
  { key: "documentos_pagar", apiName: "Documentos a Pagar", label: "Documentos a Pagar", category: "pasivo_corriente" },
  { key: "deudas_diversas", apiName: "Deudas Diversas", label: "Deudas Diversas", category: "pasivo_corriente" },
  { key: "previsiones_provisiones", apiName: "Previsiones y Provisiones", label: "Previsiones y Provisiones", category: "pasivo_corriente" },
  { key: "ctas_directores_pasivo", apiName: "Ctas. de Directores (6)", label: "Ctas. de Directores (Pasivo)", category: "pasivo_corriente" },
  { key: "otras_deudas_financieras", apiName: "otras deudas financieras", label: "Otras Deudas Financieras", category: "pasivo_corriente" },
  { key: "total_pasivo_corriente", apiName: "Total Pasivo Corriente", label: "Total Pasivo Corriente", category: "pasivo_corriente" },

  // ── Pasivo No Corriente (features 31-36) ──
  { key: "deudas_brou_mnal_lp", apiName: "Deudas BROU MNal..1", label: "Deudas BROU M/N (LP)", category: "pasivo_no_corriente" },
  { key: "deudas_brou_mext_lp", apiName: "Deudas BROU MExt..1", label: "Deudas BROU M/E (LP)", category: "pasivo_no_corriente" },
  { key: "acreeds_bancarios_lp", apiName: "Acreeds. Bancarios", label: "Acreedores Bancarios (LP)", category: "pasivo_no_corriente" },
  { key: "deutas_otros_bancos_me_lp", apiName: "Deutas Otros Bancos M/E", label: "Deudas Otros Bancos M/E (LP)", category: "pasivo_no_corriente" },
  { key: "ctras_deudas_largo_plazo", apiName: "Ctras Deudas Largo Plazo", label: "Otras Deudas Largo Plazo", category: "pasivo_no_corriente" },
  { key: "total_pasivo_no_corriente", apiName: "Total Pasivo No Corriente", label: "Total Pasivo No Corriente", category: "pasivo_no_corriente" },
  { key: "total_pasivo", apiName: "TOTAL PASIVO", label: "TOTAL PASIVO", category: "pasivo_no_corriente" },

  // ── Patrimonio (features 37-47) ──
  { key: "capital", apiName: "Capital", label: "Capital", category: "patrimonio" },
  { key: "adelantos_irrevocs", apiName: "Adelantos Irrevocs.", label: "Adelantos Irrevocables", category: "patrimonio" },
  { key: "revaluaciones", apiName: "Revaluaciones", label: "Revaluaciones", category: "patrimonio" },
  { key: "reservas", apiName: "Reservas", label: "Reservas", category: "patrimonio" },
  { key: "gan_perd_aj_infl", apiName: "+(gan) -(pérd) Aj por Infl", label: "Ajuste por Inflacion", category: "patrimonio" },
  { key: "gan_perd_res_acums", apiName: "+(gan) -(pérd) Res Acums.", label: "Resultados Acumulados", category: "patrimonio" },
  { key: "gan_perd_res_periodo", apiName: "+(gan) -(pérd) Res Periodo", label: "Resultado del Periodo", category: "patrimonio" },
  { key: "dividendo_provisorio", apiName: "- Dividendo Provisorio", label: "Dividendo Provisorio", category: "patrimonio" },
  { key: "ajustes_patrim", apiName: "Ajustes al Patrim.", label: "Ajustes al Patrimonio", category: "patrimonio" },
  { key: "ajustes_activos_pasivos", apiName: "Ajustes Activos/Pasivos", label: "Ajustes Activos/Pasivos", category: "patrimonio" },
  { key: "ajuste_resul_neto_contable", apiName: "Ajuste Resul. Neto Contable", label: "Ajuste Resul. Neto Contable", category: "patrimonio" },
  { key: "total_patrimonio", apiName: "TOTAL PATRIMONIO", label: "TOTAL PATRIMONIO", category: "patrimonio" },
  { key: "total_pasivo_y_patrimonio", apiName: "TOTAL PASIVO Y PATRIMONIO", label: "TOTAL PASIVO Y PATRIMONIO", category: "patrimonio" },

  // ── Estado de Resultados (features 48-70) ──
  { key: "ventas_plaza", apiName: "Ventas Plaza", label: "Ventas Plaza", category: "resultados" },
  { key: "exportaciones", apiName: "Exportaciones", label: "Exportaciones", category: "resultados" },
  { key: "resultado_tenencia_nic41", apiName: "Resultado por Tenencia - NIC 41 -", label: "Resultado por Tenencia (NIC 41)", category: "resultados" },
  { key: "resultado_tenencia_agri_nic41", apiName: "Resultado por Tenencia -Agricultura-NIC-41", label: "Resultado por Tenencia (Agricultura NIC 41)", category: "resultados" },
  { key: "resultado_tenencia_ganaderia_nic41", apiName: "Resultado por Tenencia -Ganaderia-NIC-41", label: "Resultado por Tenencia (Ganaderia NIC 41)", category: "resultados" },
  { key: "total_ingresos_operativos", apiName: "Total Ingresos Operativos", label: "Total Ingresos Operativos", category: "resultados" },
  { key: "ajustes_bonificaciones", apiName: "Ajustes/Bonificaciones s/Ventas", label: "Ajustes/Bonificaciones s/Ventas", category: "resultados" },
  { key: "total_ingresos_operativos_netos", apiName: "Total Ingresos Operativos Netos", label: "Total Ingresos Operativos Netos", category: "resultados" },
  { key: "costo_vendido", apiName: "Costo de lo Vendido", label: "Costo de lo Vendido", category: "resultados" },
  { key: "resultado_bruto", apiName: "Resultado Bruto", label: "Resultado Bruto", category: "resultados" },
  { key: "amortizaciones", apiName: "Amortizaciones", label: "Amortizaciones", category: "resultados" },
  { key: "gastos_ad_ventas", apiName: "Gastos  Ad.y Ventas.", label: "Gastos Admin. y Ventas", category: "resultados" },
  { key: "otros_gastos_ingresos", apiName: "- Otros Gastos + Otros Ingresos", label: "Otros Gastos / Otros Ingresos", category: "resultados" },
  { key: "otros_res_no_operativos_extra", apiName: "- Otros Res.  No Operativos", label: "Otros Res. No Operativos (extra)", category: "resultados" },
  { key: "resultado_operativo", apiName: "Resultado Operativo", label: "Resultado Operativo", category: "resultados" },
  { key: "intereses_perdidos", apiName: "Intereses Perdidos.", label: "Intereses Perdidos", category: "resultados" },
  { key: "intereses_ganados", apiName: "Intereses Ganados", label: "Intereses Ganados", category: "resultados" },
  { key: "otros_gastos_ingresos_fin", apiName: "Otros Gastos(+)/Ingresos(-) Financieros", label: "Otros Gastos/Ingresos Financieros", category: "resultados" },
  { key: "dif_cambio_perdida", apiName: "Diferencia de Cambio Perdida.", label: "Diferencia de Cambio Perdida", category: "resultados" },
  { key: "dif_cambio_ganada", apiName: "Diferencia de Cambio Ganada", label: "Diferencia de Cambio Ganada", category: "resultados" },
  { key: "perd_gan_rdm", apiName: "+(pérd) -(gan) RDM", label: "Resultado por Desmon. (RDM)", category: "resultados" },
  { key: "otros_resultados_extraordinarios", apiName: "- Otros Resultados- Extraordinarios.", label: "Otros Resultados Extraordinarios", category: "resultados" },
  { key: "impuestos_total", apiName: "Impuestos", label: "Impuestos (total)", category: "resultados" },
  { key: "impto_renta", apiName: "Impto. a la Renta", label: "Impuesto a la Renta", category: "resultados" },
  { key: "otros_resultados_no_operativos", apiName: "- Otros Resultados No Operativos.", label: "Otros Resultados No Operativos", category: "resultados" },
  { key: "resultado_neto", apiName: "Resultado Neto", label: "Resultado Neto", category: "resultados" },
  { key: "resultado_sin_amortizaciones", apiName: "Resultado Sin Amortizaciones", label: "Resultado Sin Amortizaciones", category: "resultados" },
]

// ── Accounting Validation ──

export interface ValidationRule {
  totalKey: string
  totalLabel: string
  componentKeys: string[]
  subtractKeys?: string[]
}

export interface ValidationError {
  rule: string
  expected: number
  actual: number
}

/**
 * Rules defining which component fields should sum to each total field.
 * Keys reference the `key` property from RAW_FEATURES (form field names).
 */
export const VALIDATION_RULES: ValidationRule[] = [
  {
    totalKey: "subtotal_disponibilidades",
    totalLabel: "Sub-total Disponibilidades",
    componentKeys: ["caja", "bancos", "bancos_me"],
  },
  {
    totalKey: "total_activo_corriente",
    totalLabel: "Total Activo Corriente",
    componentKeys: [
      "subtotal_disponibilidades",
      "inversiones_temporarias",
      "depositos_garantia",
      "creditos_vtas_plaza",
      "creditos_vtas_exp",
      "documentos_cobrar",
      "otros_creditos",
      "ctas_directores_activo",
      "bienes_cambio",
    ],
  },
  {
    totalKey: "total_activo_no_corriente",
    totalLabel: "Total Activo No Corriente",
    componentKeys: [
      "bienes_uso",
      "amort_acumuladas",
      "impuesto_diferido",
      "otros_activos_no_corrientes",
    ],
  },
  {
    totalKey: "total_activo",
    totalLabel: "TOTAL ACTIVO",
    componentKeys: ["total_activo_corriente", "total_activo_no_corriente"],
  },
  {
    totalKey: "total_pasivo_corriente",
    totalLabel: "Total Pasivo Corriente",
    componentKeys: [
      "deudas_comercs",
      "deudas_coms_mext",
      "deudas_brou_mnal",
      "deudas_brou_mext",
      "acreeds_bancarios_mnal",
      "acreeds_bancarios_mext",
      "deudas_diversas",
      "previsiones_provisiones",
      "ctas_directores_pasivo",
      "otras_deudas_financieras",
    ],
  },
  {
    totalKey: "total_pasivo_no_corriente",
    totalLabel: "Total Pasivo No Corriente",
    componentKeys: [
      "deudas_brou_mnal_lp",
      "deudas_brou_mext_lp",
      "acreeds_bancarios_lp",
      "ctras_deudas_largo_plazo",
    ],
  },
  {
    totalKey: "total_pasivo",
    totalLabel: "TOTAL PASIVO",
    componentKeys: ["total_pasivo_corriente", "total_pasivo_no_corriente"],
  },
  {
    totalKey: "total_patrimonio",
    totalLabel: "TOTAL PATRIMONIO",
    componentKeys: [
      "capital",
      "adelantos_irrevocs",
      "revaluaciones",
      "reservas",
      "gan_perd_aj_infl",
      "gan_perd_res_acums",
      "gan_perd_res_periodo",
      "ajustes_patrim",
    ],
    subtractKeys: ["dividendo_provisorio"],
  },
  {
    totalKey: "total_pasivo_y_patrimonio",
    totalLabel: "TOTAL PASIVO Y PATRIMONIO",
    componentKeys: ["total_pasivo", "total_patrimonio"],
  },
]

/**
 * The fundamental accounting equation: TOTAL ACTIVO = TOTAL PASIVO + TOTAL PATRIMONIO.
 * Checked separately since it compares two independently-computed totals.
 */
export const ACCOUNTING_EQUATION = {
  leftKey: "total_activo",
  leftLabel: "TOTAL ACTIVO",
  rightKeys: ["total_pasivo", "total_patrimonio"],
  rightLabel: "TOTAL PASIVO + TOTAL PATRIMONIO",
}

/**
 * Validates that accounting sums are internally consistent.
 * A rule only fires when the total AND at least one component have numeric values.
 * Tolerancia: 0,01 % del total (minimo 0,5), para admitir los redondeos de un balance en dolares pasado a
 * pesos (en un formulario real del BROU, la ecuacion patrimonial difiere en unas decenas de pesos).
 */
export function validateAccountingSums(
  data: Record<string, number | undefined>,
): ValidationError[] {
  const errors: ValidationError[] = []
  const tolerancia = (total: number) => Math.max(0.5, Math.abs(total) * 1e-4)

  for (const rule of VALIDATION_RULES) {
    const totalVal = data[rule.totalKey]
    if (totalVal == null || isNaN(totalVal)) continue

    const addComponents = rule.componentKeys
      .map((k) => data[k])
      .filter((v): v is number => v != null && !isNaN(v))

    const subComponents = (rule.subtractKeys ?? [])
      .map((k) => data[k])
      .filter((v): v is number => v != null && !isNaN(v))

    // Only validate if at least one component is filled
    if (addComponents.length === 0 && subComponents.length === 0) continue

    const expected =
      addComponents.reduce((sum, v) => sum + v, 0) -
      subComponents.reduce((sum, v) => sum + v, 0)

    if (Math.abs(totalVal - expected) > tolerancia(totalVal)) {
      errors.push({
        rule: rule.totalLabel,
        expected,
        actual: totalVal,
      })
    }
  }

  // Fundamental accounting equation
  const eq = ACCOUNTING_EQUATION
  const leftVal = data[eq.leftKey]
  const rightVals = eq.rightKeys
    .map((k) => data[k])
    .filter((v): v is number => v != null && !isNaN(v))

  if (leftVal != null && !isNaN(leftVal) && rightVals.length > 0) {
    const rightSum = rightVals.reduce((sum, v) => sum + v, 0)
    if (Math.abs(leftVal - rightSum) > tolerancia(leftVal)) {
      errors.push({
        rule: `${eq.leftLabel} = ${eq.rightLabel}`,
        expected: rightSum,
        actual: leftVal,
      })
    }
  }

  return errors
}

/**
 * Safe division replicating the notebook's safe_ratio() function.
 * Returns undefined when division is impossible (missing values or zero denominator).
 */
function safeRatio(
  numerator: number | undefined,
  denominator: number | undefined,
): number | undefined {
  if (numerator == null || denominator == null || denominator === 0) return undefined
  const result = numerator / denominator
  if (!isFinite(result)) return undefined
  return result
}

/**
 * Calcula algunos ratios desde los valores del formulario (mismas formulas que el
 * notebook). El API completa los ratios que falten y primera_observacion
 * (credit-scoring-api/app/feature_engineering.py), asi que este calculo es opcional.
 *
 * @param raw - Object keyed by apiName (feature_names.txt names) with raw values
 * @returns Object with computed engineered feature values
 */
export function computeEngineeredFeatures(
  raw: Record<string, number | undefined>,
): Record<string, number | undefined> {
  const totalActivo = raw["TOTAL ACTIVO"]
  const totalPasivo = raw["TOTAL PASIVO"]
  const totalPatrimonio = raw["TOTAL PATRIMONIO"]
  const resultadoNeto = raw["Resultado Neto"]
  const totalIngresosBrutos = raw["Total Ingresos Operativos"]
  const interesesPerdidos = raw["Intereses Perdidos."]
  const resultadoOperativo = raw["Resultado Operativo"]
  const importeMn = raw["IMPORTE_MN"]

  return {
    ROA: safeRatio(resultadoNeto, totalActivo),
    ROE: safeRatio(resultadoNeto, totalPatrimonio),
    Relacion_deuda_patrimonio: safeRatio(totalPasivo, totalPatrimonio),
    Multiplicador: safeRatio(totalActivo, totalPatrimonio),
    Cobertura_de_intereses: safeRatio(resultadoOperativo, interesesPerdidos),

    // Exposicion crediticia relativa (Central de Riesgos): el modelo usa los
    // ratios, no el importe crudo (ver notebooks/funciones.py)
    Importe_sobre_Ventas: safeRatio(importeMn, totalIngresosBrutos),
    Importe_sobre_Patrimonio: safeRatio(importeMn, totalPatrimonio),
  }
}

/** Sufijo de las columnas del archivo con el balance del año anterior (ej: "TOTAL ACTIVO (anterior)"). */
export const SUFIJO_ANTERIOR = " (anterior)"

/** Partidas del balance anterior que se necesitan para las variaciones temporales. */
export const PARTIDAS_ANTERIOR = [
  "Resultado Operativo",
  "Resultado Sin Amortizaciones",
  "Resultado Neto",
  "+(gan) -(pérd) Res Periodo",
  "Resultado Bruto",
  "Total Ingresos Operativos",
  "Total Ingresos Operativos Netos",
  "Total Activo Corriente",
  "TOTAL ACTIVO",
  "TOTAL PASIVO",
  "TOTAL PATRIMONIO",
]

/** Partidas y ratios que entran en las variaciones, como en notebooks/funciones.py (lag_items). */
function valoresParaVariacion(b: Record<string, number | undefined>): Record<string, number | undefined> {
  // Ingresos brutos y netos: si falta uno, se usa el otro (mismo criterio que el entrenamiento y el API)
  const brutos = b["Total Ingresos Operativos"] ?? b["Total Ingresos Operativos Netos"]
  const netos = b["Total Ingresos Operativos Netos"] ?? b["Total Ingresos Operativos"]
  return {
    Res_Op: b["Resultado Operativo"],
    Res_SinAmort: b["Resultado Sin Amortizaciones"],
    Res_Neto: b["Resultado Neto"],
    MgnOp: safeRatio(b["Resultado Operativo"], brutos),
    ROE: safeRatio(b["Resultado Neto"], b["TOTAL PATRIMONIO"]),
    Res_Periodo: b["+(gan) -(pérd) Res Periodo"],
    MgnNeto: safeRatio(b["Resultado Neto"], netos),
    MgnBruto: safeRatio(b["Resultado Bruto"], brutos),
    ROA: safeRatio(b["Resultado Neto"], b["TOTAL ACTIVO"]),
    ActCte: b["Total Activo Corriente"],
    Activo: b["TOTAL ACTIVO"],
    Pasivo: b["TOTAL PASIVO"],
    Patrimonio: b["TOTAL PATRIMONIO"],
  }
}

/**
 * Variaciones temporales (delta_*) entre el balance actual y el del año anterior, con la misma
 * definicion del entrenamiento: valor actual menos valor anterior, de la partida o del ratio.
 * Si falta alguno de los dos valores, esa variacion no se calcula (el API la imputa).
 */
export function computeTemporalVariations(
  actual: Record<string, number | undefined>,
  anterior: Record<string, number | undefined>,
): Record<string, number> {
  const a = valoresParaVariacion(actual)
  const p = valoresParaVariacion(anterior)
  const out: Record<string, number> = {}
  for (const [alias, va] of Object.entries(a)) {
    const vp = p[alias]
    if (va != null && vp != null && isFinite(va) && isFinite(vp)) {
      out[`delta_${alias}`] = va - vp
    }
  }
  return out
}
