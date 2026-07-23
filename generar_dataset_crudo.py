"""
Generador de dataset CRUDO (versión con desafíos de calidad de datos)
=======================================================================
Parte de la base limpia ya generada (fact_produccion.csv, fact_paradas.csv,
fact_mantenimiento.csv) y la transforma para simular cómo llegaría la
información realmente desde la planta, ANTES de cualquier limpieza:

  Escenario simulado: la planta migró de un sistema antiguo (reporte manual/
  Excel) a un sistema nuevo (más estructurado) el 1 de enero de 2025.
  Debes reconciliar ambos esquemas en una sola tabla limpia.

Salidas:
  - fact_produccion_2024_sistema_legacy.csv   (esquema viejo, en español,
      fechas DD/MM/YYYY, IDs de equipo inconsistentes, duplicados con
      corrección posterior, nulos, outliers)
  - fact_produccion_2025_sistema_nuevo.csv    (esquema nuevo, mayormente
      limpio, PERO con un tramo de 3 meses en 2 equipos reportado a nivel
      de turno en vez de diario -> hay que re-agregar)
  - fact_paradas_raw.csv                      (duplicados, texto sin
      estandarizar, fechas mixtas, nulos)
  - fact_mantenimiento_raw.csv                (nulos leves, duplicado leve)

dim_equipos.csv se mantiene igual (maestro de equipos, normalmente sí se
cuida en una empresa real).

Todo el "desorden" es determinístico (semilla fija) y reconciliable: existe
una única verdad subyacente (los CSV limpios originales).
"""

import numpy as np
import pandas as pd
from datetime import timedelta

SEED = 7
rng = np.random.default_rng(SEED)

BASE = "/home/claude/mining_sim"

# -------------------------------------------------------------------
# Cargar la verdad base (ya generada y validada)
# -------------------------------------------------------------------
fp = pd.read_csv(f"{BASE}/fact_produccion.csv", parse_dates=["fecha"])
fpar = pd.read_csv(f"{BASE}/fact_paradas.csv", parse_dates=["fecha"])
fm = pd.read_csv(f"{BASE}/fact_mantenimiento.csv", parse_dates=["fecha_apertura"])

# =====================================================================
# 1) FACT_PRODUCCION -> se parte en dos archivos con esquema distinto
# =====================================================================
fp_2024 = fp[fp["fecha"].dt.year == 2024].copy()
fp_2025 = fp[fp["fecha"].dt.year == 2025].copy()

# ---------- Formatos de equipo_id "sucios" (usados en ambos archivos) ----------
def id_sucio(equipo_id, rng_local):
    variante = rng_local.integers(0, 5)
    if variante == 0:
        return equipo_id  # correcto
    elif variante == 1:
        return equipo_id.replace("-", "")          # "EQ01"
    elif variante == 2:
        return equipo_id.lower()                   # "eq-01"
    elif variante == 3:
        return f" {equipo_id}"                      # espacio inicial
    else:
        return equipo_id + " "                      # espacio final

# =====================================================================
# 1A) SISTEMA LEGACY (2024) - esquema viejo, en español, columnas propias
# =====================================================================
n = len(fp_2024)

legacy = pd.DataFrame({
    "Fecha": fp_2024["fecha"].dt.strftime("%d/%m/%Y"),
    "Cod_Equipo": [id_sucio(e, rng) for e in fp_2024["equipo_id"]],
    "Horas_Trab": fp_2024["horas_operativas"].round(1),
    "Horas_Parada": fp_2024["horas_parada"].round(1),
    "Ton_Producidas": fp_2024["toneladas_procesadas"].round(1),
    "Ton_Rechazo": fp_2024["toneladas_fuera_especificacion"].round(1),
    "Cap_Nominal_TMH": fp_2024["capacidad_nominal_tmh"],
})
# timestamp de carga original (todo cargado "a tiempo")
legacy["Fecha_Carga"] = fp_2024["fecha"] + pd.to_timedelta(1, unit="D")

# --- Nulos (~4% en Horas_Parada, ~3% en Ton_Rechazo) ---
mask_null_hp = rng.random(n) < 0.04
legacy.loc[mask_null_hp, "Horas_Parada"] = np.nan
mask_null_tr = rng.random(n) < 0.03
legacy.loc[mask_null_tr, "Ton_Rechazo"] = np.nan

# --- Outliers / errores de digitación (~1%): Horas_Trab > 24 ---
mask_outlier = rng.random(n) < 0.01
idx_outlier = legacy[mask_outlier].index
legacy.loc[idx_outlier, "Horas_Trab"] = legacy.loc[idx_outlier, "Horas_Trab"] + rng.uniform(3, 8, len(idx_outlier))

# --- Duplicados "con corrección posterior" (~3%) ---
# Se re-envía el registro con un valor de producción distinto y carga posterior.
# La regla de reconciliación: se debe quedar con el de Fecha_Carga más reciente.
idx_dup_source = rng.choice(legacy.index, size=int(n * 0.03), replace=False)
dup_rows = legacy.loc[idx_dup_source].copy()
dup_rows["Ton_Producidas"] = (dup_rows["Ton_Producidas"] * rng.uniform(0.85, 0.93, len(dup_rows))).round(1)
dup_rows["Fecha_Carga"] = pd.to_datetime(dup_rows["Fecha_Carga"]) - pd.to_timedelta(
    rng.integers(1, 4, len(dup_rows)), unit="D")  # la version "incorrecta" se cargó ANTES

legacy_final = pd.concat([legacy, dup_rows], ignore_index=True)
legacy_final = legacy_final.sample(frac=1.0, random_state=SEED).reset_index(drop=True)  # desordenar filas
legacy_final["Fecha_Carga"] = pd.to_datetime(legacy_final["Fecha_Carga"]).dt.strftime("%Y-%m-%d %H:%M:%S")

legacy_final.to_csv(f"{BASE}/fact_produccion_2024_sistema_legacy.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 1B) SISTEMA NUEVO (2025) - esquema limpio, PERO con problema de GRANO
#     en 2 equipos durante un trimestre (reportado por turno, no por día)
# =====================================================================
nuevo = fp_2025.rename(columns={
    "equipo_id": "equipo_id",
    "horas_operativas": "horas_operativas",
    "horas_parada": "horas_parada",
    "toneladas_procesadas": "toneladas_procesadas",
    "toneladas_fuera_especificacion": "toneladas_fuera_especificacion",
    "capacidad_nominal_tmh": "capacidad_nominal_tmh",
}).copy()
nuevo["turno"] = np.nan  # normalmente no se reporta por turno

EQUIPOS_CON_PROBLEMA = ["EQ-04", "EQ-06"]
INICIO_VENTANA = pd.Timestamp("2025-04-01")
FIN_VENTANA = pd.Timestamp("2025-06-30")

filas_normales = []
filas_turno = []

for _, row in nuevo.iterrows():
    en_ventana = (
        row["equipo_id"] in EQUIPOS_CON_PROBLEMA
        and INICIO_VENTANA <= row["fecha"] <= FIN_VENTANA
    )
    if not en_ventana:
        filas_normales.append(row.to_dict())
        continue

    # Repartir el día en 3 turnos que SUMAN exactamente el total original
    pesos_h = rng.dirichlet(np.ones(3))  # reparto de horas operativas
    pesos_par = rng.dirichlet(np.ones(3))  # reparto de horas de parada (independiente)
    pesos_ton = pesos_h + rng.normal(0, 0.02, 3)
    pesos_ton = np.clip(pesos_ton, 0.01, None)
    pesos_ton = pesos_ton / pesos_ton.sum()
    pesos_rech = rng.dirichlet(np.ones(3))

    horas_turno = np.round(row["horas_operativas"] * pesos_h, 2)
    horas_turno[-1] = round(row["horas_operativas"] - horas_turno[:2].sum(), 2)  # ajuste exacto

    parada_turno = np.round(row["horas_parada"] * pesos_par, 2)
    parada_turno[-1] = round(row["horas_parada"] - parada_turno[:2].sum(), 2)

    ton_turno = np.round(row["toneladas_procesadas"] * pesos_ton, 1)
    ton_turno[-1] = round(row["toneladas_procesadas"] - ton_turno[:2].sum(), 1)

    rech_turno = np.round(row["toneladas_fuera_especificacion"] * pesos_rech, 1)
    rech_turno[-1] = round(row["toneladas_fuera_especificacion"] - rech_turno[:2].sum(), 1)

    for t in range(3):
        filas_turno.append({
            "fecha": row["fecha"],
            "equipo_id": row["equipo_id"],
            "turno": t + 1,
            "horas_operativas": horas_turno[t],
            "horas_parada": parada_turno[t],
            "toneladas_procesadas": ton_turno[t],
            "toneladas_fuera_especificacion": rech_turno[t],
            "capacidad_nominal_tmh": row["capacidad_nominal_tmh"],
        })

nuevo_final = pd.DataFrame(filas_normales + filas_turno)

# --- Nulos leves (~2% en toneladas_fuera_especificacion) ---
mask_null = rng.random(len(nuevo_final)) < 0.02
nuevo_final.loc[nuevo_final.sample(frac=1, random_state=SEED)[mask_null[:len(nuevo_final)]].index[:int(len(nuevo_final)*0.02)],
                "toneladas_fuera_especificacion"] = np.nan

# --- Duplicados exactos accidentales (~1%, doble exportación) ---
idx_dup2 = rng.choice(nuevo_final.index, size=int(len(nuevo_final) * 0.01), replace=False)
nuevo_final = pd.concat([nuevo_final, nuevo_final.loc[idx_dup2]], ignore_index=True)
nuevo_final = nuevo_final.sample(frac=1.0, random_state=SEED + 1).reset_index(drop=True)

nuevo_final["fecha"] = pd.to_datetime(nuevo_final["fecha"]).dt.strftime("%Y-%m-%d")
nuevo_final.to_csv(f"{BASE}/fact_produccion_2025_sistema_nuevo.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 2) FACT_PARADAS -> versión cruda
# =====================================================================
fpar_raw = fpar.copy()
n2 = len(fpar_raw)

# --- IDs de equipo sucios ---
fpar_raw["equipo_id"] = [id_sucio(e, rng) for e in fpar_raw["equipo_id"]]

# --- Fechas mixtas (40% en DD/MM/YYYY, resto ISO) ---
mask_fecha_alt = rng.random(n2) < 0.40
fechas_str = fpar_raw["fecha"].dt.strftime("%Y-%m-%d")
fechas_alt = fpar_raw["fecha"].dt.strftime("%d/%m/%Y")
fpar_raw["fecha"] = np.where(mask_fecha_alt, fechas_alt, fechas_str)

# --- tipo_parada con casing/espacios inconsistentes ---
def ensuciar_texto(txt, rng_local):
    variante = rng_local.integers(0, 4)
    if variante == 0:
        return txt
    elif variante == 1:
        return txt.upper()
    elif variante == 2:
        return f" {txt.lower()}"
    else:
        return f"{txt} "

fpar_raw["tipo_parada"] = [ensuciar_texto(t, rng) for t in fpar_raw["tipo_parada"]]

# --- Nulos en causa (~5%) y costo_estimado_soles (~4%) ---
mask_null_causa = rng.random(n2) < 0.05
fpar_raw.loc[mask_null_causa, "causa"] = np.nan
mask_null_costo = rng.random(n2) < 0.04
fpar_raw.loc[mask_null_costo, "costo_estimado_soles"] = np.nan

# --- Outlier: duracion_horas negativa por error de digitación (~0.5%) ---
mask_neg = rng.random(n2) < 0.005
fpar_raw.loc[mask_neg, "duracion_horas"] = -fpar_raw.loc[mask_neg, "duracion_horas"]

# --- Duplicados exactos (~2%) ---
idx_dup3 = rng.choice(fpar_raw.index, size=int(n2 * 0.02), replace=False)
fpar_raw = pd.concat([fpar_raw, fpar_raw.loc[idx_dup3]], ignore_index=True)
fpar_raw = fpar_raw.sample(frac=1.0, random_state=SEED + 2).reset_index(drop=True)

fpar_raw.to_csv(f"{BASE}/fact_paradas_raw.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 3) FACT_MANTENIMIENTO -> ensuciado leve (dato normalmente mejor cuidado)
# =====================================================================
fm_raw = fm.copy()
n3 = len(fm_raw)
mask_null_rep = rng.random(n3) < 0.02
fm_raw.loc[mask_null_rep, "repuesto_principal"] = np.nan
idx_dup4 = rng.choice(fm_raw.index, size=max(int(n3 * 0.01), 1), replace=False)
fm_raw = pd.concat([fm_raw, fm_raw.loc[idx_dup4]], ignore_index=True)
fm_raw = fm_raw.sample(frac=1.0, random_state=SEED + 3).reset_index(drop=True)
fm_raw.to_csv(f"{BASE}/fact_mantenimiento_raw.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# Resumen
# =====================================================================
print("fact_produccion_2024_sistema_legacy.csv:", legacy_final.shape)
print("fact_produccion_2025_sistema_nuevo.csv  :", nuevo_final.shape)
print("fact_paradas_raw.csv                    :", fpar_raw.shape)
print("fact_mantenimiento_raw.csv               :", fm_raw.shape)
