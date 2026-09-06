"""Variables de entorno y configuración mínima del MVP."""

import os

from dotenv import load_dotenv

load_dotenv()

# Proveedor del modelo. "openrouter" es el modelo común del curso (Nemotron
# gratuito); "openai" es un fallback documentado para cuando la cuota diaria
# gratuita de OpenRouter se agota (ver README, sección de limitaciones).
PROVIDER = os.getenv("PROVIDER", "openrouter")

MODEL_ID = os.getenv("MODEL_ID", "nvidia/nemotron-3-ultra-550b-a55b:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dónde vive el servidor FastMCP (api/mcp.py), en modo HTTP stateless.
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8001/")
