"""Lectura de mercados públicos de Polymarket (solo lectura, sin cuenta)."""
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

import requests

import config


@dataclass
class Mercado:
    id: str
    pregunta: str
    slug: str
    precio_si: float          # precio del resultado "Yes" (= probabilidad implícita)
    volumen: float
    liquidez: float
    fecha_fin: str
    cerrado: bool
    categoria: str = ""
    descripcion: str = ""

    def dias_para_cierre(self) -> Optional[float]:
        if not self.fecha_fin:
            return None
        try:
            fin = datetime.fromisoformat(self.fecha_fin.replace("Z", "+00:00"))
        except ValueError:
            return None
        return (fin - datetime.now(timezone.utc)).total_seconds() / 86400

    @property
    def url(self) -> str:
        return f"https://polymarket.com/market/{self.slug}"


def _parse(m: dict) -> Optional[Mercado]:
    try:
        outcomes = json.loads(m.get("outcomes") or "[]")
        precios = [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]
    except (ValueError, TypeError):
        return None
    # Solo mercados binarios Sí/No
    if len(outcomes) != 2 or len(precios) != 2:
        return None
    nombres = [str(o).strip().lower() for o in outcomes]
    if sorted(nombres) != ["no", "yes"]:   # solo mercados Sí/No
        return None
    idx_si = nombres.index("yes")
    return Mercado(
        id=str(m.get("id")),
        pregunta=m.get("question", ""),
        slug=m.get("slug", ""),
        precio_si=precios[idx_si],
        volumen=float(m.get("volumeNum") or m.get("volume") or 0),
        liquidez=float(m.get("liquidityNum") or m.get("liquidity") or 0),
        fecha_fin=m.get("endDate", "") or "",
        cerrado=bool(m.get("closed")),
        categoria=m.get("category", "") or "",
        descripcion=(m.get("description") or "")[:2500],
    )


def mercados_activos(limite: int = 500) -> list[Mercado]:
    """Trae mercados abiertos, ordenados por volumen."""
    resultado, offset = [], 0
    while len(resultado) < limite:
        r = requests.get(
            f"{config.GAMMA_API}/markets",
            params={"active": "true", "closed": "false", "limit": 100,
                    "offset": offset, "order": "volumeNum", "ascending": "false"},
            timeout=20,
        )
        r.raise_for_status()
        lote = r.json()
        if not lote:
            break
        resultado += [m for m in (_parse(x) for x in lote) if m]
        offset += 100
    return resultado[:limite]


def mercado_por_id(mercado_id: str) -> Optional[Mercado]:
    r = requests.get(f"{config.GAMMA_API}/markets/{mercado_id}", timeout=20)
    if r.status_code != 200:
        return None
    return _parse(r.json())


def filtrar(mercados: list[Mercado]) -> list[Mercado]:
    return [
        m for m in mercados
        if m.volumen >= config.VOLUMEN_MINIMO
        and m.liquidez >= config.LIQUIDEZ_MINIMA
        and config.PRECIO_MIN <= m.precio_si <= config.PRECIO_MAX
    ]
