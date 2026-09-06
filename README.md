# MCP MVP — consultar_medallion

Este directorio contiene el paso siguiente al PoC (`POC_feature_work_advanced.ipynb`):
en vez de migrar todas las tools del notebook, se eligió la única capacidad que ya
tenía evidencia real de funcionar y se expuso como servidor **MCP** (Model Context
Protocol) usando **FastMCP**.

## Por qué esta capacidad y no otra

El PoC registró una sola tool real, `consultar_medallion`, y fue la única evaluada
con evidencia (`RESULTADOS` / `CIERRE_POC` del notebook):

- **camino_feliz → PASS**: citó correctamente los ingresos de Globex usando la tool.
- **fuera_de_alcance → PASS**: el agente *no* la invocó ante una solicitud de escritura.

Las demás secciones del PoC (RAG, SQL genérico, tool de ejemplo, agente de
dashboards) nunca se implementaron ni se probaron — no hay valor demostrado que
migrar, así que deliberadamente no están aquí.

## Archivos

| Archivo | Qué es |
|---|---|
| `mcp_server_consultar_medallion.py` | Servidor FastMCP. Expone **una sola tool**, `consultar_medallion`, sobre una base SQLite sintética en memoria (zonas `plata_ventas` y `oro_kpis_cliente`, mismos datos que el PoC). Solo lectura. |
| `mvp_agente_mcp.py` | El MVP: un agente único (LangChain `create_agent`, mismo modelo del curso vía OpenRouter) cuya única tool viene de ese servidor MCP en vez de ser una función local. |

La tool en sí (contrato, datos, validaciones) es una copia fiel de la celda 2.4 del
PoC: mismo comportamiento ya evaluado, ahora accesible por cualquier cliente MCP
(este MVP, Claude Desktop, Cursor, etc.), no solo desde el notebook.

## Cómo ejecutarlo

Requiere el mismo `.venv` y `OPENROUTER_API_KEY` que usa el PoC (variable de
entorno o archivo `.env` en la raíz del proyecto).

```bash
source .venv/bin/activate
python mvp_agente_mcp.py "¿Cuáles son los ingresos totales de Globex?"
```

`mvp_agente_mcp.py` levanta `mcp_server_consultar_medallion.py` como subproceso
(transporte stdio), así que no hace falta arrancar el servidor por separado. Sin
argumentos, usa la pregunta de ejemplo `"¿Cuáles son los ingresos totales de
Globex?"`.

Para usar el servidor con otro cliente MCP (Claude Desktop, Cursor, etc.) en vez
del MVP, apúntalo directamente a:

```bash
python mcp_server_consultar_medallion.py
```

### Resultado real de la última corrida

```
Pregunta: ¿Cuáles son los ingresos totales de Globex?
Respuesta: Según la tabla oro_kpis_cliente, Globex registra ingresos totales de
19 200,00 (con 2 transacciones contabilizadas).
Tools usadas: ['consultar_medallion']
```

## Arquitectura: qué cambió respecto al PoC y qué no

- **No cambió**: el modelo (`nvidia/nemotron-3-ultra-550b-a55b:free` vía
  OpenRouter), el patrón de agente único, el contrato de la tool, los datos.
- **Sí cambió**: la tool dejó de ser una función `@tool` dentro del mismo proceso
  Python y pasó a vivir en un servidor MCP independiente. El agente la descubre e
  invoca por protocolo, no por import.
- **Se evitó a propósito** forzar salida estructurada (`ToolStrategy`) en el
  agente: en el PoC eso rompió el tool-calling real de este modelo gratuito (el
  modelo imprimía el tool call como texto en vez de ejecutarlo). El MVP se queda
  sin salida estructurada para no reintroducir ese bug; es la primera mejora
  obvia si se necesita JSON validado más adelante (aplicar el mismo workaround de
  dos pasos que usa `ejecutar_agente()` en el notebook).

## Dependencias y una incompatibilidad real que apareció

```bash
pip install fastmcp
```

Se evaluó `langchain-mcp-adapters` para conectar la tool MCP a LangChain, pero:

- `fastmcp` 4.x (el paquete "FastMCP" actual) requiere `mcp>=2`.
- `langchain-mcp-adapters` 0.3.1 todavía depende de `mcp.server.fastmcp`, un
  submódulo que existía en `mcp` 1.x y fue renombrado en `mcp` 2.x.

Ambos requisitos no se pueden satisfacer con la misma versión de `mcp` a la vez.
En vez de fijar un `fastmcp` viejo solo para que un adaptador desactualizado
funcione, se optó por **no usar el adaptador**: `mvp_agente_mcp.py` conecta al
servidor con el cliente async de `fastmcp` y envuelve la tool en ~10 líneas
(`construir_tool_mcp`) como una tool nativa de LangChain. Si en el futuro
`langchain-mcp-adapters` se actualiza para soportar `mcp` 2.x, esa función es el
único lugar que habría que reemplazar.

## Limitaciones (heredadas del PoC, no resueltas aquí)

- Base de datos sintética en memoria; no hay conexión a un warehouse real.
- `consultar_medallion` solo filtra por `client_name`; no soporta rangos de fecha.
- El endpoint gratuito del modelo es lento (~100-300s por llamada) y a veces
  devuelve errores transitorios (502 *"Service temporarily overloaded"*); ver
  `CIERRE_POC` del notebook para el detalle de cuántas corridas del PoC
  necesitaron reintentos.
