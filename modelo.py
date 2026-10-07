"""Modelos de pronóstico. Cada uno devuelve P(Sí) o None si no opina.

- manual: tus propios pronósticos (dashboard o mis_pronosticos.csv)
- ia: el analista con IA (ia.py). Solo opera si su confianza no es "baja".
"""
import csv
import os
from typing import Optional

import config
from datos import Mercado


class ModeloManual:
    nombre = "manual"

    def __init__(self, db=None, ruta: str = config.PRONOSTICOS_CSV):
        self.prons: dict[str, float] = {}
        if db is not None:
            import cartera
            for mid, p in cartera.pronosticos(db).items():
                self.prons[mid] = float(p["prob_si"])
        if os.path.exists(ruta):
            with open(ruta, newline="", encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    try:
                        self.prons[fila["mercado_id"].strip()] = float(fila["prob_si"])
                    except (KeyError, ValueError):
                        continue

    def estimar(self, m: Mercado) -> Optional[float]:
        return self.prons.get(m.id)


class ModeloIA:
    nombre = "ia"

    def __init__(self, db=None):
        self.analisis = {}
        if db is not None:
            import cartera
            self.analisis = cartera.ultimos_analisis(db)

    def estimar(self, m: Mercado) -> Optional[float]:
        a = self.analisis.get(m.id)
        if not a or a["confianza"] == "baja":
            return None
        return float(a["prob"])


def modelos_disponibles(db=None) -> list:
    return [ModeloManual(db), ModeloIA(db)]
