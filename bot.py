"""Bot de pronósticos para Polymarket — MODO SIMULACIÓN (sin dinero real).

Uso local (terminal):
  python bot.py escanear     # lista mercados filtrados con su precio e ID
  python bot.py operar       # corre los modelos y registra operaciones simuladas
  python bot.py resolver     # liquida operaciones de mercados ya cerrados
  python bot.py reporte      # métricas por modelo + posiciones abiertas
  python bot.py ciclo        # operar + resolver + reporte

En la nube, el dashboard (app.py) llama a ciclo() automáticamente.
"""
import sys

import cartera
import datos
from estrategia import evaluar
from modelo import modelos_disponibles


def operar(db, ms=None) -> list[str]:
    ms = ms if ms is not None else datos.filtrar(datos.mercados_activos())
    lineas = []
    for modelo in modelos_disponibles(db):
        for m in ms:
            p = modelo.estimar(m)
            if p is None or cartera.ya_abierta(db, m.id, modelo.nombre):
                continue
            s = evaluar(m, p, modelo.nombre, cartera.banca_actual(db), cartera.expuesto(db))
            if s:
                cartera.registrar(db, s)
                lineas.append(f"+ [{s.modelo}] {s.lado} @ {s.precio:.2f}  ${s.monto:.2f}  "
                              f"ventaja {s.ventaja:+.1%}  {m.pregunta[:70]}")
    return lineas


def resolver(db) -> int:
    abiertas = db.execute(
        "SELECT DISTINCT mercado_id FROM operaciones WHERE estado='ABIERTA'").fetchall()
    cerradas = 0
    for fila in abiertas:
        m = datos.mercado_por_id(fila["mercado_id"])
        if m and m.cerrado and m.precio_si in (0.0, 1.0):
            ops = db.execute("SELECT id FROM operaciones WHERE mercado_id=? AND estado='ABIERTA'",
                             (fila["mercado_id"],)).fetchall()
            for op in ops:
                cartera.liquidar(db, op["id"], int(m.precio_si))
                cerradas += 1
    return cerradas


def ciclo(db, cliente_ia=None) -> str:
    import ia
    ms = datos.filtrar(datos.mercados_activos())
    analisis = ia.correr(db, ms, cliente_ia)
    n_ia = sum(1 for x in analisis if x.startswith("IA:"))
    nuevas = operar(db, ms)
    cerradas = resolver(db)
    resumen = f"{n_ia} análisis IA, {len(nuevas)} operaciones simuladas nuevas, {cerradas} liquidadas"
    if analisis and analisis[0].startswith("IA desactivada"):
        resumen += " (IA desactivada: falta la llave)"
    cartera.log_ejecucion(db, resumen)
    return "\n".join([resumen] + analisis + nuevas)


# ---------- Comandos de terminal ----------
def _escanear(db):
    ms = datos.filtrar(datos.mercados_activos())
    print(f"{len(ms)} mercados pasan los filtros\n")
    for m in ms[:60]:
        print(f"[{m.id}] {m.precio_si:5.1%}  vol ${m.volumen:>12,.0f}  {m.pregunta[:80]}")


def _reporte(db):
    print(f"Banca simulada: ${cartera.banca_actual(db):,.2f}   "
          f"Expuesto: ${cartera.expuesto(db):,.2f}\n")
    met = cartera.metricas(db)
    if not met:
        print("Aún no hay operaciones liquidadas.")
    for nombre, r in met.items():
        mejor = "mejor" if r["brier_modelo"] < r["brier_mercado"] else "peor"
        print(f"Modelo {nombre}: {r['n']} ops, {r['ganadas']} ganadas, PnL ${r['pnl']:+,.2f}, "
              f"ROI {r['roi']:+.1%}, Brier {r['brier_modelo']:.4f} ({mejor} que el mercado "
              f"{r['brier_mercado']:.4f})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ciclo"
    db = cartera.conectar()
    if cmd == "escanear":
        _escanear(db)
    elif cmd == "operar":
        print("\n".join(operar(db)) or "Sin operaciones nuevas.")
    elif cmd == "resolver":
        print(f"{resolver(db)} operaciones liquidadas.")
    elif cmd == "reporte":
        _reporte(db)
    elif cmd == "ciclo":
        print(ciclo(db))
        _reporte(db)
    else:
        print(__doc__)
