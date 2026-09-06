"""Herramientas del dominio, expuestas como servidor MCP.

Este archivo NO se ejecuta directamente: api/mcp.py lo sirve en local vía
HTTP (modo stateless), y sería el mismo archivo que se montaría en un
despliegue unificado si se intentara la sección 8 (opcional) de la guía.

Capacidad expuesta: consultar_medallion. Es la única tool del PoC
(POC_feature_work_advanced.ipynb) que quedó validada con evidencia real:
- camino_feliz PASS: citó correctamente los ingresos de Globex.
- fuera_de_alcance PASS: el agente no la invocó ante una solicitud de escritura.
No se migran las demás secciones del PoC (RAG, tool de ejemplo, agente de
dashboards): nunca se implementaron ni se probaron.

Los datos son sintéticos (SQLite en memoria) para no requerir credenciales de
un warehouse real; el contrato (nombre, parámetros, validaciones, límites de
solo lectura) es el mismo que ya se evaluó en el PoC.
"""

import sqlite3

from fastmcp import FastMCP


def _crear_base_sintetica() -> sqlite3.Connection:
    conexion = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE plata_ventas (
            id INTEGER PRIMARY KEY,
            client_name TEXT,
            producto TEXT,
            monto REAL,
            fecha TEXT
        )
        """
    )
    cursor.executemany(
        "INSERT INTO plata_ventas VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Acme Corp", "Licencia Pro", 4200.0, "2026-01-15"),
            (2, "Acme Corp", "Soporte", 800.0, "2026-02-03"),
            (3, "Globex", "Licencia Pro", 4200.0, "2026-02-20"),
            (4, "Globex", "Licencia Enterprise", 15000.0, "2026-03-01"),
            (5, "Initech", "Licencia Pro", 4200.0, "2026-03-10"),
        ],
    )

    cursor.execute(
        """
        CREATE TABLE oro_kpis_cliente (
            client_name TEXT PRIMARY KEY,
            ingresos_totales REAL,
            num_transacciones INTEGER
        )
        """
    )
    cursor.executemany(
        "INSERT INTO oro_kpis_cliente VALUES (?, ?, ?)",
        [
            ("Acme Corp", 5000.0, 2),
            ("Globex", 19200.0, 2),
            ("Initech", 4200.0, 1),
        ],
    )

    conexion.commit()
    return conexion


_DB_SINTETICA = _crear_base_sintetica()

TABLAS_AUTORIZADAS = {
    "plata_ventas": "zona plata: transacciones crudas de ventas por cliente",
    "oro_kpis_cliente": "zona oro: indicadores agregados por cliente",
}

mcp = FastMCP(
    name="medallion-datawarehouse",
    instructions=(
        "Consulta de solo lectura sobre las zonas plata y oro de un "
        "datawarehouse medallón. Única capacidad del PoC del curso validada "
        "con evidencia (ver CIERRE_POC del notebook)."
    ),
)


@mcp.tool
def consultar_medallion(tabla: str, cliente: str | None = None) -> dict:
    """Consulta de solo lectura sobre las zonas plata u oro del datawarehouse medallón.

    Úsala cuando el usuario pida cifras, ventas, KPIs o el estado de un cliente
    que puedan responderse desde una de las tablas autorizadas. No la uses
    para crear, modificar o borrar datos: es de solo lectura.

    Args:
        tabla: nombre de tabla autorizada (plata_ventas u oro_kpis_cliente).
        cliente: nombre de cliente para filtrar (client_name); opcional.

    Returns:
        Un dict con "ok", y si tuvo éxito "tabla", "cantidad_registros",
        "registros" (hasta 50 filas) y "advertencia"; si falló, "error".
    """
    if tabla not in TABLAS_AUTORIZADAS:
        return {
            "ok": False,
            "error": f"Tabla no autorizada. Usa una de: {sorted(TABLAS_AUTORIZADAS)}",
        }

    cursor = _DB_SINTETICA.cursor()
    if cliente:
        cursor.execute(f"SELECT * FROM {tabla} WHERE client_name = ? LIMIT 50", (cliente,))
    else:
        cursor.execute(f"SELECT * FROM {tabla} LIMIT 50")

    columnas = [descripcion[0] for descripcion in cursor.description]
    filas = cursor.fetchall()
    registros = [dict(zip(columnas, fila)) for fila in filas]

    return {
        "ok": True,
        "tabla": tabla,
        "cantidad_registros": len(registros),
        "registros": registros,
        "advertencia": "Datos sintéticos de demostración; no representan un warehouse productivo.",
    }
