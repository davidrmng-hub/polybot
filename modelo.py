"""Modelos de pronóstico. Cada uno devuelve P(Sí) o None si no opina.

Aquí está la ventaja real del bot. Empieza con tus propios pronósticos
(modelo manual) y agrega modelos a medida que encuentres señales.
"""
import csv
import math
import os
from typing import Optional

import config
from datos import Mercado


class ModeloManual:
    """Lee tus pronósticos de mis_pronosticos.csv  (columnas: mercado_id,prob_si,nota).

    Es la forma más honesta de empezar: tú eres el modelo, el bot mide si aciertas.
    """
    nombre = "manual"

    def __init__(self, db=None, ruta: str = config.PRONOSTICOS_CSV):
        self.prons: dict[str, float] = {}
        if db is not None:  # pronósticos guardados desde el dashboard
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


class ModeloSesgoLongshot:
    """Modelo base: corrige el 'sesgo del favorito-longshot'.

    En mercados de apuestas los resultados poco probables suelen estar
    sobrevalorados. Este modelo comprime los extremos hacia lo que suele
    pasar en realidad. Es una línea base, NO una estrategia ganadora
    garantizada: sirve para comparar contra tus otros modelos.
    """
    nombre = "longshot"

    def __init__(self, k: float = 1.1):
        self.k = k  # >1 aleja los extremos del 50% (castiga longshots)

    def estimar(self, m: Mercado) -> Optional[float]:
        p = min(max(m.precio_si, 1e-4), 1 - 1e-4)
        logit = math.log(p / (1 - p)) * self.k
        return 1 / (1 + math.exp(-logit))


def modelos_disponibles(db=None) -> list:
    return [ModeloManual(db), ModeloSesgoLongshot()]
