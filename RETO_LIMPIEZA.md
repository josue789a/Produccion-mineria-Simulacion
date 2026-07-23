# El reto: reconciliar datos "crudos" antes de cargarlos a SQL Server

## Escenario simulado

La planta migró de un **sistema antiguo** (reporte manual/Excel, en español,
con nomenclatura propia) a un **sistema nuevo** el 1 de enero de 2025. Tu
trabajo es escribir el pipeline en Python que toma estos archivos crudos y
produce las 4 tablas limpias y consistentes (el mismo esquema del
`README.md` original) listas para cargar a SQL Server.

**No se te dice exactamente qué está mal en cada archivo — parte de la tarea
es descubrirlo, como pasaría con datos reales.** Abajo van pistas generales
por categoría, no una lista fila por fila.

## Archivos de entrada (crudos)

| Archivo | Qué representa |
|---|---|
| `fact_produccion_2024_sistema_legacy.csv` | Producción 2024, esquema del sistema viejo |
| `fact_produccion_2025_sistema_nuevo.csv` | Producción 2025, esquema del sistema nuevo |
| `fact_paradas_raw.csv` | Eventos de parada, sin estandarizar |
| `fact_mantenimiento_raw.csv` | Órdenes de mantenimiento, con detalles menores por resolver |
| `dim_equipos.csv` | Maestro de equipos (este SÍ está limpio — el dato maestro se cuida más en una empresa real) |

## Categorías de problemas a resolver (pistas, no respuestas)

### 1. Esquemas distintos entre 2024 y 2025
Los nombres de columna, el idioma y el orden de campos no coinciden entre
los dos archivos de producción. Antes de unirlos necesitas un mapeo
explícito columna-a-columna hacia un esquema común.

### 2. Formatos de fecha inconsistentes
No asumas un solo formato de fecha por archivo — revisa si dentro del mismo
archivo conviven distintos formatos.

### 3. Identificadores de equipo sin estandarizar
El código de equipo no siempre viene escrito igual. Antes de cualquier
`JOIN` o `groupby` vas a necesitar una función de normalización robusta.

### 4. Valores nulos
Aparecen en más de un campo, en más de un archivo. Para cada uno, decide
(y **documenta en tu README** por qué) si corresponde imputar, descartar,
o dejar como nulo intencional.

### 5. Outliers / errores de digitación
Al menos un campo numérico tiene valores fuera de rango físicamente
posible. Piensa qué regla de negocio usarías para detectarlos (¿un límite
fijo? ¿un percentil? ¿compararlo contra la capacidad nominal?).

### 6. Duplicados — y no todos son iguales
Hay duplicados exactos (fáciles: se descartan). Pero también hay **registros
que se repiten con un valor distinto** — como si la planta hubiera reenviado
una corrección. Para esos, necesitas un criterio para decidir cuál de las
dos versiones es la válida (pista: revisa si hay algún campo de fecha/hora
de carga que te pueda servir de criterio de desempate).

### 7. Grano inconsistente
En un archivo, no todas las filas representan lo mismo: la mayoría son
totales diarios, pero un subconjunto (identificable por equipo y rango de
fechas) viene desagregado a un nivel más fino. Vas a necesitar **detectar
ese subconjunto y re-agregarlo** al mismo grano que el resto antes de
poder unir todo en una sola tabla consistente.

### 8. Texto sin estandarizar
Algunas categorías de texto (por ejemplo, el tipo de evento) están
escritas con mayúsculas/minúsculas y espacios inconsistentes — antes de
agrupar por esa columna, hay que normalizarla.

## Cómo saber si lo resolviste bien

El dataset fue construido para que **exista una única solución correcta**:
si aplicas las técnicas adecuadas, tu tabla final de producción debería
tener exactamente el mismo número de filas (una por equipo-día, sin huecos
ni sobrantes) que el rango de fechas y equipos lo permite, y los totales
mensuales por equipo deberían ser estables (sin saltos irreales de un mes a
otro debido a duplicados no resueltos o grano mal agregado).

Como ejercicio de auto-validación, calcula el total de toneladas procesadas
por equipo y por mes, y revisa si las cifras se ven razonables y sin saltos
sospechosos — esa es la señal más simple de que la reconciliación quedó
bien hecha.

## Recomendación de documentación para tu README de GitHub

Cuando subas el proyecto, documenta cada decisión de limpieza como una
mini "bitácora de decisiones": qué problema encontraste, qué criterio
usaste para resolverlo, y por qué. Esa bitácora es, en la práctica, la
evidencia más fuerte de que hiciste el trabajo real de un analista/
ingeniero de datos — mucho más que el dashboard final.
