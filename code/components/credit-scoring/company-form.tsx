/**
 * Formulario para ingresar datos de empresa
 * Soporta las 70 variables raw del modelo + calculo automatico de 12 features de ingenieria
 * Soporta carga de datos desde archivos CSV y Excel. Ademas de las partidas del balance, el archivo
 * puede traer las variables cualitativas, la fecha de cierre, la deuda bancaria y los empleados (completan sus
 * campos). Si trae el balance del año anterior (columnas "<partida> (anterior)"), el formulario calcula
 * las variaciones temporales (delta_*); las delta_* que vengan ya calculadas se envian tal cual.
 * Las variables macro las completa el API a partir de la fecha de cierre (FECHA_CIERRE) y la actividad.
 * El formulario de estados contables del BROU (FORM_BCE 2018, .xlsx) se reconoce por sus hojas y lo lee el API
 * (POST /importar/form-bce): devuelve los mismos campos que el CSV y avisos para revisar.
 */

"use client"

import { useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import Papa from "papaparse"
import * as XLSX from "xlsx"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AlertTriangle, Building2, Upload } from "lucide-react"
import type { CompanyFeatures } from "@/lib/types"
import {
  RAW_FEATURES,
  CATEGORY_ORDER,
  CATEGORY_LABELS,
  computeEngineeredFeatures,
  computeTemporalVariations,
  SUFIJO_ANTERIOR,
  validateAccountingSums,
  type ValidationError,
} from "@/lib/feature-config"

// Campo numerico opcional: un input vacio llega como NaN (valueAsNumber) y se trata como no informado,
// en lugar de bloquear el envio. Al enviar, las partidas del balance vacias pasan a 0; la cantidad de
// empleados vacia no se envia y el API la imputa con la mediana de entrenamiento.
const numeroOpcional = () =>
  z.preprocess((v) => (typeof v === "number" && Number.isNaN(v) ? undefined : v), z.number().optional())

// El importe solicitado es obligatorio: sin él no se puede evaluar la operación
const importeObligatorio = () =>
  z.preprocess(
    (v) => (typeof v === "number" && Number.isNaN(v) ? undefined : v),
    z
      .number({ required_error: "Ingresá el importe solicitado", invalid_type_error: "Ingresá el importe solicitado" })
      .positive("El importe solicitado debe ser mayor que 0"),
  )

// Build Zod schema dynamically from feature config
const schemaFields: Record<string, z.ZodTypeAny> = {
  company_id: z.string().optional(),
  tipo_sociedad: z.string().optional(),
  actividad_economica: z.string().optional(),
  numero_empleados: numeroOpcional(),
  grupo_economico: z.string().optional(),
  fecha_cierre: z.string().optional(),
  sector_pib: z.string().optional(),
  importe_mn: importeObligatorio(),
  sector: z.string().optional(),
}
for (const f of RAW_FEATURES) {
  schemaFields[f.key] = numeroOpcional()
}
const companySchema = z.object(schemaFields)

const TIPO_SOCIEDAD_OPTIONS = [
  { value: "", label: "Sin datos" },
  { value: "Sociedad Anonima", label: "Sociedad Anonima" },
  { value: "Sociedad de Resp. Limitada", label: "Sociedad de Resp. Limitada" },
  { value: "Unipersonal", label: "Unipersonal" },
  { value: "Sociedad de Hecho", label: "Sociedad de Hecho" },
  { value: "Sociedad en Comandita Simple", label: "Sociedad en Comandita Simple" },
  { value: "Otros", label: "Otros" },
]

const SECTOR_OPTIONS = [
  { value: "", label: "Sin datos" },
  { value: "Empresas", label: "Empresas" },
  { value: "Agro", label: "Agropecuario" },
]

const GRUPO_ECONOMICO_OPTIONS = [
  { value: "", label: "Sin datos" },
  { value: "1", label: "Si" },
  { value: "0", label: "No" },
]

const ACTIVIDAD_ECONOMICA_OPTIONS = [
  { value: "", label: "Sin datos" },
  { value: "EXPLOTACION GANADERA (EXCEPTO LECHERIA)", label: "Explotacion ganadera" },
  { value: "EXPLOTACION LECHERA", label: "Explotacion lechera" },
  { value: "CUL.DE PROD.AGRI.EN COMB.CON CRIA DE ANIM. EXPLOT.MIXTA", label: "Explotacion mixta (agro + ganaderia)" },
  { value: "TRANSPORTE DE CARGA POR CARRETERA", label: "Transporte de carga" },
  { value: "CONST.DE EDIFICIOS COMPLET. O DE PARTES.OBR. DE ING.CIV", label: "Construccion" },
  { value: "VENTA AL POR MAYOR DE ALIMENTOS, BEBIDAS Y TABACO", label: "Venta mayorista alimentos" },
  { value: "VENTA AL POR MAYOR DE OTROS PRODUCTOS", label: "Venta mayorista otros" },
  { value: "VTA. MENOR ALMAC NO ESPECIALI.,DE ALIM.,BEB. TAB", label: "Venta minorista almacen" },
  { value: "VTA.X MENOR DE ALIM.,BEB.Y TABACO EN ALMACEN. ESPECIAL.", label: "Venta minorista alimentos" },
  { value: "VTA.X MENOR DE APARATOS,ARTICUL.Y EQUIPO USO DOMESTIC.", label: "Venta minorista electrodom." },
  { value: "VTA.X MENOR DE ART.DE FERRETE.,PINTUR. Y PROD.DE VIDRIO", label: "Venta minorista ferreteria" },
  { value: "VTA.X MENOR DE OTROS PRODUCTOS DE ALMACENES ESPECIALIZ.", label: "Venta minorista especializada" },
  { value: "VTA.X MENOR DE PROD.TEXTIL.,PRENDAS,CALZ. Y ARTIC.CUERO", label: "Venta minorista textil" },
  { value: "OTROS TIPOS DE VTA. AL POR MENOR NO REALIZ. EN ALMACEN.", label: "Venta minorista otros" },
  { value: "OTRAS ACTIVIDADES DE SERVICIOS N.C.P.", label: "Servicios varios" },
  { value: "Otros", label: "Otra actividad" },
]

// Industrias del PIB (mismos nombres que el notebook). Por defecto, el API la deduce de la actividad.
const SECTOR_PIB_OPTIONS = [
  { value: "", label: "Segun la actividad" },
  { value: "Agropecuario, Pesca y Minería", label: "Agropecuario, pesca y mineria" },
  { value: "Industria manufacturera", label: "Industria manufacturera" },
  { value: "Energía eléctrica, Gas y Agua", label: "Energia electrica, gas y agua" },
  { value: "Construcción", label: "Construccion" },
  { value: "Comercio,  Alojamiento y Suministro de comidas y bebidas", label: "Comercio, alojamiento y comidas" },
  { value: "Transporte y almacenamiento, Información y Comunicaciones", label: "Transporte, informacion y comunicaciones" },
  { value: "Servicios financieros", label: "Servicios financieros" },
  { value: "Actividades profesionales y Arrendamiento", label: "Actividades profesionales y arrendamiento" },
  { value: "Actividades de administración pública", label: "Administracion publica" },
  { value: "Salud, Educación, Actividades inmobiliarias y Otros servicios", label: "Salud, educacion, inmobiliarias y otros" },
]

// Industria del PIB de cada actividad de la lista (mismo mapeo que el notebook, artifacts/macro.json).
// "Otros" no tiene industria asignada: se elige a mano.
const AGRO = "Agropecuario, Pesca y Minería"
const COMERCIO = "Comercio,  Alojamiento y Suministro de comidas y bebidas"
const INDUSTRIA_POR_ACTIVIDAD: Record<string, string> = {
  "EXPLOTACION GANADERA (EXCEPTO LECHERIA)": AGRO,
  "EXPLOTACION LECHERA": AGRO,
  "CUL.DE PROD.AGRI.EN COMB.CON CRIA DE ANIM. EXPLOT.MIXTA": AGRO,
  "TRANSPORTE DE CARGA POR CARRETERA": "Transporte y almacenamiento, Información y Comunicaciones",
  "CONST.DE EDIFICIOS COMPLET. O DE PARTES.OBR. DE ING.CIV": "Construcción",
  "VENTA AL POR MAYOR DE ALIMENTOS, BEBIDAS Y TABACO": COMERCIO,
  "VENTA AL POR MAYOR DE OTROS PRODUCTOS": COMERCIO,
  "VTA. MENOR ALMAC NO ESPECIALI.,DE ALIM.,BEB. TAB": COMERCIO,
  "VTA.X MENOR DE ALIM.,BEB.Y TABACO EN ALMACEN. ESPECIAL.": COMERCIO,
  "VTA.X MENOR DE APARATOS,ARTICUL.Y EQUIPO USO DOMESTIC.": COMERCIO,
  "VTA.X MENOR DE ART.DE FERRETE.,PINTUR. Y PROD.DE VIDRIO": COMERCIO,
  "VTA.X MENOR DE OTROS PRODUCTOS DE ALMACENES ESPECIALIZ.": COMERCIO,
  "VTA.X MENOR DE PROD.TEXTIL.,PRENDAS,CALZ. Y ARTIC.CUERO": COMERCIO,
  "OTROS TIPOS DE VTA. AL POR MENOR NO REALIZ. EN ALMACEN.": COMERCIO,
  "OTRAS ACTIVIDADES DE SERVICIOS N.C.P.": "Salud, Educación, Actividades inmobiliarias y Otros servicios",
}

type CompanyFormData = z.infer<typeof companySchema>

// Columnas del archivo que completan campos del formulario fuera de RAW_FEATURES
const ARCHIVO_SELECTS: Record<string, { key: "sector" | "tipo_sociedad" | "actividad_economica" | "grupo_economico" | "sector_pib"; options: { value: string }[] }> = {
  SECTOR: { key: "sector", options: SECTOR_OPTIONS },
  TIPO_SOCIEDAD: { key: "tipo_sociedad", options: TIPO_SOCIEDAD_OPTIONS },
  ACTIVIDAD_ECONOMICA: { key: "actividad_economica", options: ACTIVIDAD_ECONOMICA_OPTIONS },
  GRUPO_ECONOMICO: { key: "grupo_economico", options: GRUPO_ECONOMICO_OPTIONS },
  SECTOR_PIB: { key: "sector_pib", options: SECTOR_PIB_OPTIONS },
}
const ARCHIVO_NUMERICOS: Record<string, "numero_empleados" | "importe_mn"> = {
  NUMERO_EMPLEADOS: "numero_empleados",
  IMPORTE_MN: "importe_mn",
}
// Variaciones temporales ya calculadas: si vienen en el archivo, se envian al API tal cual
const esVariacion = (col: string) => col.startsWith("delta_")

// Formulario de estados contables del BROU (FORM_BCE 2018): se reconoce por sus hojas
const HOJAS_FORM_BCE = ["INFORMACIÓN GENERAL", "ACTIVO CORRIENTE", "ESTADO DEL RESULTADO INTEGRAL", "DETALLE DE PASIVOS FINANCIEROS"]
const esFormularioBce = (hojas: string[]) => {
  const normalizadas = new Set(hojas.map((h) => h.normalize("NFC").trim().toUpperCase()))
  return HOJAS_FORM_BCE.every((h) => normalizadas.has(h.normalize("NFC")))
}

interface ImportacionFormBce {
  campos: Record<string, string | number>
  avisos: string[]
}

interface CompanyFormProps {
  onSubmit: (data: CompanyFeatures, companyId?: string) => void
  loading?: boolean
}

// Build reverse map: apiName → form key (computed once)
const apiNameToKey: Record<string, string> = {}
for (const f of RAW_FEATURES) {
  apiNameToKey[f.apiName] = f.key
}

export function CompanyForm({ onSubmit, loading = false }: CompanyFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CompanyFormData>({
    resolver: zodResolver(companySchema),
  })

  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([])
  // Avisos del ultimo formulario del BROU importado
  const [avisosImportacion, setAvisosImportacion] = useState<string[]>([])
  const [importando, setImportando] = useState(false)
  // Si la actividad cargada (la propone el importador del BROU) no esta en la lista corta, se agrega como opcion.
  // Se calcula del valor actual, en el mismo render: si la opcion faltara, el select la borraria.
  const actividadActual = watch("actividad_economica")
  const actividadOptions =
    actividadActual && actividadActual !== "none" && !ACTIVIDAD_ECONOMICA_OPTIONS.some((o) => o.value === actividadActual)
      ? [...ACTIVIDAD_ECONOMICA_OPTIONS.slice(0, -1), { value: actividadActual, label: actividadActual },
         ACTIVIDAD_ECONOMICA_OPTIONS[ACTIVIDAD_ECONOMICA_OPTIONS.length - 1]]
      : ACTIVIDAD_ECONOMICA_OPTIONS
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Variaciones y balance del año anterior leidos del ultimo archivo cargado (se usan al predecir)
  const variacionesRef = useRef<Record<string, number>>({})
  const anteriorRef = useRef<Record<string, number>>({})

  // actividadLibre: actividad que se acepta aunque no este en la lista corta (la propone el importador del BROU)
  const applyParsedRow = (row: Record<string, string>, actividadLibre?: string) => {
    let count = 0
    const matchedKeys = new Set<string>()
    variacionesRef.current = {}
    anteriorRef.current = {}
    let actividadArchivo = ""
    let industriaArchivo = false

    for (const [col, rawVal] of Object.entries(row)) {
      const trimmedCol = col.trim()
      const texto = String(rawVal ?? "").trim()

      // Balance del año anterior: columnas "<partida> (anterior)", para calcular las variaciones
      if (trimmedCol.endsWith(SUFIJO_ANTERIOR)) {
        const num = parseFloat(texto)
        if (!isNaN(num)) {
          anteriorRef.current[trimmedCol.slice(0, -SUFIJO_ANTERIOR.length)] = num
          count++
        }
        continue
      }

      // Fecha de cierre del balance (YYYY-MM)
      if (trimmedCol === "FECHA_CIERRE") {
        const m = texto.match(/^(\d{4})-(\d{2})/)
        if (m) {
          setValue("fecha_cierre", `${m[1]}-${m[2]}`)
          count++
        }
        continue
      }

      // Cualitativas: solo se aceptan los valores que ofrece cada lista
      const sel = ARCHIVO_SELECTS[trimmedCol]
      if (sel) {
        const aceptada =
          sel.options.some((o) => o.value === texto) || (sel.key === "actividad_economica" && texto === actividadLibre)
        if (texto !== "" && aceptada) {
          setValue(sel.key, texto)
          if (sel.key === "actividad_economica") actividadArchivo = texto
          if (sel.key === "sector_pib") industriaArchivo = true
          count++
        }
        continue
      }

      const numKey = ARCHIVO_NUMERICOS[trimmedCol]
      if (numKey) {
        const num = parseFloat(texto)
        if (!isNaN(num)) {
          setValue(numKey, num, { shouldValidate: true })
          count++
        }
        continue
      }

      if (esVariacion(trimmedCol)) {
        const num = parseFloat(texto)
        if (!isNaN(num)) {
          variacionesRef.current[trimmedCol] = num
          count++
        }
        continue
      }

      const formKey = apiNameToKey[trimmedCol]
      if (!formKey) continue

      const num = parseFloat(String(rawVal))
      if (isNaN(num)) continue

      setValue(formKey as keyof CompanyFormData, num, { shouldValidate: true })
      matchedKeys.add(formKey)
      count++
    }

    // Industria del PIB: si el archivo no la trae, se deduce de la actividad
    if (!industriaArchivo && actividadArchivo) {
      setValue("sector_pib", INDUSTRIA_POR_ACTIVIDAD[actividadArchivo] ?? "")
    }

    // Las variables que no se extrajeron del archivo se marcan como 0.
    // Esto refleja la convencion contable: una linea ausente del balance
    // equivale a "no aplica" / monto nulo, no a "dato faltante".
    for (const field of RAW_FEATURES) {
      if (!matchedKeys.has(field.key)) {
        setValue(field.key as keyof CompanyFormData, 0, { shouldValidate: true })
      }
    }

    return count
  }

  // El API lee el formulario del BROU y devuelve los campos con los nombres del CSV de carga
  const importarFormularioBce = async (data: Uint8Array) => {
    setImportando(true)
    try {
      const response = await fetch("/api/importar", {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: data as BodyInit,
      })
      const r = await response.json()
      if (!response.ok) {
        toast.error(r.error || "No se pudo leer el formulario del BROU")
        return
      }
      const { campos, avisos } = r as ImportacionFormBce
      // Las cualitativas y la fecha de un archivo anterior no deben quedar si este no las trae
      for (const k of ["sector", "tipo_sociedad", "actividad_economica", "sector_pib", "fecha_cierre"] as const) {
        setValue(k, "")
      }
      // Es otra empresa: el importe de un archivo anterior no vale (el formulario del BROU no lo trae)
      setValue("numero_empleados", undefined)
      setValue("importe_mn", undefined)
      const actividad = typeof campos.ACTIVIDAD_ECONOMICA === "string" ? campos.ACTIVIDAD_ECONOMICA : undefined
      const fila = Object.fromEntries(Object.entries(campos).map(([k, v]) => [k, String(v)]))
      const count = applyParsedRow(fila, actividad)
      setValidationErrors([])
      setAvisosImportacion([
        ...avisos,
        "El formulario no trae el importe solicitado: completalo a mano antes de evaluar.",
      ])
      toast.success(
        `Formulario del BROU importado: ${count} campos`,
      )
    } catch {
      toast.error("No se pudo conectar con el API para leer el formulario")
    } finally {
      setImportando(false)
    }
  }

  const handleFileUpload = (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase()
    setAvisosImportacion([])

    if (ext === "csv") {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (!results.data || results.data.length === 0) {
            toast.error("El archivo CSV esta vacio o no se pudo leer")
            return
          }
          const row = results.data[0] as Record<string, string>
          const count = applyParsedRow(row)
          toast.success(`Se cargaron ${count} campos desde el archivo CSV`)
        },
        error: () => {
          toast.error("Error al leer el archivo CSV")
        },
      })
    } else if (ext === "xlsx" || ext === "xls") {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target?.result as ArrayBuffer)
          const workbook = XLSX.read(data, { type: "array", bookSheets: true })
          if (esFormularioBce(workbook.SheetNames)) {
            void importarFormularioBce(data)
            return
          }
          const libro = XLSX.read(data, { type: "array" })
          const firstSheet = libro.Sheets[libro.SheetNames[0]]
          const rows = XLSX.utils.sheet_to_json<Record<string, string>>(firstSheet)

          if (!rows || rows.length === 0) {
            toast.error("El archivo Excel esta vacio o no se pudo leer")
            return
          }

          const count = applyParsedRow(rows[0])
          toast.success(`Se cargaron ${count} campos desde el archivo Excel`)
        } catch {
          toast.error("Error al leer el archivo Excel")
        }
      }
      reader.onerror = () => {
        toast.error("Error al leer el archivo")
      }
      reader.readAsArrayBuffer(file)
    } else {
      toast.error("Formato no soportado. Usa archivos .csv, .xlsx o .xls")
    }

    // Reset the input so the same file can be re-uploaded
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleFormSubmit = (data: CompanyFormData) => {
    // 0. Las partidas del balance vacias valen 0, como en los datos de entrenamiento:
    // una partida que no figura en el balance es un monto nulo, no un dato faltante.
    const formValues: Record<string, number> = {}
    for (const field of RAW_FEATURES) {
      const value = data[field.key as keyof CompanyFormData] as number | undefined
      formValues[field.key] = value != null && !isNaN(value) ? value : 0
    }

    const errors = validateAccountingSums(formValues)
    if (errors.length > 0) {
      setValidationErrors(errors)
      return
    }
    setValidationErrors([])

    // 1. Map raw form values to API names
    const rawFeatures: Record<string, number | undefined> = {}
    for (const field of RAW_FEATURES) {
      rawFeatures[field.apiName] = formValues[field.key]
    }

    // 2. Auto-compute engineered features
    const engineered = computeEngineeredFeatures(rawFeatures)

    // 3. Merge raw + engineered, filtering out undefined
    const features: CompanyFeatures = {}
    for (const [key, val] of Object.entries(rawFeatures)) {
      if (val != null) features[key] = val
    }
    for (const [key, val] of Object.entries(engineered)) {
      if (val != null) features[key] = val
    }

    // 4. Variables cualitativas
    if (data.sector && data.sector !== "" && data.sector !== "none") {
      features["SECTOR"] = data.sector
    }
    if (data.tipo_sociedad && data.tipo_sociedad !== "" && data.tipo_sociedad !== "none") {
      features["TIPO_SOCIEDAD"] = data.tipo_sociedad
    }
    if (data.actividad_economica && data.actividad_economica !== "" && data.actividad_economica !== "none") {
      features["ACTIVIDAD_ECONOMICA"] = data.actividad_economica
    }
    // GRUPO_ECONOMICO: binario (1 = pertenece a grupo, 0 = no)
    if (data.grupo_economico && data.grupo_economico !== "" && data.grupo_economico !== "none") {
      features["GRUPO_ECONOMICO"] = parseFloat(data.grupo_economico)
    }
    // NUMERO_EMPLEADOS: cantidad
    if (data.numero_empleados != null && !isNaN(data.numero_empleados)) {
      features["NUMERO_EMPLEADOS"] = data.numero_empleados
    }
    // Macro: el API completa el PIB de la industria, el desempleo y sus variaciones con la fecha de cierre
    if (data.fecha_cierre) features["FECHA_CIERRE"] = data.fecha_cierre
    if (data.sector_pib && data.sector_pib !== "" && data.sector_pib !== "none") {
      features["SECTOR_PIB"] = data.sector_pib
    }
    if (data.importe_mn != null && !isNaN(data.importe_mn)) features["IMPORTE_MN"] = data.importe_mn

    // 5. tamaño_EMPRESA calculado desde ingresos operativos (criterio BCU, UI=6.4).
    // Clave con tilde y minuscula para matchear las columnas OHE del modelo
    // (tamaño_EMPRESA_Microempresa, _Pequena, _Mediana, _Grande).
    const ingresos = rawFeatures["Total Ingresos Operativos Netos"] || rawFeatures["Total Ingresos Operativos"]
    if (ingresos != null) {
      const UI = 6.4
      const ingresosUI = ingresos / UI
      let tamano: string
      if (ingresosUI <= 2_000_000) tamano = "Microempresa"
      else if (ingresosUI <= 10_000_000) tamano = "Pequena"
      else if (ingresosUI <= 75_000_000) tamano = "Mediana"
      else tamano = "Grande"
      features["tamaño_EMPRESA"] = tamano
    }

    // 6. Variaciones temporales: se calculan contra el balance del año anterior, si vino en el archivo.
    // Las variaciones que traiga el archivo directamente (delta_*, PIB_var_*, Desempleo_var_*) tienen prioridad.
    if (Object.keys(anteriorRef.current).length > 0) {
      for (const [key, val] of Object.entries(computeTemporalVariations(rawFeatures, anteriorRef.current))) {
        features[key] = val
      }
    }
    for (const [key, val] of Object.entries(variacionesRef.current)) {
      features[key] = val
    }

    onSubmit(features, data.company_id)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-5 w-5" />
          Datos de la Empresa
        </CardTitle>
        <CardDescription>
          Ingresa los datos financieros disponibles. Las partidas del balance que quedan vacias se toman como 0.
          Los ratios (ROA, ROE, etc.) se calculan automaticamente. Los costos y gastos (costo de lo vendido,
          gastos de administracion y ventas, amortizaciones, intereses perdidos e impuestos) se ingresan en positivo
          y las ganancias financieras (intereses ganados, diferencia de cambio ganada) en negativo, como en los
          balances con que se entreno el modelo.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
          {/* Company ID */}
          <div className="space-y-2">
            <Label htmlFor="company_id">RUT / ID Empresa (Opcional)</Label>
            <Input
              id="company_id"
              placeholder="12345678-9"
              {...register("company_id")}
            />
          </div>

          {/* Datos Cualitativos */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="sector">Sector</Label>
              <Select
                value={watch("sector") || ""}
                onValueChange={(val) => setValue("sector", val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sin datos" />
                </SelectTrigger>
                <SelectContent>
                  {SECTOR_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value || "none"} value={opt.value || "none"}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tipo_sociedad">Tipo de Sociedad</Label>
              <Select
                value={watch("tipo_sociedad") || ""}
                onValueChange={(val) => setValue("tipo_sociedad", val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sin datos" />
                </SelectTrigger>
                <SelectContent>
                  {TIPO_SOCIEDAD_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value || "none"} value={opt.value || "none"}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="actividad_economica">Actividad Economica</Label>
              {/* Se vuelve a montar cuando cambia la lista de opciones: si no, el select oculto de Radix ve el valor
                  nuevo antes que su opcion y lo reemplaza por "Sin datos" */}
              <Select
                key={actividadOptions === ACTIVIDAD_ECONOMICA_OPTIONS ? "lista" : `extra:${actividadActual}`}
                value={watch("actividad_economica") || ""}
                onValueChange={(val) => {
                  setValue("actividad_economica", val)
                  setValue("sector_pib", INDUSTRIA_POR_ACTIVIDAD[val] ?? "")
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sin datos" />
                </SelectTrigger>
                <SelectContent>
                  {actividadOptions.map((opt) => (
                    <SelectItem key={opt.value || "none"} value={opt.value || "none"}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="numero_empleados">Numero de Empleados</Label>
              <Input
                id="numero_empleados"
                type="number"
                min="0"
                step="1"
                placeholder="Ej. 12"
                {...register("numero_empleados", { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="grupo_economico">Integra Grupo Economico</Label>
              <Select
                value={watch("grupo_economico") || ""}
                onValueChange={(val) => setValue("grupo_economico", val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sin datos" />
                </SelectTrigger>
                <SelectContent>
                  {GRUPO_ECONOMICO_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value || "none"} value={opt.value || "none"}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Importe solicitado — variable de la operacion, separada de las macro. */}
          <div className="space-y-2">
            <Label htmlFor="importe_mn">Importe solicitado</Label>
            <Input
              id="importe_mn"
              type="number"
              step="any"
              placeholder="Ej. 5000000"
              aria-invalid={errors.importe_mn ? true : undefined}
              {...register("importe_mn", { valueAsNumber: true })}
            />
            {errors.importe_mn && (
              <p className="text-xs text-destructive">{String(errors.importe_mn.message)}</p>
            )}
          </div>

          {/* Variables macroeconomicas: el API las completa con la fecha de cierre y la actividad */}
          <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
            <p className="text-sm font-medium">Variables Macroeconómicas</p>
            <p className="text-xs text-muted-foreground">
              Con la fecha de cierre del balance, el sistema completa el PIB de la industria de la empresa, el
              desempleo y sus variaciones, con los mismos rezagos que en el entrenamiento.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="fecha_cierre" className="text-xs">Fecha de cierre del balance</Label>
                <Input id="fecha_cierre" type="month" className="h-9 text-sm" {...register("fecha_cierre")} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="sector_pib" className="text-xs">Industria (para el PIB)</Label>
                <Select
                  value={watch("sector_pib") || ""}
                  onValueChange={(val) => setValue("sector_pib", val)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Segun la actividad" />
                  </SelectTrigger>
                  <SelectContent>
                    {SECTOR_PIB_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value || "none"} value={opt.value || "none"}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* File Upload Drop Zone */}
          <div
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/25 p-6 transition-colors hover:border-muted-foreground/50 hover:bg-muted/50"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-8 w-8 text-muted-foreground/50" />
            <div className="text-center">
              <p className="text-sm font-medium">
                {importando ? "Leyendo el formulario del BROU..." : "Cargar archivo CSV o Excel"}
              </p>
              <p className="text-xs text-muted-foreground">
                El formulario de estados contables del BROU (FORM_BCE, versión 2018) se reconoce solo y completa
                todos los campos; revisá los avisos antes de evaluar. Para otros archivos: 
                las columnas deben coincidir con los nombres de los campos del modelo (ej: &quot;Caja&quot;, &quot;TOTAL ACTIVO&quot;, &quot;SECTOR&quot;, &quot;FECHA_CIERRE&quot;). Para calcular las variaciones, agregar el balance del año anterior con el sufijo &quot; (anterior)&quot; (ej: &quot;TOTAL ACTIVO (anterior)&quot;). Los costos y gastos van en positivo y las ganancias financieras en negativo. Se usa la primera fila de datos.
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleFileUpload(file)
              }}
            />
          </div>

          {/* Avisos del formulario del BROU importado */}
          {avisosImportacion.length > 0 && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
              <div className="mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                  Revisar antes de evaluar
                </p>
              </div>
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800 dark:text-amber-200">
                {avisosImportacion.map((aviso, i) => (
                  <li key={i}>{aviso}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Feature Tabs */}
          <Tabs defaultValue="activo_corriente" className="w-full">
            <TabsList className="flex flex-wrap h-auto gap-1 p-1">
              {CATEGORY_ORDER.map((cat) => (
                <TabsTrigger key={cat} value={cat} className="text-xs px-3 py-1.5">
                  {CATEGORY_LABELS[cat]}
                </TabsTrigger>
              ))}
            </TabsList>

            {CATEGORY_ORDER.map((cat) => {
              const fields = RAW_FEATURES.filter((f) => f.category === cat)
              return (
                <TabsContent key={cat} value={cat} className="space-y-4 mt-4">
                  <p className="text-sm text-muted-foreground">
                    {CATEGORY_LABELS[cat]} — {fields.length} campos
                  </p>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {fields.map((field) => (
                      <div key={field.key} className="space-y-1">
                        <Label htmlFor={field.key} className="text-xs">
                          {field.label}
                        </Label>
                        <Input
                          id={field.key}
                          type="number"
                          step="0.01"
                          className="h-9 text-sm"
                          {...register(field.key as keyof CompanyFormData, {
                            valueAsNumber: true,
                          })}
                        />
                      </div>
                    ))}
                  </div>
                </TabsContent>
              )
            })}
          </Tabs>

          {/* Validation Errors */}
          {validationErrors.length > 0 && (
            <div className="rounded-lg border border-red-300 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  Los datos contables no son consistentes
                </p>
              </div>
              <ul className="space-y-1 text-sm text-red-700 dark:text-red-300">
                {validationErrors.map((err, i) => (
                  <li key={i}>
                    <strong>{err.rule}:</strong> el valor ingresado es{" "}
                    {err.actual.toLocaleString("es-UY", { maximumFractionDigits: 2 })}, pero la suma de
                    componentes da{" "}
                    {err.expected.toLocaleString("es-UY", { maximumFractionDigits: 2 })}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Submit Buttons */}
          <div className="flex gap-3">
            <Button type="submit" className="flex-1" disabled={loading || importando}>
              {loading ? "Procesando..." : importando ? "Leyendo el formulario..." : "Evaluar Empresa"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                reset()
                setAvisosImportacion([])
                setValidationErrors([])
              }}
            >
              Limpiar
            </Button>
          </div>

        </form>
      </CardContent>
    </Card>
  )
}
