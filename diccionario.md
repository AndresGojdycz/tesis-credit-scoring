# Diccionario de variables

Variables del dataset final: 5.843 balances anuales de 3.179 empresas, con cierres entre 11/2019 y 07/2022.
El pipeline recibe **137 variables candidatas**. El modelo elegido (Random Forest con IQR, Yeo-Johnson y RFECV,
sin resampling) usa **107**, las que eligió RFECV, marcadas con "Sí" en la columna "En el modelo". El API recibe
solo esas 107.

Los montos de los estados contables están en pesos uruguayos. Un valor vacío (por ejemplo, un ratio con
denominador cero o una variación sin balance anterior) se imputa dentro del pipeline con la mediana de
entrenamiento.

---

## Identificación, fechas y variable objetivo

Estas columnas no son predictores.

| Variable | Descripción |
|---|---|
| `RUT` | Identificador de la empresa, enmascarado. Agrupa las particiones (entrenamiento/test y validación cruzada) para que una empresa no quede en los dos lados |
| `FECHA` | Fecha de cierre del balance (DD/MM/AA). Los balances fechados el día 1 se toman como cierre del último día del mes anterior |
| `FECHA_dt`, `YEAR_MONTH` | La misma fecha como fecha y como año-mes; el mes de cierre es `t` |
| `SECTOR` | Origen del balance: Empresas (`doc2`) o Agro (`doc3`). Entra al modelo como indicadoras (`SECTOR_*`) |
| `CALIFICACION` | Calificación de la Central de Riesgos del BCU al cierre: la peor entre instituciones, del mes `t` o del último mes registrado en los 12 anteriores. Se usa para excluir los balances de empresas ya calificadas en 3, 4 o 5, no como predictor |
| `IMPORTE_MN` | Deuda total en el sistema financiero en el mes `t` (Central de Riesgos); 0 si la empresa no registra deuda ese mes. No entra cruda: se usa en `Importe_sobre_Ventas` e `Importe_sobre_Patrimonio` |
| `DEFAULT_FUTURE` | **Variable objetivo.** Vale 1 si en algún mes de [t+1, t+12] la empresa registra, en cualquier institución, un crédito vencido, en gestión, moroso o castigado por atraso (atraso de 60 días o más), y 0 si no. Tasa: 7,80% (456 eventos) |

---

## Partidas de los estados contables (74 candidatas)

Fuente: estados contables presentados al BROU (`doc2` para Empresas y `doc3` para Agro, con los nombres de
columna de Agro llevados a los de Empresas).

### Activo corriente

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Caja` | Efectivo en caja | Sí |
| `Bancos` | Depósitos en bancos en moneda nacional | Sí |
| `Bancos M/E` | Depósitos en bancos en moneda extranjera | Sí |
| `Sub-total - Disponibilidades` | Total de disponibilidades (caja y bancos) | Sí |
| `Inversiones Temporarias` | Inversiones de corto plazo | Sí |
| `Depositos en Garantia` | Depósitos dados en garantía | Sí |
| `Creditos Vtas.Plaza` | Cuentas a cobrar por ventas en plaza | Sí |
| `Creditos Vtas.Exp.` | Cuentas a cobrar por exportaciones | Sí |
| `Documentos a cobrar` | Documentos a cobrar (pagarés, cheques diferidos) | Sí |
| `Ctas. de Directores(6)` | Cuentas a cobrar a directores o socios | Sí |
| `Impuestos Adelantados` | Impuestos pagados por adelantado (anticipos, créditos fiscales) | Sí |
| `Otros Creditos` | Otros créditos de corto plazo | Sí |
| `Bienes de Cambio` | Inventarios | Sí |
| `Total Activo Corriente` | Total del activo corriente | Sí |

### Activo no corriente

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Bienes de Cambio L/P` | Inventarios de largo plazo (por ejemplo, ganado de cría) | Sí |
| `Bienes de Uso` | Activo fijo (inmuebles, maquinaria, vehículos) | Sí |
| `Otros Activos No Corrientes` | Otros activos no corrientes | Sí |
| `Intangibles` | Activos intangibles |  |
| `Amort. Acumuladas` | Amortizaciones acumuladas del activo fijo | Sí |
| `Impuesto Diferido` | Activo por impuesto diferido |  |
| `Total Activo no Corriente` | Total del activo no corriente | Sí |
| `TOTAL ACTIVO` | Activo total | Sí |

### Pasivo corriente

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Deudas Comercs` | Deudas comerciales (proveedores) en moneda nacional | Sí |
| `Deudas Coms. MExt.` | Deudas comerciales en moneda extranjera |  |
| `Deudas BROU MNal.` | Deudas con el BROU en moneda nacional, corto plazo | Sí |
| `Deudas BROU MExt.` | Deudas con el BROU en moneda extranjera, corto plazo | Sí |
| `Acreeds. Bancarios MNal.` | Deudas con otros bancos en moneda nacional, corto plazo | Sí |
| `Acreeds. Bancarios MExt.` | Deudas con otros bancos en moneda extranjera, corto plazo | Sí |
| `Documentos a Pagar` | Documentos a pagar |  |
| `Deudas Diversas` | Otras deudas (salarios, cargas sociales, impuestos) | Sí |
| `Previsiones y Provisiones` | Previsiones y provisiones |  |
| `Ctas. de Directores (6)` | Deudas con directores o socios |  |
| `otras deudas financieras` | Otras deudas financieras de corto plazo |  |
| `Total Pasivo Corriente` | Total del pasivo corriente | Sí |

### Pasivo no corriente

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Deudas BROU MNal..1` | Deudas con el BROU en moneda nacional, largo plazo | Sí |
| `Deudas BROU MExt..1` | Deudas con el BROU en moneda extranjera, largo plazo | Sí |
| `Acreeds. Bancarios` | Deudas con otros bancos, largo plazo | Sí |
| `Deutas Otros Bancos M/E` | Deudas con otros bancos en moneda extranjera, largo plazo (el nombre viene así del archivo de origen) |  |
| `Ctras Deudas Largo Plazo` | Otras deudas de largo plazo |  |
| `Total Pasivo No Corriente` | Total del pasivo no corriente | Sí |
| `TOTAL PASIVO` | Pasivo total | Sí |

### Patrimonio

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Capital` | Capital integrado | Sí |
| `Ajustes al Patrim.` | Ajustes al patrimonio | Sí |
| `Reservas` | Reservas legales y voluntarias | Sí |
| `+(gan) -(pérd) Res Acums.` | Resultados acumulados de ejercicios anteriores | Sí |
| `+(gan) -(pérd) Aj por Infl` | Resultado por ajuste por inflación |  |
| `- Dividendo Provisorio` | Dividendos anticipados (restan del patrimonio) | Sí |
| `Ajustes Activos/Pasivos` | Ajustes contables sobre activos y pasivos | Sí |
| `Ajuste Resul. Neto Contable` | Ajuste al resultado neto contable | Sí |
| `Adelantos Irrevocs.` | Aportes irrevocables a cuenta de futuras capitalizaciones | Sí |
| `Revaluaciones` | Reserva por revaluación de activos | Sí |
| `TOTAL PATRIMONIO` | Patrimonio total | Sí |

### Estado de resultados

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `Resultado por Tenencia -Agricultura-NIC-41` | Cambio en el valor razonable de activos biológicos agrícolas (NIC 41) |  |
| `Resultado por Tenencia -Ganaderia-NIC-41` | Cambio en el valor razonable de activos biológicos ganaderos (NIC 41) | Sí |
| `Total Ingresos Operativos` | Ingresos operativos (ventas brutas) | Sí |
| `Ajustes/Bonificaciones s/Ventas` | Descuentos, bonificaciones y devoluciones sobre ventas |  |
| `Costo de lo Vendido` | Costo de los bienes vendidos o servicios prestados | Sí |
| `Resultado Bruto` | Ingresos menos costo de lo vendido | Sí |
| `Gastos  Ad.y Ventas.` | Gastos de administración y ventas | Sí |
| `- Otros Gastos + Otros Ingresos` | Neto de otros gastos e ingresos operativos | Sí |
| `Resultado Operativo` | Resultado operativo | Sí |
| `Intereses Perdidos.` | Intereses pagados | Sí |
| `Intereses Ganados` | Intereses cobrados |  |
| `Otros Gastos(+)/Ingresos(-) Financieros` | Neto de otros gastos e ingresos financieros | Sí |
| `+(pérd) -(gan) RDM` | Resultado por desvalorización monetaria |  |
| `Diferencia de Cambio Perdida.` | Pérdida por diferencia de cambio | Sí |
| `Diferencia de Cambio Ganada` | Ganancia por diferencia de cambio | Sí |
| `- Otros Res.  No Operativos` | Otros resultados no operativos |  |
| `- Otros Resultados No Operativos.` | Otros resultados no operativos (otra columna del formulario) |  |
| `- Otros Resultados- Extraordinarios.` | Resultados extraordinarios |  |
| `Impuestos` | Impuestos sobre resultados | Sí |
| `Impto. a la Renta` | Impuesto a la renta | Sí |
| `Amortizaciones` | Amortizaciones del ejercicio | Sí |
| `Resultado Neto` | Resultado neto del ejercicio | Sí |

---

## Ratios financieros (14)

Calculados por `apply_feature_engineering` en `notebooks/funciones.py`. Si el denominador es cero o falta, el
ratio queda vacío.

| Variable | Fórmula | Descripción | En el modelo |
|---|---|---|:---:|
| `Ratio_Corriente` | Total Activo Corriente / Total Pasivo Corriente | Liquidez corriente | Sí |
| `Prueba_Acida` | (Total Activo Corriente − Bienes de Cambio) / Total Pasivo Corriente | Liquidez sin inventarios | Sí |
| `Ratio_Efectivo` | Sub-total - Disponibilidades / Total Pasivo Corriente | Liquidez inmediata | Sí |
| `Deuda_sobre_Activos` | TOTAL PASIVO / TOTAL ACTIVO | Endeudamiento | Sí |
| `Relacion_deuda_patrimonio` | TOTAL PASIVO / TOTAL PATRIMONIO | Endeudamiento respecto del patrimonio | Sí |
| `Ratio_Patrimonio` | TOTAL PATRIMONIO / TOTAL ACTIVO | Solvencia | Sí |
| `Cobertura_de_intereses` | Resultado Operativo / Intereses Perdidos. | Capacidad de pagar los intereses con el resultado operativo | Sí |
| `ROA` | Resultado Neto / TOTAL ACTIVO | Rentabilidad del activo | Sí |
| `ROE` | Resultado Neto / TOTAL PATRIMONIO | Rentabilidad del patrimonio | Sí |
| `Margen_Bruto` | Resultado Bruto / Total Ingresos Operativos | Margen bruto | Sí |
| `Margen_Neto` | Resultado Neto / Total Ingresos Operativos Netos | Margen neto (sobre ingresos netos de bonificaciones) | Sí |
| `Ratio_GAV` | Gastos  Ad.y Ventas. / Total Ingresos Operativos | Peso de los gastos de administración y ventas | Sí |
| `Ratio_Exportaciones` | Exportaciones / Total Ingresos Operativos | Peso de las exportaciones en las ventas |  |
| `Rotacion_Activos` | Total Ingresos Operativos / TOTAL ACTIVO | Eficiencia en el uso del activo | Sí |

## Exposición crediticia relativa (2)

El importe adeudado no entra crudo: se normaliza por el tamaño de la empresa.

| Variable | Fórmula | Descripción | En el modelo |
|---|---|---|:---:|
| `Importe_sobre_Ventas` | IMPORTE_MN / Total Ingresos Operativos | Deuda bancaria total en relación con las ventas | Sí |
| `Importe_sobre_Patrimonio` | IMPORTE_MN / TOTAL PATRIMONIO | Deuda bancaria total en relación con el patrimonio | Sí |

## Variaciones respecto del balance anterior (11)

Diferencia con el balance anterior de la misma empresa dentro de la muestra. En el primer balance de cada
empresa quedan vacías.

| Variable | Fórmula | Descripción | En el modelo |
|---|---|---|:---:|
| `primera_observacion` | 1 si es el primer balance de la empresa en la muestra | Indica que la empresa no tiene un balance anterior, por lo que sus variaciones quedan vacías | Sí |
| `delta_Activo` | TOTAL ACTIVO − el del balance anterior | Variación del activo | Sí |
| `delta_ActCte` | Total Activo Corriente − el del balance anterior | Variación del activo corriente | Sí |
| `delta_Pasivo` | TOTAL PASIVO − el del balance anterior | Variación del pasivo | Sí |
| `delta_Patrimonio` | TOTAL PATRIMONIO − el del balance anterior | Variación del patrimonio | Sí |
| `delta_Res_Op` | Resultado Operativo − el del balance anterior | Variación del resultado operativo | Sí |
| `delta_Res_Neto` | Resultado Neto − el del balance anterior | Variación del resultado neto | Sí |
| `delta_MgnBruto` | Margen_Bruto − el del balance anterior | Variación del margen bruto | Sí |
| `delta_MgnNeto` | Margen_Neto − el del balance anterior | Variación del margen neto | Sí |
| `delta_ROA` | ROA − el del balance anterior | Variación del ROA | Sí |
| `delta_ROE` | ROE − el del balance anterior | Variación del ROE | Sí |

---

## Variables macroeconómicas (6)

Fuente: `datos macro/` (PIB trimestral por industria del BCU y tasa de desempleo). Se asignan por mes de
cierre del balance y, en el caso del PIB, por la industria de la actividad económica de la empresa.

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `PIB` | PIB trimestral de la industria a la que pertenece la actividad de la empresa (BCU). Se asigna a cada mes del trimestre y se desfasa 3 meses por el rezago de publicación | Sí |
| `PIB_var_trimestral` | Variación porcentual del PIB de la industria respecto de 3 meses antes | Sí |
| `PIB_var_interanual` | Variación porcentual del PIB de la industria respecto de 12 meses antes | Sí |
| `Desempleo` | Tasa de desempleo del mes anterior al cierre del balance (rezago de publicación de 1 mes) | Sí |
| `Desempleo_var_trimestral` | Variación porcentual de la tasa de desempleo respecto de 3 meses antes | Sí |
| `Desempleo_var_interanual` | Variación porcentual de la tasa de desempleo respecto de 12 meses antes | Sí |

---

## Variables cualitativas (30)

Fuente: datos cualitativos de los clientes (`doc1`). Las categóricas entran como variables indicadoras
(0/1).

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `GRUPO_ECONOMICO` | 1 si la empresa informa pertenecer a un grupo económico, 0 si no |  |
| `NUMERO_EMPLEADOS` | Cantidad de empleados declarada | Sí |

### Tipo de sociedad

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `TIPO_SOCIEDAD_Otros` | Indicadora del tipo de sociedad (agrupa los tipos con pocas observaciones) | Sí |
| `TIPO_SOCIEDAD_Sociedad Anonima` | Indicadora del tipo de sociedad | Sí |
| `TIPO_SOCIEDAD_Sociedad de Hecho` | Indicadora del tipo de sociedad | Sí |
| `TIPO_SOCIEDAD_Sociedad de Resp. Limitada` | Indicadora del tipo de sociedad | Sí |
| `TIPO_SOCIEDAD_Sociedad en Comandita Simple` | Indicadora del tipo de sociedad | Sí |
| `TIPO_SOCIEDAD_Unipersonal` | Indicadora del tipo de sociedad | Sí |

### Actividad económica

Las 15 actividades más frecuentes tienen su propia indicadora; el resto se agrupa en `Otros`.

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `ACTIVIDAD_ECONOMICA_CUL.DE PROD.AGRI.EN COMB.CON CRIA DE ANIM. EXPLOT.MIXTA` | Indicadora de actividad económica | Sí |
| `ACTIVIDAD_ECONOMICA_EXPLOTACION GANADERA (EXCEPTO LECHERIA)` | Indicadora de actividad económica | Sí |
| `ACTIVIDAD_ECONOMICA_EXPLOTACION LECHERA` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_OTRAS ACTIVIDADES DE SERVICIOS N.C.P.` | Indicadora de actividad económica | Sí |
| `ACTIVIDAD_ECONOMICA_OTROS TIPOS DE VTA. AL POR MENOR NO REALIZ. EN ALMACEN.` | Indicadora de actividad económica | Sí |
| `ACTIVIDAD_ECONOMICA_Otros` | Indicadora de actividad económica (actividades fuera de las 15 más frecuentes) | Sí |
| `ACTIVIDAD_ECONOMICA_SERVICIOS AGRICOLAS` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_TRANSPORTE DE CARGA POR CARRETERA` | Indicadora de actividad económica | Sí |
| `ACTIVIDAD_ECONOMICA_VENTA AL POR MAYOR DE ALIMENTOS, BEBIDAS Y TABACO` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VENTA AL POR MAYOR DE OTROS PRODUCTOS` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA. MENOR ALMAC NO ESPECIALI.,DE ALIM.,BEB. TAB` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA.X MENOR DE ALIM.,BEB.Y TABACO EN ALMACEN. ESPECIAL.` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA.X MENOR DE APARATOS,ARTICUL.Y EQUIPO USO DOMESTIC.` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA.X MENOR DE ART.DE FERRETE.,PINTUR. Y PROD.DE VIDRIO` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA.X MENOR DE OTROS PRODUCTOS DE ALMACENES ESPECIALIZ.` | Indicadora de actividad económica |  |
| `ACTIVIDAD_ECONOMICA_VTA.X MENOR DE PROD.TEXTIL.,PRENDAS,CALZ. Y ARTIC.CUERO` | Indicadora de actividad económica |  |

### Tamaño de la empresa

Criterio del BCU por ventas anuales en Unidades Indexadas (`Total Ingresos Operativos` dividido por la UI
promedio del mes de cierre): microempresa, hasta 2 millones de UI; pequeña, de 2 a 10 millones; mediana, de 10
a 75 millones; grande, más de 75 millones.

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `tamaño_EMPRESA_Microempresa` | Indicadora del tamaño de la empresa | Sí |
| `tamaño_EMPRESA_Pequena` | Indicadora del tamaño de la empresa | Sí |
| `tamaño_EMPRESA_Mediana` | Indicadora del tamaño de la empresa | Sí |
| `tamaño_EMPRESA_Grande` | Indicadora del tamaño de la empresa |  |

### Sector

| Variable | Descripción | En el modelo |
|---|---|:---:|
| `SECTOR_Agro` | Indicadora del sector de origen del balance (Empresas o Agro) | Sí |
| `SECTOR_Empresas` | Indicadora del sector de origen del balance (Empresas o Agro) | Sí |

---

## Variables descartadas por redundancia

Antes de la imputación y de toda selección se quitan 24 variables. En cada grupo con correlación de Spearman
de 0,9 o más (sobre deciles de entrenamiento), o con una equivalencia contable, se conserva una sola, elegida
por criterio de dominio y sin usar la variable objetivo.

| Variable | Motivo |
|---|---|
| `TOTAL PASIVO Y PATRIMONIO` | Igual a `TOTAL ACTIVO` |
| `Total Ingresos Operativos Netos` | Casi igual a `Total Ingresos Operativos` (se usa en `Margen_Neto`) |
| `Ventas Plaza`, `Exportaciones` | Componentes de los ingresos (queda `Ratio_Exportaciones`) |
| `+(gan) -(pérd) Res Periodo` | Igual a `Resultado Neto` (en todos los balances de Agro y en el 77% de Empresas) |
| `Resultado Sin Amortizaciones` | Igual a `Resultado Neto` en Agro |
| `Margen_Operativo` | Gemela de `Margen_Neto` |
| `Multiplicador` (`TOTAL ACTIVO / TOTAL PATRIMONIO`) | Gemela de `Ratio_Patrimonio` |
| `delta_Res_SinAmort`, `delta_Res_Periodo`, `delta_MgnOp` | Variaciones de variables quitadas |
| `pct_chg_*` (13 variables) | Variaciones porcentuales; se conserva una sola forma de variación, `delta_*` |

También se descarta `Resultado por Tenencia - NIC 41 -`, que es constante en entrenamiento.

---

## Escala de calificaciones del BCU

Categorías de riesgo de los deudores en la Central de Riesgos, según el Marco Contable del BCU.
En este trabajo se excluyen los balances de empresas calificadas en 3, 4 o 5 en el mes de cierre, porque ya
están en dificultades; la variable objetivo no se define por la calificación sino por el atraso.

| Categoría | Significado |
|---|---|
| 1A | Operaciones con garantías autoliquidables admitidas |
| 1C | Deudores con capacidad de pago fuerte |
| 2A | Deudores con capacidad de pago adecuada |
| 2B | Deudores con capacidad de pago con problemas potenciales |
| 3 | Deudores con capacidad de pago comprometida |
| 4 | Deudores con capacidad de pago muy comprometida |
| 5 | Deudores irrecuperables |
