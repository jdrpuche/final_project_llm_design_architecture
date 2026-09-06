# MVP — Agente de datawarehouse medallón con FastMCP

Este proyecto es la transición del PoC (`POC_feature_work_advanced.ipynb`) a un
MVP siguiendo la guía de curso *"Del Proof of Concept al MVP"*. Sigue su regla
central: **no se migran todas las tools del PoC** — se eligió la única
capacidad que ya tenía evidencia real de funcionar, se convirtió en un
servidor FastMCP, y el MVP entero se construyó alrededor de ella.

## Por qué esta capacidad y no otra

El PoC registró una sola tool real, `consultar_medallion`, y fue la única
evaluada con evidencia (`RESULTADOS` / `CIERRE_POC` del notebook):

- **camino_feliz → PASS**: citó correctamente los ingresos de Globex.
- **fuera_de_alcance → PASS**: el agente *no* la invocó ante una solicitud de escritura.

Las demás secciones del PoC (RAG, tool de ejemplo, agente de dashboards) nunca
se implementaron ni se probaron — no hay valor demostrado que migrar.

## Estructura del proyecto

```
mcp_server.py       # Tool del dominio (FastMCP) — no se ejecuta directamente
agent.py            # Agente LangChain + descubrimiento de tools vía MCP (HTTP)
config.py           # Variables de entorno
prompts.py          # SYSTEM_PROMPT (traducido de la Ficha 1 / PoC)
index.html          # Interfaz del chat
static/
├── app.js
└── style.css
api/
├── __init__.py
├── mcp.py          # Sirve mcp_server.py como servicio HTTP independiente
└── chat.py         # Backend FastAPI: sirve la UI y expone /api/chat
requirements.txt
.env.example
data/
└── README.md       # Por qué no hay CSV aquí (los datos son sintéticos en memoria)
tests/
└── test_smoke.py
```

Sigue la convención `api/` para mantener el proyecto listo para un despliegue
tipo Vercel (sección 8 de la guía, opcional) sin reorganizar nada más tarde.
Ese despliegue **no se intentó** — no es un requisito de entrega.

## Cómo ejecutarlo

Requiere el mismo `.venv` que el PoC.

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y completa OPENROUTER_API_KEY (o OPENAI_API_KEY, ver abajo)
```

**Terminal 1 — servidor MCP (tools del dominio):**

```bash
uvicorn api.mcp:app --reload --port 8001
```

**Terminal 2 — backend + interfaz:**

```bash
uvicorn api.chat:app --reload --port 8000
```

Abre `http://127.0.0.1:8000` y pregunta, por ejemplo, *"¿Cuáles son los
ingresos totales de Globex?"*.

### Elegir proveedor de modelo

`PROVIDER` en `.env` controla qué modelo usa `agent.py`:

- `PROVIDER=openrouter` (por defecto): el modelo común del curso
  (`nvidia/nemotron-3-ultra-550b-a55b:free`). Requiere `OPENROUTER_API_KEY`.
- `PROVIDER=openai`: fallback de prueba (`gpt-4o-mini`). Requiere
  `OPENAI_API_KEY`. Útil porque el tier gratuito de OpenRouter tiene un límite
  de 50 requests/día que se agota rápido iterando (ver Limitaciones).

## Evidencia real de las pruebas

Los 5 casos de la matriz de aceptación de la guía (sección 7), probados contra
el backend real (`POST /api/chat`) con `PROVIDER=openai`:

| Caso | Pregunta | Resultado |
|---|---|---|
| Camino feliz | ingresos totales de Globex | `ok: true`, cita 19,200 correctamente vía `consultar_medallion` |
| Fuera de alcance | "elimina permanentemente..." | `ok: true`, rechaza explícitamente, sin invocar la tool |
| Incertidumbre | "¿cuánto vendimos el año pasado?" | `ok: true`, aclara que no tiene datos de ese período en vez de inventar una cifra |
| Tool inválida | pide una tabla no autorizada | `ok: true`, la tool devuelve `{"ok": false, "error": ...}` y el agente lo explica sin romperse |
| MCP no disponible | servidor MCP apagado a propósito | `ok: false` con mensaje claro (`Client failed to connect`); **el backend no se cayó** |

## Qué cambió respecto al MVP anterior (versión de un solo archivo)

Una iteración previa de este MVP vivía en dos archivos sueltos
(`mcp_server_consultar_medallion.py` + `mvp_agente_mcp.py`, transporte stdio,
sin backend web). Al recibir la guía completa del curso, se reestructuró para
seguir su arquitectura: FastAPI + frontend estático + servidor MCP servido por
HTTP en modo `stateless_http`, `config.py`/`prompts.py` separados, y pruebas
en `tests/`. La tool en sí (contrato, datos, validaciones) no cambió: sigue
siendo la misma que se evaluó en el PoC.

## Desviación importante de la guía: `langchain-mcp-adapters`

La guía recomienda `langchain-mcp-adapters>=0.3.0` con `MultiServerMCPClient`
para que el agente descubra tools por MCP. Al construir este MVP (verificado
en esta misma sesión), **esa combinación no es instalable hoy**:

- `fastmcp` (cualquier versión probada: 4.0.3, 2.14.7, 2.3.0) requiere
  `mcp>=2`, el paquete oficial del SDK.
- `langchain-mcp-adapters` 0.3.1/0.3.2 todavía importa
  `mcp.server.fastmcp`, un submódulo que solo existe en `mcp<2` y fue
  renombrado a `mcp.server.mcpserver` en `mcp` 2.x.

Es decir: no hay ninguna versión de `fastmcp` instalable ahora mismo que
funcione con `mcp<2`, y `langchain-mcp-adapters` todavía no soporta `mcp>=2`.
Esto es una ruptura muy reciente en el ecosistema (posterior a la referencia
de "agosto de 2026" de la guía) — exactamente el tipo de cosa que la propia
guía advierte en su sección de referencias técnicas ("las interfaces cambian
con rapidez").

**Solución aplicada:** `agent.py` no usa `langchain-mcp-adapters`. En su lugar:

- Se conecta al servidor MCP con el cliente async nativo de `fastmcp`
  (`fastmcp.Client(MCP_URL)`).
- Descubre las tools dinámicamente con `client.list_tools()` — **no** importa
  `consultar_medallion` directamente, igual que exige la guía.
- Envuelve cada tool descubierta como una `StructuredTool` de LangChain,
  usando el `input_schema` (JSON Schema) que ya expone el servidor MCP como
  `args_schema` (LangChain lo acepta directamente, sin convertirlo a Pydantic).
- Replica a mano el comportamiento que la guía pide de
  `langchain-mcp-adapters>=0.3.0`: si `call_tool` falla, la tool devuelve
  `{"ok": False, "error": ...}` en vez de dejar que la excepción rompa la
  conversación del agente o el backend (ver `_invocar_tool_mcp` en `agent.py`).

Si en el futuro `langchain-mcp-adapters` soporta `mcp>=2`, ese es el único
archivo (`agent.py`) que habría que simplificar.

## Limitaciones (heredadas del PoC)

- Base de datos sintética en memoria (`mcp_server.py`); no hay conexión a un
  warehouse real.
- `consultar_medallion` solo filtra por `client_name`; no soporta rangos de fecha.
- El endpoint gratuito de OpenRouter es lento (~100-300s por llamada) y a
  veces devuelve errores transitorios (502 *"Service temporarily
  overloaded"*), además de un límite duro de 50 requests/día. `PROVIDER=openai`
  existe como fallback documentado para no quedar bloqueado durante pruebas.
- No hay memoria de conversación entre turnos: cada pregunta se procesa de
  forma independiente (modo stateless, igual que el servidor MCP).

## Despliegue en Vercel

No se intentó — es un paso opcional (sección 8 de la guía), no un requisito
de entrega, y el MVP local ya cumple el entregable mínimo.

## Registro de decisiones (sección 11 de la guía)

- **Ruta del PoC**: Ruta C (agente único con tools).
- **Qué se reutilizó del PoC**: la tool `consultar_medallion` completa (datos,
  contrato, validación de solo lectura) y el patrón de agente único.
- **Qué se dejó fuera del MVP**: todo lo que el PoC no llegó a implementar o
  probar (RAG, tool de ejemplo, agente de dashboards, salida estructurada
  forzada — esta última se abandonó también en el PoC por romper el
  tool-calling del modelo gratuito, ver notebook).
