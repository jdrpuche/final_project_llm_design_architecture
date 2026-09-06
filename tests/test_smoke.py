"""Prueba de humo: el agente responde una pregunta real usando la tool MCP.

Ejecuta con el servidor MCP corriendo en otra terminal (uvicorn api.mcp:app
--port 8001): python tests/test_smoke.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import responder


async def main():
    respuesta = await responder("¿Cuáles son los ingresos totales de Globex?")
    assert respuesta
    assert "19" in respuesta.replace(",", "").replace(".", "")
    print("PASS —", respuesta)


if __name__ == "__main__":
    asyncio.run(main())
