"""MVP construido alrededor de una sola capacidad: consultar_medallion vía MCP.

Decisión de alcance (instrucción del curso): "No migres todas las tools del
PoC. Elige primero una capacidad crítica que ya haya demostrado valor.
Conviértela en un servidor FastMCP y construye el MVP alrededor de ella."

consultar_medallion es esa capacidad: en el PoC (POC_feature_work_advanced.ipynb)
fue la única tool implementada y evaluada con evidencia real (camino_feliz PASS,
fuera_de_alcance PASS). Este archivo NO reimplementa la tool: se conecta al
servidor mcp_server_consultar_medallion.py y la usa tal cual quedó validada.

Arquitectura: la misma del PoC (agente único, LangChain create_agent, modelo
común del curso vía OpenRouter). El único cambio es de dónde viene la tool:
antes era una función @tool local, ahora es un proceso MCP separado — el
mismo patrón que usaría un cliente externo (Claude Desktop, Cursor, otro
servicio) para reutilizar esta capacidad sin duplicar código.

Uso:
    python mvp_agente_mcp.py
    python mvp_agente_mcp.py "¿Cuáles son los ingresos totales de Acme Corp?"

El modelo por defecto es el común del curso (OpenRouter + nemotron gratuito).
Si su cuota diaria gratuita ya se agotó (429 free-models-per-day), se puede
usar OpenAI directamente con --provider openai (requiere OPENAI_API_KEY en
.env). Esto es solo para probar que la tool MCP funciona igual con otro
proveedor; no reemplaza el modelo común exigido por el curso.

    python mvp_agente_mcp.py --provider openai "¿Cuáles son los ingresos totales de Globex?"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

SERVER_SCRIPT = Path(__file__).parent / "mcp_server_consultar_medallion.py"
MODEL_ID_OPENROUTER = "nvidia/nemotron-3-ultra-550b-a55b:free"
MODEL_ID_OPENAI = "gpt-4o-mini"

# Recorte del Pasaporte del PoC: mismo rol y mismo límite de alcance, sin las
# secciones que no aplican a este MVP de una sola capacidad.
SYSTEM_PROMPT = """
Rol y responsabilidades:
agente: responde preguntas de negocio consultando el datawarehouse medallón.

Objetivo del MVP:
Demostrar que la única capacidad validada del PoC (consultar_medallion) sigue
funcionando igual cuando se expone como servidor MCP en vez de tool local.

Contrato de salida:
Respuesta en lenguaje natural que cite las cifras devueltas por la tool.

Reglas:
- Acceso de solo lectura: nunca afirmes haber escrito, borrado o modificado datos.
- Ante ambigüedad o datos insuficientes, dilo explícitamente en vez de inventar una cifra.
- Usa consultar_medallion solo con tabla in {plata_ventas, oro_kpis_cliente}.
""".strip()


def construir_tool_mcp(client: Client):
    """Envuelve la tool remota del servidor MCP como una tool de LangChain.

    El contrato (nombre, parámetros, docstring) es idéntico al de la tool
    local del PoC para que el agente decida igual cuándo usarla.
    """

    @tool
    async def consultar_medallion(tabla: str, cliente: str | None = None) -> list[dict]:
        """Consulta de solo lectura sobre las zonas plata u oro del datawarehouse medallón.

        Recibe el nombre de una tabla autorizada (plata_ventas u oro_kpis_cliente) y,
        opcionalmente, un client_name para filtrar. Devuelve hasta 50 filas.
        Úsala cuando el usuario pida cifras, ventas, KPIs o el estado de un cliente.
        No permite escritura ni tablas fuera de la lista autorizada.
        """
        resultado = await client.call_tool(
            "consultar_medallion", {"tabla": tabla, "cliente": cliente}
        )
        return resultado.data

    return consultar_medallion


def construir_llm(provider: str) -> ChatOpenAI:
    if provider == "openai":
        return ChatOpenAI(
            model=MODEL_ID_OPENAI,
            api_key=os.environ["OPENAI_API_KEY"],
            temperature=0,
            max_tokens=4096,
            timeout=60,
            max_retries=2,
        )
    return ChatOpenAI(
        model=MODEL_ID_OPENROUTER,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=4096,
        timeout=180,
        max_retries=3,
        default_headers={
            "HTTP-Referer": "https://colab.research.google.com/",
            "X-Title": "AI Project MVP MCP",
        },
    )


async def ejecutar_mvp(pregunta: str, provider: str = "openrouter") -> dict:
    transport = StdioTransport(command=sys.executable, args=[str(SERVER_SCRIPT)])
    client = Client(transport)

    async with client:
        tool_mcp = construir_tool_mcp(client)
        llm = construir_llm(provider)

        # Nota (hallazgo del PoC): forzar salida estructurada con
        # response_format=ToolStrategy(...) junto a una tool real rompe el
        # tool-calling de este modelo gratuito. El MVP se queda deliberadamente
        # sin salida estructurada para no reintroducir ese bug.
        agent = create_agent(model=llm, tools=[tool_mcp], system_prompt=SYSTEM_PROMPT)

        estado = await agent.ainvoke(
            {"messages": [{"role": "user", "content": pregunta}]}
        )

        tools_usadas = [
            llamada.get("name", "tool_sin_nombre")
            for mensaje in estado.get("messages", [])
            for llamada in (getattr(mensaje, "tool_calls", None) or [])
        ]
        respuesta = estado["messages"][-1].content

        return {"respuesta": respuesta, "tools_usadas": tools_usadas}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["openrouter", "openai"],
        default="openrouter",
        help="openrouter (modelo común del curso, por defecto) u openai (fallback de prueba)",
    )
    parser.add_argument("pregunta", nargs="*", default=[])
    args = parser.parse_args()

    pregunta = " ".join(args.pregunta) or "¿Cuáles son los ingresos totales de Globex?"
    print(f"Proveedor: {args.provider}")
    print(f"Pregunta: {pregunta}\n")
    resultado = asyncio.run(ejecutar_mvp(pregunta, provider=args.provider))
    print("Respuesta:", resultado["respuesta"])
    print("Tools usadas:", resultado["tools_usadas"])
