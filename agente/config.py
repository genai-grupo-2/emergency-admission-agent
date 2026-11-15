"""Configuración de la entrega, separada en modelo, prompt, buscador y agente.

La configuración vive en `configuracion.json` (en la raíz del repo). Para evaluar otras combinaciones sin tocar el
archivo, cada parte se puede pisar con una variable de entorno:

- `ADMISION_CONFIG`: ruta a otro JSON con la misma forma (por ejemplo, el de una condición de la matriz).
- `ADMISION_PROMPT`: versión del prompt (`prompts/<versión>.txt`) o ruta a un archivo de texto.
- `ADMISION_MODELO_REPO` y `ADMISION_MODELO_REVISION`: el punto de control de Hugging Face.
- `ADMISION_BACKEND`: `hf` (el modelo real) o `falso` (sólo para pruebas de humo sin GPU; no sirve para reportar).
- `ADMISION_DEVICE_MAP`: dónde se cargan los pesos; `cuda` (una GPU, el valor por defecto) o `auto` (repartidos entre
  varias GPU, por ejemplo 2×T4 de 16 GB, donde Gemma 4 E4B en bf16 no entra en una sola).
- `ADMISION_LOTE`: cuántas conversaciones genera el modelo a la vez (bajarlo si la GPU se queda sin memoria).

Lo que se pisa queda en la parte `modelo` de la configuración, y por eso en el `condicion.json` de cada evaluación y
en los metadatos de cada optimización.
"""

import copy
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ / "configuracion.json"


def cargar_config(ruta: Path | None = None, entorno: dict | None = None) -> dict:
    entorno = os.environ if entorno is None else entorno
    ruta = Path(ruta or entorno.get("ADMISION_CONFIG") or RUTA_POR_DEFECTO)
    config = json.loads(ruta.read_text(encoding="utf-8"))
    config = copy.deepcopy(config)
    pisar = {
        "ADMISION_PROMPT": ("prompt", "version"),
        "ADMISION_MODELO_REPO": ("modelo", "repo"),
        "ADMISION_MODELO_REVISION": ("modelo", "revision"),
        "ADMISION_BACKEND": ("modelo", "backend"),
        "ADMISION_DEVICE_MAP": ("modelo", "device_map"),
        "ADMISION_LOTE": ("modelo", "lote"),
    }
    for variable, (parte, clave) in pisar.items():
        if entorno.get(variable):
            valor = entorno[variable]
            config.setdefault(parte, {})[clave] = int(valor) if clave == "lote" else valor
    for parte in ("modelo", "prompt", "buscador", "agente"):
        if parte not in config:
            raise KeyError(f"falta la parte {parte!r} en {ruta}")
    return config
