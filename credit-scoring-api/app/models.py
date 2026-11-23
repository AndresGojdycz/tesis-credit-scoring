from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import warnings

class CompanyFeatures(BaseModel):
    """
    Schema de entrada del modelo de credit scoring — GENERADO desde
    artifacts/feature_names.txt (fuente de verdad del modelo desplegado).

    Todas las features son opcionales: las faltantes se imputan en el servidor
    con las medianas de entrenamiento serializadas junto al modelo, y la
    respuesta incluye `warnings` con el detalle de lo imputado.

    Las variables cualitativas (TIPO_SOCIEDAD, ACTIVIDAD_ECONOMICA,
    tamaño_EMPRESA, SECTOR) se envian como texto y el servidor las codifica
    one-hot con las categorias derivadas del propio modelo.
    """

    # ========================================================================
    # PARTIDAS CONTABLES BCU (balance y estado de resultados, nombres exactos
    # del plan de cuentas de la fuente — ver diccionario.md)
    # ========================================================================
    resultado_neto: Optional[float] = Field(None, alias="Resultado Neto")
    gan_perd_res_periodo: Optional[float] = Field(None, alias="+(gan) -(pérd) Res Periodo")
    resultado_sin_amortizaciones: Optional[float] = Field(None, alias="Resultado Sin Amortizaciones")
    resultado_operativo: Optional[float] = Field(None, alias="Resultado Operativo")
    impto_a_la_renta: Optional[float] = Field(None, alias="Impto. a la Renta")
    total_patrimonio: Optional[float] = Field(None, alias="TOTAL PATRIMONIO")
    gan_perd_res_acums: Optional[float] = Field(None, alias="+(gan) -(pérd) Res Acums.")
    sub_total_disponibilidades: Optional[float] = Field(None, alias="Sub-total - Disponibilidades")
    ajuste_resul_neto_contable: Optional[float] = Field(None, alias="Ajuste Resul. Neto Contable")
    total_activo: Optional[float] = Field(None, alias="TOTAL ACTIVO")
    total_pasivo_y_patrimonio: Optional[float] = Field(None, alias="TOTAL PASIVO Y PATRIMONIO")
    bienes_de_cambio_l_p: Optional[float] = Field(None, alias="Bienes de Cambio L/P")
    intereses_ganados: Optional[float] = Field(None, alias="Intereses Ganados")
    bancos_m_e: Optional[float] = Field(None, alias="Bancos M/E")
    ajustes_activos_pasivos: Optional[float] = Field(None, alias="Ajustes Activos/Pasivos")
    otros_gastos_otros_ingresos: Optional[float] = Field(None, alias="- Otros Gastos + Otros Ingresos")
    amort_acumuladas: Optional[float] = Field(None, alias="Amort. Acumuladas")
    resultado_bruto: Optional[float] = Field(None, alias="Resultado Bruto")
    resultado_por_tenencia_ganaderia_nic_41: Optional[float] = Field(None, alias="Resultado por Tenencia -Ganaderia-NIC-41")
    total_activo_corriente: Optional[float] = Field(None, alias="Total Activo Corriente")
    capital: Optional[float] = Field(None, alias="Capital")
    amortizaciones: Optional[float] = Field(None, alias="Amortizaciones")
    total_pasivo_no_corriente: Optional[float] = Field(None, alias="Total Pasivo No Corriente")
    deudas_diversas: Optional[float] = Field(None, alias="Deudas Diversas")
    dividendo_provisorio: Optional[float] = Field(None, alias="- Dividendo Provisorio")
    ajustes_al_patrim: Optional[float] = Field(None, alias="Ajustes al Patrim.")
    acreeds_bancarios_mext: Optional[float] = Field(None, alias="Acreeds. Bancarios MExt.")
    bancos: Optional[float] = Field(None, alias="Bancos")
    ajustes_bonificaciones_s_ventas: Optional[float] = Field(None, alias="Ajustes/Bonificaciones s/Ventas")
    total_pasivo_corriente: Optional[float] = Field(None, alias="Total Pasivo Corriente")
    bienes_de_cambio: Optional[float] = Field(None, alias="Bienes de Cambio")
    otros_res_no_operativos: Optional[float] = Field(None, alias="- Otros Res.  No Operativos")
    impuestos_adelantados: Optional[float] = Field(None, alias="Impuestos Adelantados")
    impuestos: Optional[float] = Field(None, alias="Impuestos")
    total_pasivo: Optional[float] = Field(None, alias="TOTAL PASIVO")
    documentos_a_cobrar: Optional[float] = Field(None, alias="Documentos a cobrar")
    otros_gastos_ingresos_financieros: Optional[float] = Field(None, alias="Otros Gastos(+)/Ingresos(-) Financieros")
    caja: Optional[float] = Field(None, alias="Caja")
    gastos_ad_y_ventas: Optional[float] = Field(None, alias="Gastos  Ad.y Ventas.")
    deudas_brou_mnal_1: Optional[float] = Field(None, alias="Deudas BROU MNal..1")
    depositos_en_garantia: Optional[float] = Field(None, alias="Depositos en Garantia")
    costo_de_lo_vendido: Optional[float] = Field(None, alias="Costo de lo Vendido")
    perd_gan_rdm: Optional[float] = Field(None, alias="+(pérd) -(gan) RDM")
    revaluaciones: Optional[float] = Field(None, alias="Revaluaciones")
    intereses_perdidos: Optional[float] = Field(None, alias="Intereses Perdidos.")
    acreeds_bancarios: Optional[float] = Field(None, alias="Acreeds. Bancarios")
    intangibles: Optional[float] = Field(None, alias="Intangibles")
    otros_creditos: Optional[float] = Field(None, alias="Otros Creditos")
    otros_resultados_extraordinarios: Optional[float] = Field(None, alias="- Otros Resultados- Extraordinarios.")
    resultado_por_tenencia_nic_41: Optional[float] = Field(None, alias="Resultado por Tenencia - NIC 41 -")
    resultado_por_tenencia_agricultura_nic_41: Optional[float] = Field(None, alias="Resultado por Tenencia -Agricultura-NIC-41")
    documentos_a_pagar: Optional[float] = Field(None, alias="Documentos a Pagar")
    deudas_brou_mext: Optional[float] = Field(None, alias="Deudas BROU MExt.")
    deutas_otros_bancos_m_e: Optional[float] = Field(None, alias="Deutas Otros Bancos M/E")
    reservas: Optional[float] = Field(None, alias="Reservas")
    ctas_de_directores_6: Optional[float] = Field(None, alias="Ctas. de Directores(6)")
    deudas_coms_mext: Optional[float] = Field(None, alias="Deudas Coms. MExt.")
    diferencia_de_cambio_ganada: Optional[float] = Field(None, alias="Diferencia de Cambio Ganada")
    total_ingresos_operativos: Optional[float] = Field(None, alias="Total Ingresos Operativos")
    gan_perd_aj_por_infl: Optional[float] = Field(None, alias="+(gan) -(pérd) Aj por Infl")
    deudas_brou_mext_1: Optional[float] = Field(None, alias="Deudas BROU MExt..1")
    impuesto_diferido: Optional[float] = Field(None, alias="Impuesto Diferido")
    total_activo_no_corriente: Optional[float] = Field(None, alias="Total Activo no Corriente")
    total_ingresos_operativos_netos: Optional[float] = Field(None, alias="Total Ingresos Operativos Netos")
    deudas_brou_mnal: Optional[float] = Field(None, alias="Deudas BROU MNal.")
    creditos_vtas_exp: Optional[float] = Field(None, alias="Creditos Vtas.Exp.")
    diferencia_de_cambio_perdida: Optional[float] = Field(None, alias="Diferencia de Cambio Perdida.")
    ventas_plaza: Optional[float] = Field(None, alias="Ventas Plaza")
    inversiones_temporarias: Optional[float] = Field(None, alias="Inversiones Temporarias")
    bienes_de_uso: Optional[float] = Field(None, alias="Bienes de Uso")
    ctas_de_directores_6_2: Optional[float] = Field(None, alias="Ctas. de Directores (6)")
    acreeds_bancarios_mnal: Optional[float] = Field(None, alias="Acreeds. Bancarios MNal.")
    otros_activos_no_corrientes: Optional[float] = Field(None, alias="Otros Activos No Corrientes")
    ctras_deudas_largo_plazo: Optional[float] = Field(None, alias="Ctras Deudas Largo Plazo")
    creditos_vtas_plaza: Optional[float] = Field(None, alias="Creditos Vtas.Plaza")
    previsiones_y_provisiones: Optional[float] = Field(None, alias="Previsiones y Provisiones")
    deudas_comercs: Optional[float] = Field(None, alias="Deudas Comercs")
    otras_deudas_financieras: Optional[float] = Field(None, alias="otras deudas financieras")
    otros_resultados_no_operativos: Optional[float] = Field(None, alias="- Otros Resultados No Operativos.")
    exportaciones: Optional[float] = Field(None, alias="Exportaciones")

    # ========================================================================
    # RATIOS FINANCIEROS DERIVADOS (safe_ratio; el frontend los calcula a partir
    # de las partidas — tambien pueden enviarse directamente)
    # ========================================================================
    roe: Optional[float] = Field(None, alias="ROE")
    margen_neto: Optional[float] = Field(None, alias="Margen_Neto")
    roa: Optional[float] = Field(None, alias="ROA")
    margen_operativo: Optional[float] = Field(None, alias="Margen_Operativo")
    ratio_corriente: Optional[float] = Field(None, alias="Ratio_Corriente")
    ratio_patrimonio: Optional[float] = Field(None, alias="Ratio_Patrimonio")
    deuda_sobre_activos: Optional[float] = Field(None, alias="Deuda_sobre_Activos")
    relacion_deuda_patrimonio: Optional[float] = Field(None, alias="Relacion_deuda_patrimonio")
    ratio_efectivo: Optional[float] = Field(None, alias="Ratio_Efectivo")
    multiplicador: Optional[float] = Field(None, alias="Multiplicador")
    cobertura_de_intereses: Optional[float] = Field(None, alias="Cobertura_de_intereses")
    prueba_acida: Optional[float] = Field(None, alias="Prueba_Acida")
    importe_sobre_patrimonio: Optional[float] = Field(None, alias="Importe_sobre_Patrimonio")
    margen_bruto: Optional[float] = Field(None, alias="Margen_Bruto")
    ratio_gav: Optional[float] = Field(None, alias="Ratio_GAV")
    importe_sobre_ventas: Optional[float] = Field(None, alias="Importe_sobre_Ventas")
    rotacion_activos: Optional[float] = Field(None, alias="Rotacion_Activos")
    ratio_exportaciones: Optional[float] = Field(None, alias="Ratio_Exportaciones")

    # ========================================================================
    # FLAGS DE DENOMINADOR CERO
    # ========================================================================


    # ========================================================================
    # VARIABLES TEMPORALES (delta y variacion porcentual vs balance anterior)
    # ========================================================================
    delta_mgnop: Optional[float] = Field(None, alias="delta_MgnOp")
    pct_chg_mgnop: Optional[float] = Field(None, alias="pct_chg_MgnOp")
    delta_mgnneto: Optional[float] = Field(None, alias="delta_MgnNeto")
    pct_chg_mgnneto: Optional[float] = Field(None, alias="pct_chg_MgnNeto")
    delta_mgnbruto: Optional[float] = Field(None, alias="delta_MgnBruto")
    delta_roa: Optional[float] = Field(None, alias="delta_ROA")
    pct_chg_res_periodo: Optional[float] = Field(None, alias="pct_chg_Res_Periodo")
    pct_chg_roa: Optional[float] = Field(None, alias="pct_chg_ROA")
    pct_chg_res_sinamort: Optional[float] = Field(None, alias="pct_chg_Res_SinAmort")
    delta_res_periodo: Optional[float] = Field(None, alias="delta_Res_Periodo")
    pct_chg_res_op: Optional[float] = Field(None, alias="pct_chg_Res_Op")
    pct_chg_mgnbruto: Optional[float] = Field(None, alias="pct_chg_MgnBruto")
    delta_roe: Optional[float] = Field(None, alias="delta_ROE")
    pct_chg_res_neto: Optional[float] = Field(None, alias="pct_chg_Res_Neto")
    pct_chg_roe: Optional[float] = Field(None, alias="pct_chg_ROE")
    delta_res_op: Optional[float] = Field(None, alias="delta_Res_Op")
    pct_chg_patrimonio: Optional[float] = Field(None, alias="pct_chg_Patrimonio")
    delta_res_neto: Optional[float] = Field(None, alias="delta_Res_Neto")
    delta_res_sinamort: Optional[float] = Field(None, alias="delta_Res_SinAmort")
    pct_chg_actcte: Optional[float] = Field(None, alias="pct_chg_ActCte")
    delta_patrimonio: Optional[float] = Field(None, alias="delta_Patrimonio")
    pct_chg_pasivo: Optional[float] = Field(None, alias="pct_chg_Pasivo")
    pct_chg_activo: Optional[float] = Field(None, alias="pct_chg_Activo")
    delta_actcte: Optional[float] = Field(None, alias="delta_ActCte")
    delta_activo: Optional[float] = Field(None, alias="delta_Activo")
    delta_pasivo: Optional[float] = Field(None, alias="delta_Pasivo")

    # ========================================================================
    # MACROECONOMICAS (del mes de cierre del balance, con rezago de publicacion
    # ya incorporado en el entrenamiento; si faltan se imputan con la mediana)
    # ========================================================================
    valor_ui: Optional[float] = Field(None, alias="Valor_UI")
    pib: Optional[float] = Field(None, alias="PIB")
    pib_var_trimestral: Optional[float] = Field(None, alias="PIB_var_trimestral")
    pib_var_interanual: Optional[float] = Field(None, alias="PIB_var_interanual")
    desempleo: Optional[float] = Field(None, alias="Desempleo")
    desempleo_var_trimestral: Optional[float] = Field(None, alias="Desempleo_var_trimestral")
    desempleo_var_interanual: Optional[float] = Field(None, alias="Desempleo_var_interanual")

    # ========================================================================
    # CONTEXTO DE LA EMPRESA
    # ========================================================================
    grupo_economico: Optional[float] = Field(None, alias="GRUPO_ECONOMICO")
    numero_empleados: Optional[float] = Field(None, alias="NUMERO_EMPLEADOS")
    tipo_sociedad: Optional[str] = Field(None, alias="TIPO_SOCIEDAD")
    actividad_economica: Optional[str] = Field(None, alias="ACTIVIDAD_ECONOMICA")
    tamano_empresa: Optional[str] = Field(None, alias="tamaño_EMPRESA", description="Microempresa | Pequena | Mediana | Grande (criterio BCU)")
    sector: Optional[str] = Field(None, alias="SECTOR", description="Empresas | Agro")
    fecha_cierre: Optional[str] = Field(
        None, alias="FECHA_CIERRE",
        description="Mes de cierre del balance (YYYY-MM, YYYY-MM-DD o DD/MM/YYYY). Con la actividad "
                    "economica, el API completa el PIB de la industria, el desempleo y sus variaciones.",
    )
    sector_pib: Optional[str] = Field(
        None, alias="SECTOR_PIB",
        description="Industria del PIB (opcional). Si no viene, se deduce de la actividad economica.",
    )
    importe_mn: Optional[float] = Field(
        None, alias="IMPORTE_MN",
        description="Exposicion en la Central de Riesgos (M/N). El modelo NO la consume "
                    "directamente: se usa para derivar Importe_sobre_Ventas e "
                    "Importe_sobre_Patrimonio (el frontend los calcula automaticamente).",
    )

    class Config:
        populate_by_name = True
        extra = "allow"  # tolera claves adicionales (se descartan en el reindex)
        json_schema_extra = {
            "example": {
                "TOTAL ACTIVO": 5000000,
                "Total Activo Corriente": 3200000,
                "Sub-total - Disponibilidades": 400000,
                "Bienes de Cambio": 900000,
                "TOTAL PASIVO": 3000000,
                "Total Pasivo Corriente": 2100000,
                "Deudas Comercs": 800000,
                "TOTAL PATRIMONIO": 2000000,
                "Total Ingresos Operativos": 4200000,
                "Resultado Bruto": 1300000,
                "Resultado Operativo": 700000,
                "Resultado Neto": 450000,
                "Intereses Perdidos.": 120000,
                "TIPO_SOCIEDAD": "Sociedad Anonima",
                "ACTIVIDAD_ECONOMICA": "TRANSPORTE DE CARGA POR CARRETERA",
                "SECTOR": "Empresas",
                "NUMERO_EMPLEADOS": 25,
                "IMPORTE_MN": 600000,
            }
        }

    @field_validator('*', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convierte strings vacios a None"""
        if v == '' or v == ' ':
            return None
        return v

    @field_validator('total_activo', 'total_pasivo', 'total_activo_corriente',
                     'total_pasivo_corriente', mode='after')
    @classmethod
    def validate_positive_if_present(cls, v):
        """Validacion condicional: si el valor existe, debe ser >= 0"""
        if v is not None and v < 0:
            raise ValueError(f'El valor no puede ser negativo: {v}')
        return v

    @model_validator(mode='after')
    def validate_ecuacion_patrimonial(self):
        """
        Validacion de la ecuacion patrimonial basica:
            TOTAL ACTIVO = TOTAL PASIVO + TOTAL PATRIMONIO

        Tolerancia RELATIVA del 1%:
        los balances reales traen redondeos y ajustes menores; una diferencia
        mayor al 1% del activo si indica datos inconsistentes y se rechaza.
        La validacion aplica solo si los tres componentes estan presentes.
        """
        extras = self.__pydantic_extra__ or {}

        def _get(*names):
            for n in names:
                v = getattr(self, n, None)
                if v is not None:
                    return v
            for n in names:
                if n in extras and extras[n] is not None:
                    return extras[n]
            return None

        activo = _get('total_activo', 'TOTAL ACTIVO')
        pasivo = _get('total_pasivo', 'TOTAL PASIVO')
        patrimonio = _get('total_patrimonio', 'TOTAL PATRIMONIO')
        if activo is not None and pasivo is not None and patrimonio is not None:
            diff = abs(activo - (pasivo + patrimonio))
            tolerancia = max(abs(activo) * 0.01, 1.0)  # 1% relativo, piso $1
            if diff > tolerancia:
                raise ValueError(
                    "La ecuacion patrimonial basica no se cumple (tolerancia 1%):\n"
                    f"  TOTAL ACTIVO ({activo:,.2f}) != TOTAL PASIVO + TOTAL PATRIMONIO "
                    f"({pasivo:,.2f} + {patrimonio:,.2f} = {pasivo + patrimonio:,.2f}), "
                    f"diferencia = {diff:,.2f}"
                )

        return self


class PredictionRequest(BaseModel):
    """Request para predicción individual"""
    company_id: Optional[str] = Field(None, description="ID único de empresa")
    features: CompanyFeatures
    explain: bool = Field(False, description="Incluir explicación LIME")
    

class BatchPredictionRequest(BaseModel):
    """Request para predicción batch"""
    companies: List[CompanyFeatures] = Field(..., max_length=100)
    explain: bool = Field(False, description="Incluir explicación LIME")
    
    @field_validator('companies', mode='after')
    @classmethod
    def validate_batch_size(cls, v):
        if len(v) > 100:
            raise ValueError('Máximo 100 empresas por batch')
        return v


class RiskRating(BaseModel):
    """Banda de rating crediticio con DR empirico validado.

    Las cuatro bandas (Bueno / Aceptable / Comprometido / Crítico) se derivan
    en el notebook combinado buscando los tres cortes que maximizan el
    Information Value (Siddiqi, 2017) sobre probabilidades out-of-fold de
    entrenamiento, sujetos a monotonia en DR. Los cortes y DRs vigentes se
    publican en model_card.json (fuente unica de verdad) — no se hardcodean aca.
    """
    category: str = Field(..., description="Bueno, Aceptable, Comprometido, Crítico")
    description: str = Field(..., description="Nivel de riesgo de la banda (Tabla 6): mínimo, bajo, moderado o alto")
    color: str = Field(..., description="green, yellow, orange, red")


class LIMEFeature(BaseModel):
    """Una feature LIME con su contribución"""
    feature: str = Field(..., description="Nombre/condición de la feature")
    contribution: float = Field(..., description="Contribución al score")


class LIMEExplanation(BaseModel):
    """Explicación LIME"""
    top_features: List[LIMEFeature] = Field(..., description="Top features con contribución")
    prediction: float = Field(..., description="Predicción del modelo")
    intercept: float = Field(..., description="Intercept del modelo local")
    summary: Optional[str] = Field(None, description="Resumen en lenguaje natural generado por LLM")


class PredictionResponse(BaseModel):
    """Response de predicción"""
    company_id: Optional[str] = None
    
    # Predicción
    probability: float = Field(..., ge=0, le=1, description="Probabilidad de default (0-1)")
    score: int = Field(..., ge=0, le=1500, description="Credit score (rango teorico 0-1500)")
    risk_rating: RiskRating
    
    # Metadata
    prediction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = "2.1.0"

    # Opcional
    explanation: Optional[LIMEExplanation] = None
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Advertencias de calidad del input (features imputadas, macro faltantes, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "company_id": "12345678-9",
                "probability": 0.05,
                "score": 750,
                "risk_rating": {
                    "category": "Bueno",
                    "description": "Aprobar",
                    "color": "green"
                },
                "prediction_timestamp": "2024-01-15T10:30:00Z",
                "model_version": "1.0.0"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool
    model_version: str
    uptime_seconds: float