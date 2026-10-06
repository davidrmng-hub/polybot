# PolyBot — bot de pronósticos en modo simulación

Lee mercados reales de Polymarket, compara tus probabilidades con el precio,
decide cuánto "apostar" con Kelly fraccionado y registra todo con **dinero ficticio**.
No usa cuenta, wallet ni llaves privadas.

## En la nube (Render, gratis)
- **Dashboard**: `https://<tu-servicio>.onrender.com`. El navegador pide usuario
  (cualquiera) y clave (la variable `CLAVE`).
- **Mercados**: busca un mercado, escribe tu probabilidad (%) y guárdala.
- **Ciclo automático**: cron-job.org visita `/ciclo?token=TU_CLAVE` cada 6 horas.
  El bot abre operaciones simuladas y liquida las que ya cerraron.

Variables de entorno en Render:
| Variable | Valor |
|---|---|
| `DATABASE_URL` | connection string de Neon (`postgresql://...`) |
| `CLAVE` | tu contraseña del dashboard |

Plan gratuito: el servicio se duerme tras 15 min sin visitas y tarda ~1 min en
despertar. Es normal.

## En tu computador (opcional)
```
pip install -r requirements.txt
python bot.py escanear      # lista mercados
python bot.py ciclo         # opera + liquida + reporte
python app.py               # dashboard en http://localhost:5000
```
Sin `DATABASE_URL` usa un archivo local `cartera.db`.

## Cómo leer los resultados
- **Brier score**: más bajo = mejor calibrado. Si tu modelo no le gana al mercado
  tras 50+ operaciones, no tiene ventaja real.
- El ROI con pocas operaciones es ruido.

## Modelos (`modelo.py`)
- `manual`: tus pronósticos (dashboard o `mis_pronosticos.csv`).
- `longshot`: línea base que castiga resultados improbables.

Para agregar uno: clase con `nombre` y `estimar(mercado) -> prob | None`,
y súmala en `modelos_disponibles()`.

## Ajustes (`config.py`)
Banca ficticia, umbral de ventaja, fracción de Kelly, límites de exposición y filtros.
