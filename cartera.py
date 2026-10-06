"""Cartera simulada: registra operaciones, las liquida y mide resultados."""
from datetime import datetime, timezone

import config
from db import conectar  # noqa: F401  (re-export para bot.py)
from estrategia import Senal


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escalar(db, sql, params=()):
    fila = db.execute(sql, params).fetchone()
    return list(dict(fila).values())[0] if fila else None


def ya_abierta(db, mercado_id: str, modelo: str) -> bool:
    return db.execute(
        "SELECT 1 AS x FROM operaciones WHERE mercado_id=? AND modelo=? AND estado='ABIERTA'",
        (mercado_id, modelo)).fetchone() is not None


def expuesto(db) -> float:
    return float(_escalar(db, "SELECT COALESCE(SUM(monto),0) AS s FROM operaciones WHERE estado='ABIERTA'") or 0)


def banca_actual(db) -> float:
    pnl = _escalar(db, "SELECT COALESCE(SUM(pnl),0) AS s FROM operaciones WHERE estado!='ABIERTA'") or 0
    return config.BANCA_INICIAL + float(pnl)


def registrar(db, s: Senal):
    db.execute(
        """INSERT INTO operaciones (fecha, mercado_id, pregunta, url, modelo, prob_modelo,
           precio_mercado, lado, precio, monto, acciones) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (_ahora(), s.mercado.id, s.mercado.pregunta, s.mercado.url, s.modelo, s.prob_modelo,
         s.mercado.precio_si, s.lado, s.precio, s.monto, round(s.monto / s.precio, 4)))
    db.commit()


def liquidar(db, op_id: int, resultado_si: int):
    op = dict(db.execute("SELECT * FROM operaciones WHERE id=?", (op_id,)).fetchone())
    gano = (op["lado"] == "SI" and resultado_si == 1) or (op["lado"] == "NO" and resultado_si == 0)
    pnl = (op["acciones"] - op["monto"]) if gano else -op["monto"]
    db.execute("UPDATE operaciones SET estado=?, resultado_si=?, pnl=?, fecha_cierre=? WHERE id=?",
               ("GANADA" if gano else "PERDIDA", resultado_si, round(pnl, 2), _ahora(), op_id))
    db.commit()


def guardar_pronostico(db, mercado_id: str, prob_si: float, nota: str = "", pregunta: str = ""):
    db.execute("DELETE FROM pronosticos WHERE mercado_id=?", (mercado_id,))
    db.execute("INSERT INTO pronosticos (mercado_id, prob_si, nota, pregunta, fecha) VALUES (?,?,?,?,?)",
               (mercado_id, prob_si, nota, pregunta, _ahora()))
    db.commit()


def borrar_pronostico(db, mercado_id: str):
    db.execute("DELETE FROM pronosticos WHERE mercado_id=?", (mercado_id,))
    db.commit()


def pronosticos(db) -> dict[str, dict]:
    return {f["mercado_id"]: dict(f) for f in db.execute("SELECT * FROM pronosticos").fetchall()}


def log_ejecucion(db, resumen: str):
    db.execute("INSERT INTO ejecuciones (fecha, resumen) VALUES (?,?)", (_ahora(), resumen))
    db.commit()


def ultima_ejecucion(db):
    f = db.execute("SELECT * FROM ejecuciones ORDER BY id DESC LIMIT 1").fetchone()
    return dict(f) if f else None


def historial_banca(db) -> list[tuple[str, float]]:
    filas = db.execute("SELECT fecha_cierre, pnl FROM operaciones WHERE estado!='ABIERTA' "
                       "ORDER BY fecha_cierre").fetchall()
    banca, serie = config.BANCA_INICIAL, [("inicio", config.BANCA_INICIAL)]
    for f in filas:
        banca += float(f["pnl"])
        serie.append((f["fecha_cierre"][:10], round(banca, 2)))
    return serie


def metricas(db) -> dict:
    """Por modelo: operaciones, aciertos, PnL, ROI y Brier (modelo vs mercado)."""
    filas = db.execute("SELECT * FROM operaciones WHERE estado!='ABIERTA'").fetchall()
    res = {}
    for f in filas:
        r = res.setdefault(f["modelo"], {"n": 0, "ganadas": 0, "pnl": 0.0, "invertido": 0.0,
                                         "brier_modelo": 0.0, "brier_mercado": 0.0})
        r["n"] += 1
        r["ganadas"] += f["estado"] == "GANADA"
        r["pnl"] += f["pnl"]
        r["invertido"] += f["monto"]
        r["brier_modelo"] += (f["prob_modelo"] - f["resultado_si"]) ** 2
        r["brier_mercado"] += (f["precio_mercado"] - f["resultado_si"]) ** 2
    for r in res.values():
        r["roi"] = r["pnl"] / r["invertido"] if r["invertido"] else 0
        r["brier_modelo"] /= r["n"]
        r["brier_mercado"] /= r["n"]
    return res
