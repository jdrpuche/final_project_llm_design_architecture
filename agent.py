"""Agente LangChain que descubre tools vía MCP.

No importa mcp_server.py directamente: la única forma de llegar a una tool es
a través del protocolo MCP (HTTP, hacia MCP_URL) — ese desacople es el punto.

Nota sobre langchain-mcp-adapters: la guía recomienda MultiServerMCPClient de
langchain-mcp-adapters>=0.3.0. Al construir este MVP, ese paquete resultó
incompatible con toda versión de fastmcp actualmente instalable (fastmcp
requiere mcp>=2; langchain-mcp-adapters todavía depende de mcp.server.fastmcp,
un submódulo que solo existe en mcp<2). Mientras esa incompatibilidad no se
resuelva río arriba, este archivo usa el cliente async de fastmcp directamente
y replica a mano el comportamiento que la guía pide de ese paquete: un fallo
al invocar una tool vuelve como {"ok": False, "error": ...}, nunca como una
excepción que tumbe el backend (ver _invocar_tool_mcp).
"""

from fastmcp import Client
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from config import (
    MCP_URL,
    MODEL_ID,
    OPENAI_API_KEY,
    OPENAI_MODEL_ID,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    PROVIDER,
)
from prompts import SYSTEM_PROMPT


def construir_llm(provider: str = PROVIDER) -> ChatOpenAI:
    if provider == "openai":
        return ChatOpenAI(
            model=OPENAI_MODEL_ID,
            api_key=OPENAI_API_KEY,
            temperature=0,
            max_tokens=4096,
            timeout=60,
            max_retries=2,
        )
    # Mismo bloque ya probado en el PoC (OpenRouter + Nemotron gratuito).
    return ChatOpenAI(
        model=MODEL_ID,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0,
        max_tokens=4096,
        timeout=180,
        max_retries=3,
        default_headers={
            "HTTP-Referer": "https://colab.research.google.com/",
            "X-Title": "AI Project MVP MCP",
        },
    )


def _tool_lc_desde_mcp(client: Client, tool_mcp) -> StructuredTool:
    """Envuelve una tool descubierta por MCP como una tool nativa de LangChain.

    El nombre, descripción y esquema de parámetros vienen del servidor MCP,
    no de este archivo: si mcp_server.py agrega o cambia una tool, agent.py
    no necesita tocarse.
    """

    async def _invocar_tool_mcp(**kwargs):
        try:
            resultado = await client.call_tool(tool_mcp.name, kwargs)
            return resultado.data
        except Exception as exc:
            # Equivalente al manejo de errores de langchain-mcp-adapters>=0.3.0:
            # la tool "falla" con un mensaje, no con una excepción que
            # interrumpa la conversación del agente ni el backend.
            return {"ok": False, "error": f"No fue posible invocar {tool_mcp.name}: {exc}"}

    return StructuredTool.from_function(
        coroutine=_invocar_tool_mcp,
        name=tool_mcp.name,
        description=tool_mcp.description or "",
        args_schema=tool_mcp.input_schema,
    )


async def _descubrir_tools(client: Client) -> list[StructuredTool]:
    tools_mcp = await client.list_tools()
    return [_tool_lc_desde_mcp(client, tool_mcp) for tool_mcp in tools_mcp]


async def responder(pregunta: str, provider: str = PROVIDER) -> str:
    """Punto de entrada del backend: recibe una pregunta, devuelve la respuesta.

    Abre una conexión MCP nueva por invocación (modo stateless, igual que el
    servidor): no asume que dos llamadas comparten sesión ni memoria.
    """
    llm = construir_llm(provider)

    async with Client(MCP_URL) as client:
        tools = await _descubrir_tools(client)
        agente = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
        estado = await agente.ainvoke(
            {"messages": [{"role": "user", "content": pregunta}]}
        )
        return estado["messages"][-1].content
