"""Servidor FastMCP para la única capacidad del PoC que ya demostró valor.

Decisión de alcance: el PoC (POC_feature_work_advanced.ipynb) registró una sola
tool real, consultar_medallion, y fue la única evaluada con evidencia:
- camino_feliz PASS: citó correctamente los ingresos de Globex vía esta tool.
- fuera_de_alcance PASS: el agente NO la invocó ante una solicitud de escritura.
No se migran las demás secciones del PoC (RAG, SQL genérico, tool de ejemplo):
nunca se implementaron ni se probaron, así que no hay valor demostrado que
migrar. Este servidor expone deliberadamente una sola tool.

La implementación de la tool (base sintética, tablas autorizadas, validación
de solo lectura) es una copia fiel de la celda 2.4 del PoC: mismo contrato,
mismos datos, para que el resultado ya evaluado siga siendo válido aquí.

Ejecución como servidor MCP real (stdio, para Claude Desktop, Cursor, el
MVP de este mismo proyecto, etc.):

    python mcp_server_consultar_medallion.py
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


@mcp.tool()
def consultar_medallion(tabla: str, cliente: str | None = None) -> list[dict]:
    """Consulta de solo lectura sobre las zonas plata u oro del datawarehouse medallón.

    Recibe el nombre de una tabla autorizada (plata_ventas u oro_kpis_cliente) y,
    opcionalmente, un client_name para filtrar. Devuelve hasta 50 filas.
    Úsala cuando el usuario pida cifras, ventas, KPIs o el estado de un cliente.
    No permite escritura ni tablas fuera de la lista autorizada.
    """
    if tabla not in TABLAS_AUTORIZADAS:
        return [
            {
                "error": f"Tabla no autorizada. Usa una de: {sorted(TABLAS_AUTORIZADAS)}",
            }
        ]

    cursor = _DB_SINTETICA.cursor()
    if cliente:
        cursor.execute(f"SELECT * FROM {tabla} WHERE client_name = ? LIMIT 50", (cliente,))
    else:
        cursor.execute(f"SELECT * FROM {tabla} LIMIT 50")

    columnas = [descripcion[0] for descripcion in cursor.description]
    filas = cursor.fetchall()
    return [dict(zip(columnas, fila)) for fila in filas]


if __name__ == "__main__":
    mcp.run()
