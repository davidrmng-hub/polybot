"""Dashboard web del bot (para Render). Arranque: gunicorn app:app"""
import os
import threading
import time
from functools import wraps

from flask import Flask, Response, redirect, render_template, request, url_for

import bot
import cartera
import config
import datos

app = Flask(__name__)
CLAVE = os.environ.get("CLAVE", "cambiame")
_lock = threading.Lock()
_cache = {"t": 0, "mercados": []}


# ---------- Acceso ----------
def protegido(f):
    """Pide usuario/clave del navegador. Usuario: cualquiera. Clave: variable CLAVE."""
    @wraps(f)
    def envoltura(*a, **kw):
        auth = request.authorization
        if not auth or auth.password != CLAVE:
            return Response("Acceso restringido", 401,
                            {"WWW-Authenticate": 'Basic realm="PolyBot"'})
        return f(*a, **kw)
    return envoltura


def _mercados():
    if time.time() - _cache["t"] > 600:  # refresca cada 10 min
        _cache["mercados"] = datos.filtrar(datos.mercados_activos())
        _cache["t"] = time.time()
    return _cache["mercados"]


def _ciclo_en_fondo():
    def tarea():
        if not _lock.acquire(blocking=False):
            return  # ya hay un ciclo corriendo
        try:
            db = cartera.conectar()
            print("[ciclo]", bot.ciclo(db).split("\n")[0], flush=True)
            db.close()
        except Exception as e:  # noqa: BLE001
            print("[ciclo] ERROR:", e, flush=True)
            db = cartera.conectar()
            cartera.log_ejecucion(db, f"ERROR: {e}")
            db.close()
        finally:
            _lock.release()
    threading.Thread(target=tarea, daemon=True).start()


# ---------- Rutas ----------
def _recomendaciones(ms):
    """Cruza el último análisis de la IA con el precio ACTUAL de cada mercado."""
    from estrategia import kelly
    db = cartera.conectar()
    analisis = cartera.ultimos_analisis(db)
    db.close()
    por_id = {m.id: m for m in ms}
    recs = []
    for mid, a in analisis.items():
        m = por_id.get(mid)
        if not m:
            continue  # ya cerró o salió de los filtros
        p, precio_si = float(a["prob"]), m.precio_si
        if p >= precio_si:
            lado, precio, prob_lado = "SÍ", precio_si, p
        else:
            lado, precio, prob_lado = "NO", 1 - precio_si, 1 - p
        ventaja = prob_lado - precio
        if ventaja >= 0.08 and a["confianza"] != "baja":
            nivel = "oportunidad"
        elif ventaja >= 0.04:
            nivel = "vigilar"
        else:
            nivel = "justo"
        pct = min(kelly(prob_lado, precio + config.COSTO_EJECUCION) * config.FRACCION_KELLY,
                  config.MAX_POR_OPERACION)
        acciones = 10 / precio if precio else 0
        recs.append(dict(a=a, m=m, lado=lado, precio=precio, prob_lado=prob_lado,
                         ventaja=ventaja, nivel=nivel, pct_banca=pct,
                         ejemplo_acciones=acciones, ejemplo_cobro=acciones,
                         dias=m.dias_para_cierre()))
    recs.sort(key=lambda r: r["ventaja"], reverse=True)
    return recs


@app.get("/")
@protegido
def hoy():
    error = None
    try:
        ms = _mercados()
    except Exception as e:  # noqa: BLE001
        ms, error = [], str(e)
    recs = _recomendaciones(ms)
    db = cartera.conectar()
    met = cartera.metricas(db).get("ia")
    ultima = cartera.ultima_ejecucion(db)
    db.close()
    import ia
    return render_template(
        "hoy.html", pagina="hoy", error=error, ia_activa=ia.disponible(),
        oportunidades=[r for r in recs if r["nivel"] == "oportunidad"],
        vigilar=[r for r in recs if r["nivel"] == "vigilar"],
        justos=[r for r in recs if r["nivel"] == "justo"],
        met=met, ultima=ultima, corriendo=_lock.locked())


@app.get("/guia")
@protegido
def guia():
    return render_template("guia.html", pagina="guia")


@app.get("/simulacion")
@protegido
def inicio():
    db = cartera.conectar()
    ctx = dict(
        banca=cartera.banca_actual(db),
        inicial=config.BANCA_INICIAL,
        expuesto=cartera.expuesto(db),
        metricas=cartera.metricas(db),
        historial=cartera.historial_banca(db),
        abiertas=[dict(f) for f in db.execute(
            "SELECT * FROM operaciones WHERE estado='ABIERTA' ORDER BY fecha DESC").fetchall()],
        cerradas=[dict(f) for f in db.execute(
            "SELECT * FROM operaciones WHERE estado!='ABIERTA' ORDER BY fecha_cierre DESC LIMIT 30").fetchall()],
        ultima=cartera.ultima_ejecucion(db),
        corriendo=_lock.locked(),
        pagina="simulacion",
    )
    db.close()
    return render_template("inicio.html", **ctx)


@app.get("/mercados")
@protegido
def mercados():
    q = (request.args.get("q") or "").lower()
    error = None
    try:
        ms = _mercados()
    except Exception as e:  # noqa: BLE001
        ms, error = [], str(e)
    if q:
        ms = [m for m in ms if q in m.pregunta.lower()]
    db = cartera.conectar()
    prons = cartera.pronosticos(db)
    db.close()
    return render_template("mercados.html", mercados=ms[:150], prons=prons, q=q,
                           error=error, pagina="mercados")


@app.post("/pronostico")
@protegido
def pronostico():
    mid = request.form["mercado_id"]
    db = cartera.conectar()
    if request.form.get("borrar"):
        cartera.borrar_pronostico(db, mid)
    else:
        prob = max(0.01, min(0.99, float(request.form["prob"]) / 100))
        cartera.guardar_pronostico(db, mid, prob, request.form.get("nota", ""),
                                   request.form.get("pregunta", ""))
    db.close()
    return redirect(request.referrer or url_for("mercados"))


@app.post("/ciclo-ahora")
@protegido
def ciclo_ahora():
    _ciclo_en_fondo()
    return redirect(request.referrer or url_for("hoy"))


@app.get("/ciclo")
def ciclo_remoto():
    """Lo visita el despertador (cron-job.org): /ciclo?token=TU_CLAVE"""
    if request.args.get("token") != CLAVE:
        return "no autorizado", 401
    _ciclo_en_fondo()
    return "ciclo iniciado", 202


@app.get("/salud")
def salud():
    """Diagnóstico sin datos sensibles: cuántos mercados se leen y si hay base de datos externa."""
    import db as _db
    try:
        n = len(_mercados())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}, 500
    return {"ok": True, "mercados_filtrados": n, "postgres": _db.ES_PG}


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
