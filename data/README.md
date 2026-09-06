# Datos de demostración

Este MVP no usa un CSV en esta carpeta: la capacidad validada en el PoC
(`consultar_medallion`) genera sus propios datos sintéticos en memoria
(SQLite), definidos directamente en `mcp_server.py`, para no depender de un
archivo externo ni de credenciales de un warehouse real.

Si tu equipo migra otra capacidad que sí lea un archivo, esta es la carpeta
donde debería vivir (datos anonimizados o sintéticos únicamente).
