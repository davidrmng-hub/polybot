"""Configuración del bot. Todo es dinero ficticio (paper trading)."""

GAMMA_API = "https://gamma-api.polymarket.com"

# Banca simulada inicial (USD ficticios)
BANCA_INICIAL = 1000.0

# Ventaja mínima (tu probabilidad - precio) para entrar. 0.05 = 5 puntos.
UMBRAL_VENTAJA = 0.05

# Fracción de Kelly. 0.25 = un cuarto de Kelly (conservador).
FRACCION_KELLY = 0.25

# Máximo por operación como % de la banca
MAX_POR_OPERACION = 0.05

# Máximo expuesto en total como % de la banca
MAX_EXPOSICION_TOTAL = 0.50

# Filtros de mercado
VOLUMEN_MINIMO = 10_000     # USD negociados
LIQUIDEZ_MINIMA = 2_000     # USD en el libro
PRECIO_MIN, PRECIO_MAX = 0.03, 0.97  # evita mercados casi decididos

# Costo asumido por operación (spread + deslizamiento), en puntos de precio
COSTO_EJECUCION = 0.01

# Archivos
DB_PATH = "cartera.db"
PRONOSTICOS_CSV = "mis_pronosticos.csv"
