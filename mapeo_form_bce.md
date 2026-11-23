# Importador del formulario de estados contables del BROU (FORM_BCE) — correspondencia

Actualizado el 17/11/2026 con un formulario real completado por un cliente. El banco usa hoy la **versión 08/08/2018**, no la de 2011 del primer borrador.

## Cómo se usa

En el dashboard, se sube el .xlsx en la zona "Cargar archivo CSV o Excel". El formulario se reconoce por sus hojas y lo lee el API (`POST /importar/form-bce`), que devuelve los campos, sin convertir montos, y una lista de avisos. Los avisos aparecen en un recuadro "Revisar antes de evaluar":
- la actividad propuesta a partir del giro;
- los cuadres que no cierran;
- siempre, que hay que completar el importe a mano: el formulario no lo trae y, si queda vacío, el modelo lo imputa con la mediana.

Al importar se borran la fecha, las cualitativas y el importe que hubiera de un archivo anterior. El botón "Evaluar Empresa" queda deshabilitado mientras se lee el formulario.

**Lo que se verificó en el dashboard (17/11):**
- Los cuatro ejemplos, importados desde el formulario y con el importe del CSV, mandan al modelo exactamente los mismos datos que el CSV y dan el mismo puntaje (821, 777, 739 y 705).
- El formulario real da 755, banda Comprometido, sin errores contables. Quedan imputadas 5 variables: el importe (2 ratios) y el PIB (3).

## Qué se validó con el formulario real

El formulario real es de una empresa con balance a enero de 2026, cargado en dólares. Está guardado fuera del repositorio, en `data/formulario_bce_real/`.

**Qué no se pudo validar:**
- **Contra `data/doc2.txt`.** Los RUT de doc2 están enmascarados con un hash que no coincide con MD5, SHA-1 ni SHA-256 del RUT. Además, los balances de doc2 llegan hasta 2022.

**Qué sí se validó, contra la estructura del propio formulario:**
- El balance cuadra en los dos ejercicios. La diferencia es de 35 pesos, por redondeo del cliente.
- El resultado neto cierra con el operativo menos las partidas financieras e impuestos, con la convención de signos de doc2.
- El resultado operativo cierra con sus partidas.
- Los totales de disponibilidades, deudas comerciales y pasivos financieros coinciden con sus hojas de detalle.
- El API lo puntúa sin errores: 755, banda Comprometido. El PIB va imputado, porque enero de 2026 está fuera de la serie.
- **Errores de tipeo del cliente.** En el tipo de sociedad y en el giro hay errores de tipeo. El importador los tolera: la búsqueda compara palabras parecidas y abreviaturas.

## Cómo está armado el formulario 2018

- **Hojas de estados.** Son ACTIVO CORRIENTE, ACTIVO NO CORRIENTE, PASIVO CORRIENTE, PASIVO NO CORRIENTE, PATRIMONIO y ESTADO DEL RESULTADO INTEGRAL.
  - El año anterior va en las columnas C (US$) y D ($); el actual, en F (US$) y G ($).
  - **El cliente completa una sola moneda.** Se usa la que completó, sin convertir (decisión del autor, 19/11: se asume que siempre es la misma moneda y no se menciona). El tipo de cambio de cierre (INFORMACIÓN GENERAL F17) solo se usa, internamente, para llevar las hojas de detalle (que vienen en la columna en $) a la escala de los estados cuando el cliente completó la otra columna.
- **Hojas de detalle** (DETALLE DEL ACTIVO, DETALLE DEL PASIVO y DETALLE DE PASIVOS FINANCIEROS). Traen solo el año actual, ya en pesos, en tres columnas: D (moneda extranjera traducida), F (moneda nacional) y H (total).
- **La hoja "Temporal" no sirve para el importador.** Solo lee la columna en pesos de los estados, así que cuando el cliente carga en dólares quedan en cero el patrimonio, las ventas y los gastos.
- **Signos en el resultado.** Costo de ventas, gastos, amortizaciones e impuesto a la renta van en positivo; los demás resultados van con su signo (pérdidas en negativo). En doc2, en cambio, las pérdidas financieras están en positivo y las ganancias en negativo, así que el importador les invierte el signo.
- **BROU y otros bancos.** En el detalle de pasivos financieros, el cliente real cargó un préstamo del BROU en una fila del bloque de "otros bancos". Por eso el importador clasifica cada fila por el nombre de la institución y no por la posición.

## Correspondencia (año actual)

Abreviaturas de las hojas: AC = ACTIVO CORRIENTE, ANC = ACTIVO NO CORRIENTE, PC = PASIVO CORRIENTE, PNC = PASIVO NO CORRIENTE, PAT = PATRIMONIO, ER = ESTADO DEL RESULTADO INTEGRAL. "Fila n" es la fila de la hoja de estados, en la columna de la moneda que completó el cliente.

| Variable del modelo | Celdas del formulario 2018 | Duda |
|---|---|---|
| Caja | Disponibilidades − bancos del detalle | |
| Bancos / Bancos M/E | DETALLE DEL ACTIVO F9+F10 / D9+D10 | |
| Sub-total - Disponibilidades | AC fila 13 | |
| Inversiones Temporarias | AC fila 22 | |
| Depositos en Garantia | AC fila 37 | |
| Creditos Vtas.Plaza | AC filas 25 + 29 + 31 + 32 (neto de previsión) | ¿Neto de previsión en doc2? |
| Creditos Vtas.Exp. / Documentos a cobrar | AC fila 26 / fila 27 | |
| Otros Creditos | AC filas 36, 38, 40, 41, 43 y 44 | |
| Ctas. de Directores(6) | AC fila 39 | |
| Bienes de Cambio | AC fila 56 (+ activos biológicos, fila 70) | |
| Bienes de Uso / Amort. Acumuladas | ANC fila 43 / fila 45 (negativa) | |
| Impuesto Diferido | ANC fila 10 | |
| Otros Activos No Corrientes | Total ANC − bienes de uso − amortizaciones − impuesto diferido | |
| Deudas Comercs / Deudas Coms. MExt. | DETALLE DEL PASIVO F15+F22 / D15+D22 | |
| Deudas BROU MNal. / MExt. (corto plazo) | Filas del detalle de pasivos financieros cuya institución es el BROU: capital + intereses a pagar − intereses a vencer (en pesos en el detalle; si los estados están en dólares, se pasan a dólares) | ¿doc2 incluye los intereses? |
| Acreeds. Bancarios MNal. / MExt. (corto plazo) | Ídem, filas de otros bancos | Misma duda |
| otras deudas financieras | Filas "OTRAS DS FINANCIERAS" + lo que el detalle no explica del total de PC fila 30 | |
| Ctas. de Directores (6) (pasivo) | DETALLE DEL PASIVO D24+F24 (si está vacío, PC fila 40) | |
| Deudas Diversas | PC fila 42 − directores | |
| Previsiones y Provisiones | PC fila 49 | |
| Deudas BROU MNal..1 / MExt..1, Acreeds. Bancarios (largo plazo) | Detalle de pasivos financieros, bloques de largo plazo | |
| Ctras Deudas Largo Plazo | Total PNC − deudas bancarias de largo plazo | ¿Incluye previsiones no corrientes? |
| Capital | PAT filas 9 a 12 | |
| Adelantos Irrevocs. | PAT filas 14 y 15 | |
| Revaluaciones | PAT filas 18 a 20 | |
| Reservas | PAT filas 24 a 26 | |
| Res Acums. / Res Periodo / Dividendo | PAT fila 29 / fila 30 / fila 32 | |
| Ventas Plaza / Exportaciones | ER filas 9, 10 y 13 a 20 / fila 12 | |
| Ajustes/Bonificaciones s/Ventas | −ER fila 22 | |
| Costo de lo Vendido | ER fila 27 | |
| Amortizaciones | ER fila 33 | |
| Gastos Ad.y Ventas. | ER fila 37 − fila 33 (incluye el impuesto al patrimonio) | ¿doc2 pone el impuesto al patrimonio en gastos? |
| - Otros Gastos + Otros Ingresos | ER fila 42 | |
| Intereses Perdidos. / Ganados | −ER fila 47 / −fila 48 | |
| Otros Gastos(+)/Ingresos(-) Financieros | −(ER filas 49 + 50) | |
| Diferencia de Cambio Perdida. / Ganada | −ER fila 51 / −fila 52 | |
| +(pérd) -(gan) RDM | −ER fila 53 | |
| - Otros Resultados- Extraordinarios. | −(ER filas 63 a 65, otros resultados integrales) | |
| Impto. a la Renta | ER fila 58 | |
| Resultado Neto | ER fila 67 (resultado integral total) | |
| Resultado Sin Amortizaciones | Neto + amortizaciones | |

**Año anterior.** Los totales que usan las variaciones (activo corriente, activo, pasivo, patrimonio, ingresos y resultados) salen de las columnas C/D de las mismas filas. Si el formulario está en dólares, el año anterior también se usa en dólares, así que las variaciones quedan en dólares.

**Otros datos (INFORMACIÓN GENERAL):**
- **Fecha de cierre:** C9.
- **Empleados:** E13 + I13.
- **Grupo económico:** una X en E37 es Sí; en G37, No.
- **Tipo de sociedad (C5):** es texto libre. Se reconocen S.A., S.R.L., unipersonal, sociedad de hecho y comandita, aunque estén abreviados o mal escritos; si no se reconoce, queda "Otros" con aviso.
- **Giro (C10):** es texto libre. El importador propone la actividad más parecida de la lista del BCU (las 187 de `artifacts/macro.json`), y de ella salen la industria del PIB y el sector (Agro si la industria es agropecuaria; si no, Empresas). Compara palabra por palabra y tolera abreviaturas y errores de tipeo. Si ninguna actividad convence, o dos empatan, la deja para elegir a mano. Para el formulario real propuso "ALMACENAMIENTO Y DEPOSITO".
- **Fecha de cierre (C9):** como en el notebook, un balance fechado el día 1 se toma como cierre del mes anterior.

## Archivos

- **`credit-scoring-api/app/form_bce.py`** es el importador: `leer` devuelve las variables del modelo en la moneda de los estados, con los controles de cuadre, e `importar` arma los campos del dashboard y los avisos. Un residuo de menos de un peso entre el total de pasivos financieros y su detalle se toma como redondeo.
- **Endpoint y dashboard:** `POST /importar/form-bce` en `credit-scoring-api/app/main.py`, la ruta `code/app/api/importar/route.ts` y la carga en `code/components/credit-scoring/company-form.tsx`.
- **Validación contable del dashboard:** la tolerancia pasó de 0,5 a 0,01 % del total (mínimo 0,5), en `code/lib/feature-config.ts`. Con la tolerancia anterior, los 35 pesos de redondeo del formulario real bloqueaban la evaluación.
- **`ejemplos/leer_formulario.py`** usa el mismo lector para revisar un formulario desde la terminal.
- **`ejemplos/generar_formularios.py`** llena el formulario en blanco con los cuatro CSV de `ejemplos/` y deja los .xlsx en `ejemplos/formulario_bce/`.
  - **Ejercicio anterior.** Como el CSV trae solo los totales, las partidas de ese ejercicio se reparten en la misma proporción que en el actual.
  - **Lectura de vuelta.** Releídos, dan los mismos valores que el CSV, variable por variable, y el mismo puntaje del API (821, 777, 739 y 705).
- **La plantilla en blanco** (`data/formulario_bce_real/plantilla_bce_2018.xlsx`) se hizo vaciando el formulario real: se borraron las celdas de carga, las fórmulas con montos del cliente y las propiedades del archivo. Se revisó que no quedara ningún dato del cliente. Igual queda fuera del repositorio, porque sale de un archivo confidencial.

## Lo que queda por confirmar

1. **Intereses en las deudas bancarias.** ¿doc2 incluye los intereses a pagar dentro de "Deudas BROU" y "Acreeds. Bancarios"?
2. **Impuesto al patrimonio.** ¿Va dentro de gastos de administración y ventas?
3. **Tipo de cambio del año anterior.** ¿Cómo convierte el banco el ejercicio anterior cuando los estados están en dólares?
