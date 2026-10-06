"""Capa de base de datos: Postgres si existe DATABASE_URL (nube), si no SQLite (local)."""
import os
import sqlite3

import config

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ES_PG = DATABASE_URL.startswith("postgres")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS operaciones (
    id {pk},
    fecha TEXT, mercado_id TEXT, pregunta TEXT, url TEXT,
    modelo TEXT, prob_modelo REAL, precio_mercado REAL,
    lado TEXT, precio REAL, monto REAL, acciones REAL,
    estado TEXT DEFAULT 'ABIERTA',
    resultado_si INTEGER,
    pnl REAL DEFAULT 0,
    fecha_cierre TEXT
);
CREATE TABLE IF NOT EXISTS pronosticos (
    mercado_id TEXT PRIMARY KEY,
    prob_si REAL, nota TEXT, pregunta TEXT, fecha TEXT
);
CREATE TABLE IF NOT EXISTS ejecuciones (
    id {pk}, fecha TEXT, resumen TEXT
);
"""


class Conexion:
    """Envoltura mínima: usa '?' como marcador en ambos motores y filas tipo dict."""

    def __init__(self):
        if ES_PG:
            import psycopg
            from psycopg.rows import dict_row
            self.cx = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
            pk = "SERIAL PRIMARY KEY"
        else:
            self.cx = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            self.cx.row_factory = sqlite3.Row
            pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        for stmt in ESQUEMA.format(pk=pk).split(";"):
            if stmt.strip():
                self.cx.execute(stmt)
        self.commit()

    def execute(self, sql: str, params: tuple = ()):
        if ES_PG:
            sql = sql.replace("?", "%s")
        return self.cx.execute(sql, params)

    def commit(self):
        if not ES_PG:
            self.cx.commit()

    def close(self):
        self.cx.close()


def conectar() -> Conexion:
    return Conexion()
