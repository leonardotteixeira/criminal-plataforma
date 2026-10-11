import os
from pathlib import Path

_default_lake = Path(__file__).resolve().parents[2] / "data" / "lake"
LAKE_DIR = Path(os.environ.get("SINALBR_LAKE", _default_lake))
K_MIN = int(os.environ.get("SINALBR_K_MIN", "5"))
CACHE_TTL = int(os.environ.get("SINALBR_CACHE_TTL", "300"))
CORS_ORIGINS = os.environ.get("SINALBR_CORS", "http://localhost:3000").split(",")
# Nome exibido pela API (a marca do frontend fica em web/src/config/brand.ts).
BRAND = os.environ.get("SINALBR_BRAND", "SinalBR")
# Contagens por hexágono são arredondadas para múltiplos deste valor (mitiga a diferenciação
# entre janelas de tempo sobrepostas; ver docs/privacidade.md). 1 desliga o arredondamento.
CELL_ROUND = int(os.environ.get("SINALBR_CELL_ROUND", "5"))
