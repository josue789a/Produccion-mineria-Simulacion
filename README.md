# Dataset simulado — Planta Concentradora Minera

Dataset 100% sintético (semilla fija, reproducible) que simula la operación de
una planta de procesamiento de mineral durante 24 meses (2024-01-01 a 2025-12-31).
Diseñado como base para un proyecto de portafolio: ingesta → SQL Server →
cálculo de KPIs → Power BI.

La estructura y las relaciones imitan un reporte industrial real (turnos,
horas operativas, causas de parada, órdenes de trabajo), pero **ningún valor
proviene de datos reales de ninguna empresa**.

## Modelo de datos (4 tablas, esquema estrella)

```
dim_equipos (10 filas)
      │
      ├──< fact_produccion (7,310 filas)   [1 fila por equipo-día]
      │
      └──< fact_paradas (1,773 filas)      [1 fila por evento de parada]
                  │
                  └──< fact_mantenimiento (1,328 filas)  [1 fila por orden de trabajo]
```

Flujo de proceso simulado: **Chancado → Molienda → Flotación → Espesado → Filtrado**
(10 equipos distribuidos en esas 5 áreas).

## Diccionario de datos

### `dim_equipos.csv`
| Campo | Tipo | Descripción |
|---|---|---|
| equipo_id | texto | Llave primaria (EQ-01 … EQ-10) |
| nombre_equipo | texto | Nombre descriptivo |
| area | texto | Chancado / Molienda / Flotación / Espesado / Filtrado |
| tipo_equipo | texto | Chancadora, Molino, Flotacion, Espesador, Filtro, Faja |
| capacidad_nominal_tmh | numérico | Toneladas métricas por hora, a capacidad plena |
| anio_instalacion | numérico | Año de puesta en marcha |
| clase_confiabilidad | texto | alta / media / baja — controla la frecuencia de fallas simuladas |

### `fact_produccion.csv` (grano: equipo + día)
| Campo | Descripción |
|---|---|
| fecha | Fecha (diaria) |
| equipo_id | FK a dim_equipos |
| horas_operativas | Horas que el equipo estuvo produciendo (máx. 24) |
| horas_parada | Horas detenido (correctiva + preventiva + operativa) |
| toneladas_procesadas | Producción real del día |
| toneladas_fuera_especificacion | Producción que no cumplió especificación de calidad |
| capacidad_nominal_tmh | Referencia de capacidad teórica (para calcular rendimiento) |

### `fact_paradas.csv` (grano: 1 fila por evento de parada)
| Campo | Descripción |
|---|---|
| parada_id | Llave primaria |
| equipo_id | FK a dim_equipos |
| fecha | Fecha del evento |
| hora_inicio_aprox | Hora aproximada de inicio |
| duracion_horas | Duración del evento |
| tipo_parada | Correctiva / Preventiva / Operativa |
| causa | Causa raíz (texto libre categorizado) |
| costo_estimado_soles | Costo estimado del evento (producción perdida + intervención) |

### `fact_mantenimiento.csv` (grano: 1 fila por orden de trabajo)
Solo existe para paradas **Correctiva** y **Preventiva** (las Operativas no generan
orden de mantenimiento, porque no son una falla de equipo).

| Campo | Descripción |
|---|---|
| orden_id | Llave primaria |
| parada_id | FK a fact_paradas |
| equipo_id | FK a dim_equipos |
| fecha_apertura | Fecha de la orden |
| tipo_orden | Correctiva / Preventiva |
| horas_hombre | Horas-hombre invertidas |
| num_tecnicos | Técnicos asignados |
| repuesto_principal | Repuesto/insumo principal usado |
| costo_repuestos_soles | Costo de repuestos de la orden |

## KPIs sugeridos (fórmulas para tus medidas DAX / SQL)

**Disponibilidad mecánica**
```
Disponibilidad = (Horas totales − Horas de parada) / Horas totales
```

**MTBF — Mean Time Between Failures** (usar solo paradas tipo "Correctiva")
```
MTBF = Horas operativas totales del periodo / N° de fallas correctivas
```

**MTTR — Mean Time To Repair** (usar solo paradas tipo "Correctiva")
```
MTTR = Suma de duracion_horas (Correctiva) / N° de fallas correctivas
```

**OEE — Overall Equipment Effectiveness**
```
Disponibilidad = Horas operativas / Horas totales
Rendimiento    = Toneladas procesadas / (Horas operativas × Capacidad nominal)
Calidad        = (Toneladas procesadas − Toneladas fuera de especificación) / Toneladas procesadas

OEE = Disponibilidad × Rendimiento × Calidad
```

**Costo total de no confiabilidad** (para el ángulo "traducir a dinero" que
valoran los reclutadores)
```
Costo total = SUM(fact_paradas.costo_estimado_soles) + SUM(fact_mantenimiento.costo_repuestos_soles)
```

## Ideas para llevarlo más allá de un dashboard

1. **Ranking de equipos por confiabilidad** — comparar MTBF/MTTR entre los 10
   equipos y priorizar cuáles necesitan repotenciación.
2. **Costo evitable** — si el equipo con peor disponibilidad llegara al
   promedio de su área, ¿cuántas toneladas/soles adicionales se producirían?
3. **Modelo simple de predicción de falla** — con `horas_operativas` acumuladas
   desde la última correctiva como variable, entrenar un modelo de riesgo básico
   (esto es opcional y solo tiene sentido si documentas honestamente que es
   sobre datos simulados).
4. **Extender el generador**: puedes pedir que se agregue estacionalidad,
   turnos (día/noche) en vez de agregados diarios, o más equipos/plantas.

## Reproducibilidad

Generado con `generar_dataset.py` (semilla fija `SEED = 42`). Puedes volver a
correrlo para regenerar los mismos datos, o cambiar la semilla / parámetros de
MTBF-MTTR por clase de confiabilidad para obtener variantes distintas.
