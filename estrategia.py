"""Detección de ventaja y tamaño de posición (Kelly fraccionado)."""
from dataclasses import dataclass
from typing import Optional

import config
from datos import Mercado


@dataclass
class Senal:
    mercado: Mercado
    modelo: str
    prob_modelo: float
    lado: str          # "SI" o "NO"
    precio: float      # precio pagado por acción del lado elegido (incluye costo)
    ventaja: float     # prob_lado - precio
    monto: float       # USD ficticios a invertir


def kelly(prob: float, precio: float) -> float:
    """Fracción óptima de Kelly para un contrato que paga 1 si gana."""
    if precio <= 0 or precio >= 1:
        return 0.0
    b = (1 - precio) / precio        # ganancia neta por dólar
    f = (prob * b - (1 - prob)) / b
    return max(f, 0.0)


def evaluar(m: Mercado, prob_si: float, modelo: str,
            banca: float, expuesto: float) -> Optional[Senal]:
    # Lado SÍ
    precio_si = m.precio_si + config.COSTO_EJECUCION
    ventaja_si = prob_si - precio_si
    # Lado NO
    precio_no = (1 - m.precio_si) + config.COSTO_EJECUCION
    ventaja_no = (1 - prob_si) - precio_no

    if ventaja_si >= ventaja_no:
        lado, precio, ventaja, prob_lado = "SI", precio_si, ventaja_si, prob_si
    else:
        lado, precio, ventaja, prob_lado = "NO", precio_no, ventaja_no, 1 - prob_si

    if ventaja < config.UMBRAL_VENTAJA:
        return None

    f = kelly(prob_lado, precio) * config.FRACCION_KELLY
    monto = min(f * banca, config.MAX_POR_OPERACION * banca)
    disponible = config.MAX_EXPOSICION_TOTAL * banca - expuesto
    monto = round(min(monto, disponible), 2)
    if monto < 1:
        return None
    return Senal(m, modelo, prob_si, lado, round(precio, 4), round(ventaja, 4), monto)
