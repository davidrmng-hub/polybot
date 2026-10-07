"""Analista con IA: busca noticias de cada mercado y estima la probabilidad de forma independiente.

A propósito NO le mostramos el precio del mercado a la IA: si lo viera, tendería a
copiarlo y nunca encontraría diferencias. Primero estima sola y después comparamos.
"""
import json
import os
import re
from datetime import datetime, timezone

import cartera
import datos

MODELO_IA = os.environ.get("MODELO_IA", "claude-haiku-4-5-20251001")
ANALISIS_POR_CICLO = int(os.environ.get("ANALISIS_POR_CICLO", "3"))
HORAS_REANALISIS = int(os.environ.get("HORAS_REANALISIS", "48"))
BUSQUEDAS_POR_ANALISIS = 3

# Prioriza mercados que se resuelven pronto (aprendemos rápido si la IA acierta)
DIAS_MIN, DIAS_MAX = 2, 60
PRECIO_MIN, PRECIO_MAX = 0.08, 0.92

PROMPT = """Eres un analista de pronósticos riguroso y calibrado (estilo superforecaster).
Fecha de hoy: {hoy}.

Pregunta del mercado de predicción:
"{pregunta}"

Reglas de resolución:
{descripcion}

Fecha límite de resolución: {fecha_fin}

Tarea:
1. Busca en la web las noticias y datos MÁS RECIENTES que afecten esta pregunta.
2. Parte de una tasa base (qué tan seguido pasan cosas así) y ajústala con la evidencia.
3. Estima la probabilidad de que se resuelva "Sí". Evita extremos (<3% o >97%) salvo que sea casi seguro.
4. Sé honesto con la confianza: "baja" si la información es escasa, contradictoria o muy incierta.

Responde SOLO con un JSON válido (sin texto antes ni después), en español:
{{"probabilidad": 0.00,
  "confianza": "baja|media|alta",
  "resumen": "2-3 frases explicando tu estimación en lenguaje sencillo",
  "a_favor": ["razón 1", "razón 2"],
  "en_contra": ["razón 1", "razón 2"],
  "que_vigilar": "qué noticia o evento cambiaría la estimación"}}"""


def disponible() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _extraer_json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("La IA no devolvió JSON")
    d = json.loads(m.group(0))
    p = float(d["probabilidad"])
    if p > 1:  # por si responde en porcentaje
        p /= 100
    d["probabilidad"] = min(max(p, 0.01), 0.99)
    if d.get("confianza") not in ("baja", "media", "alta"):
        d["confianza"] = "baja"
    return d


def analizar(m: datos.Mercado, cliente=None) -> dict:
    if cliente is None:
        import anthropic
        cliente = anthropic.Anthropic()
    prompt = PROMPT.format(
        hoy=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        pregunta=m.pregunta,
        descripcion=m.descripcion or "(sin descripción)",
        fecha_fin=m.fecha_fin[:10] or "no indicada",
    )
    resp = cliente.messages.create(
        model=MODELO_IA,
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search",
                "max_uses": BUSQUEDAS_POR_ANALISIS}],
        messages=[{"role": "user", "content": prompt}],
    )
    texto, fuentes = "", []
    for bloque in resp.content:
        if getattr(bloque, "type", "") == "text":
            texto += bloque.text
            for c in getattr(bloque, "citations", None) or []:
                url = getattr(c, "url", None)
                if url and url not in [f["url"] for f in fuentes]:
                    fuentes.append({"url": url, "titulo": getattr(c, "title", "") or url})
    d = _extraer_json(texto)
    d["fuentes"] = fuentes[:5]
    return d


def candidatos(mercados: list[datos.Mercado], ya_analizados: dict) -> list[datos.Mercado]:
    ahora = datetime.now(timezone.utc)
    res = []
    for m in mercados:
        dias = m.dias_para_cierre()
        if dias is None or not (DIAS_MIN <= dias <= DIAS_MAX):
            continue
        if not (PRECIO_MIN <= m.precio_si <= PRECIO_MAX):
            continue
        previo = ya_analizados.get(m.id)
        if previo:
            horas = (ahora - datetime.fromisoformat(previo["fecha"])).total_seconds() / 3600
            if horas < HORAS_REANALISIS:
                continue
        res.append(m)
    # Más volumen primero = mercados más relevantes y con mejor liquidez
    return sorted(res, key=lambda x: x.volumen, reverse=True)


def correr(db, mercados: list[datos.Mercado], cliente=None) -> list[str]:
    if not disponible() and cliente is None:
        return ["IA desactivada: falta ANTHROPIC_API_KEY"]
    lineas = []
    for m in candidatos(mercados, cartera.ultimos_analisis(db))[:ANALISIS_POR_CICLO]:
        try:
            d = analizar(m, cliente)
            cartera.guardar_analisis(db, m, d, MODELO_IA)
            lineas.append(f"IA: {d['probabilidad']:.0%} ({d['confianza']}) vs mercado "
                          f"{m.precio_si:.0%} — {m.pregunta[:60]}")
        except Exception as e:  # noqa: BLE001
            lineas.append(f"IA error en {m.id}: {e}")
    return lineas
