"""
Generador de dataset simulado - Planta Concentradora Minera
=============================================================
Genera 4 tablas relacionadas (consistentes entre sí) que simulan
la operación de una planta de procesamiento de mineral:

  1. dim_equipos.csv          -> maestro de equipos
  2. fact_produccion.csv      -> producción diaria por equipo
  3. fact_paradas.csv         -> eventos de parada (fallas, mantenimiento, operativas)
  4. fact_mantenimiento.csv   -> órdenes de mantenimiento (ligadas a paradas correctivas)

Diseñado para practicar: modelo estrella en SQL Server, cálculo de KPIs
(disponibilidad mecánica, MTBF, MTTR, OEE) y dashboard en Power BI.

Los valores son 100% sintéticos, pero la estructura y las relaciones
imitan un reporte industrial real (turnos, horas operativas, causas de
parada, costos, órdenes de trabajo).
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

SEED = 42
rng = np.random.default_rng(SEED)

# -------------------------------------------------------------------
# 1) DIM_EQUIPOS - maestro de equipos (flujo de proceso de una planta
#    concentradora: chancado -> molienda -> flotación -> espesado -> filtrado)
# -------------------------------------------------------------------
equipos = [
    # equipo_id, nombre, area, tipo, capacidad_nominal_tmh, anio_instalacion, clase_confiabilidad
    ("EQ-01", "Chancadora Primaria",   "Chancado",    "Chancadora", 520, 2016, "media"),
    ("EQ-02", "Chancadora Secundaria", "Chancado",    "Chancadora", 430, 2016, "media"),
    ("EQ-03", "Chancadora Terciaria",  "Chancado",    "Chancadora", 380, 2019, "alta"),
    ("EQ-04", "Molino SAG",            "Molienda",    "Molino",     460, 2014, "baja"),
    ("EQ-05", "Molino de Bolas 1",     "Molienda",    "Molino",     300, 2014, "baja"),
    ("EQ-06", "Molino de Bolas 2",     "Molienda",    "Molino",     300, 2018, "media"),
    ("EQ-07", "Celda de Flotación",    "Flotación",   "Flotacion",  350, 2017, "alta"),
    ("EQ-08", "Espesador de Relave",   "Espesado",    "Espesador",  400, 2015, "media"),
    ("EQ-09", "Filtro Prensa",         "Filtrado",    "Filtro",     260, 2020, "alta"),
    ("EQ-10", "Faja Transportadora 3", "Chancado",    "Faja",       500, 2016, "media"),
]

dim_equipos = pd.DataFrame(
    equipos,
    columns=["equipo_id", "nombre_equipo", "area", "tipo_equipo",
             "capacidad_nominal_tmh", "anio_instalacion", "clase_confiabilidad"],
)

# Parámetros de confiabilidad -> horas promedio entre fallas (MTBF objetivo real, oculto)
# Calibrado para lograr disponibilidad mecánica realista (~85-92%) según clase
mtbf_objetivo = {"alta": 280, "media": 170, "baja": 105}   # horas operativas entre fallas
mttr_objetivo = {"alta": 5.0, "media": 8.0, "baja": 12.0}  # horas promedio de reparación

# -------------------------------------------------------------------
# Rango de fechas: 24 meses de operación diaria
# -------------------------------------------------------------------
fecha_inicio = date(2024, 1, 1)
fecha_fin = date(2025, 12, 31)
fechas = pd.date_range(fecha_inicio, fecha_fin, freq="D")
HORAS_DIA = 24.0

produccion_rows = []
paradas_rows = []
mantenimiento_rows = []

parada_id_counter = 1
orden_id_counter = 1

for _, eq in dim_equipos.iterrows():
    equipo_id = eq["equipo_id"]
    clase = eq["clase_confiabilidad"]
    cap_nominal = eq["capacidad_nominal_tmh"]
    mtbf_h = mtbf_objetivo[clase]
    mttr_h = mttr_objetivo[clase]

    horas_hasta_prox_falla = rng.exponential(mtbf_h)
    horas_acumuladas_operativas = 0.0

    # mantenimiento preventivo programado cada ~18 dias (+/- variacion)
    prox_preventivo = rng.integers(14, 24)
    dias_desde_ultimo_preventivo = 0

    for fecha in fechas:
        horas_parada_dia = 0.0
        eventos_hoy = []

        dias_desde_ultimo_preventivo += 1

        # --- Mantenimiento preventivo programado ---
        if dias_desde_ultimo_preventivo >= prox_preventivo:
            dur = round(rng.uniform(4, 9), 1)
            horas_parada_dia += dur
            eventos_hoy.append(("Preventiva", dur, "Mantenimiento programado (plan anual)"))
            dias_desde_ultimo_preventivo = 0
            prox_preventivo = rng.integers(14, 24)

        # --- Paradas operativas aleatorias (falta de mineral, corte de energia, clima) ---
        if rng.random() < 0.06:  # ~6% de dias con incidente operativo menor
            dur = round(rng.uniform(0.5, 3.0), 1)
            causa = rng.choice([
                "Falta de mineral en cancha",
                "Corte de energía externo",
                "Condiciones climáticas adversas",
                "Espera de insumos (reactivos/bolas de molienda)",
            ])
            horas_parada_dia += dur
            eventos_hoy.append(("Operativa", dur, causa))

        # --- Falla correctiva (según MTBF simulado por horas operativas) ---
        horas_disponibles_hoy = max(HORAS_DIA - horas_parada_dia, 0)
        horas_acumuladas_operativas += horas_disponibles_hoy
        if horas_acumuladas_operativas >= horas_hasta_prox_falla:
            dur = round(max(rng.exponential(mttr_h), 0.5), 1)
            dur = min(dur, 20.0)  # tope realista
            causa = rng.choice([
                "Falla mecánica - desgaste de componente",
                "Falla eléctrica - motor/tablero",
                "Rotura de faja/correa",
                "Atoro de mineral / obstrucción",
                "Falla de lubricación",
            ])
            horas_parada_dia = min(horas_parada_dia + dur, HORAS_DIA)
            eventos_hoy.append(("Correctiva", dur, causa))
            # reset del contador de horas hasta próxima falla
            horas_acumuladas_operativas = 0.0
            horas_hasta_prox_falla = rng.exponential(mtbf_h)

        horas_parada_dia = min(horas_parada_dia, HORAS_DIA)
        horas_operativas_dia = HORAS_DIA - horas_parada_dia

        # --- Producción del día ---
        # eficiencia con variación natural + leve degradación estacional aleatoria
        eficiencia = np.clip(rng.normal(0.90, 0.05), 0.55, 0.99)
        toneladas_procesadas = round(horas_operativas_dia * cap_nominal * eficiencia, 1)

        # dimensión de calidad: % de producción fuera de especificación
        pct_fuera_espec = np.clip(rng.normal(0.02, 0.008), 0.0, 0.15)
        toneladas_fuera_espec = round(toneladas_procesadas * pct_fuera_espec, 1)

        produccion_rows.append({
            "fecha": fecha.date(),
            "equipo_id": equipo_id,
            "horas_operativas": round(horas_operativas_dia, 1),
            "horas_parada": round(horas_parada_dia, 1),
            "toneladas_procesadas": toneladas_procesadas,
            "toneladas_fuera_especificacion": toneladas_fuera_espec,
            "capacidad_nominal_tmh": cap_nominal,
        })

        # --- Registrar eventos de parada del día ---
        for tipo_parada, dur, causa in eventos_hoy:
            pid = f"PAR-{parada_id_counter:05d}"
            parada_id_counter += 1
            hora_inicio = rng.integers(0, max(int(24 - dur), 1))
            paradas_rows.append({
                "parada_id": pid,
                "equipo_id": equipo_id,
                "fecha": fecha.date(),
                "hora_inicio_aprox": f"{hora_inicio:02d}:00",
                "duracion_horas": dur,
                "tipo_parada": tipo_parada,
                "causa": causa,
                "costo_estimado_soles": round(dur * rng.uniform(800, 2200), 0)
                    if tipo_parada != "Operativa" else round(dur * rng.uniform(200, 600), 0),
            })

            # Cada parada Correctiva o Preventiva genera una orden de mantenimiento
            if tipo_parada in ("Correctiva", "Preventiva"):
                oid = f"OT-{orden_id_counter:05d}"
                orden_id_counter += 1
                mantenimiento_rows.append({
                    "orden_id": oid,
                    "parada_id": pid,
                    "equipo_id": equipo_id,
                    "fecha_apertura": fecha.date(),
                    "tipo_orden": tipo_parada,
                    "horas_hombre": round(dur * rng.uniform(0.8, 1.6), 1),
                    "num_tecnicos": int(rng.integers(1, 4)),
                    "repuesto_principal": rng.choice([
                        "Rodamiento", "Faja/correa", "Sello mecánico", "Motor eléctrico",
                        "Revestimiento (liner)", "Sensor/instrumento", "Ninguno (solo mano de obra)"
                    ]),
                    "costo_repuestos_soles": round(rng.uniform(0, 8000), 0)
                        if tipo_parada == "Correctiva" else round(rng.uniform(0, 2500), 0),
                })

dim_equipos_out = dim_equipos.copy()
fact_produccion = pd.DataFrame(produccion_rows)
fact_paradas = pd.DataFrame(paradas_rows)
fact_mantenimiento = pd.DataFrame(mantenimiento_rows)

# -------------------------------------------------------------------
# Validaciones de consistencia básicas
# -------------------------------------------------------------------
assert fact_produccion["horas_operativas"].between(0, 24).all()
assert (fact_produccion["horas_operativas"] + fact_produccion["horas_parada"]).round(1).le(24.01).all()
assert fact_paradas["equipo_id"].isin(dim_equipos_out["equipo_id"]).all()
assert fact_mantenimiento["equipo_id"].isin(dim_equipos_out["equipo_id"]).all()
assert fact_mantenimiento["parada_id"].isin(fact_paradas["parada_id"]).all()

# -------------------------------------------------------------------
# Guardar CSVs
# -------------------------------------------------------------------
out_dir = "/home/claude/mining_sim"
dim_equipos_out.to_csv(f"{out_dir}/dim_equipos.csv", index=False, encoding="utf-8-sig")
fact_produccion.to_csv(f"{out_dir}/fact_produccion.csv", index=False, encoding="utf-8-sig")
fact_paradas.to_csv(f"{out_dir}/fact_paradas.csv", index=False, encoding="utf-8-sig")
fact_mantenimiento.to_csv(f"{out_dir}/fact_mantenimiento.csv", index=False, encoding="utf-8-sig")

print("dim_equipos:", dim_equipos_out.shape)
print("fact_produccion:", fact_produccion.shape)
print("fact_paradas:", fact_paradas.shape)
print("fact_mantenimiento:", fact_mantenimiento.shape)
print()
print("Resumen paradas por tipo:")
print(fact_paradas["tipo_parada"].value_counts())
print()
print("Ejemplo disponibilidad mecánica global:")
disp = 1 - (fact_produccion["horas_parada"].sum() / (len(fact_produccion) * 24))
print(f"{disp:.2%}")
