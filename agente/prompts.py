"""Versiones del mensaje de sistema. Cada versión es un archivo `prompts/<versión>.txt` en UTF-8; la huella (sha256 de
los bytes) identifica exactamente qué prompt usó cada corrida y cada conversación de entrenamiento.

El formato del resto de los mensajes es el del agente de ejemplo de la cátedra y el que usa `datos/conversaciones.py`
para entrenar: primer mensaje `Ingresó a la guardia el paciente <id>. Completá su ficha de admisión.`, respuestas del
modelo con `{"herramienta": ..., "argumentos": ...}` y resultados como `Resultado de <herramienta>:\\n<observación>`.
Se mantiene fijo para que las conversaciones de entrenamiento y las de evaluación tengan la misma forma."""

import hashlib
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "prompts"
CARACTERES_POR_TOKEN = 4  # la misma aproximación que usa admision.evaluar_rag


def ruta_prompt(version: str) -> Path:
    ruta = Path(version)
    if ruta.suffix == ".txt" and ruta.exists():
        return ruta
    ruta = CARPETA / f"{version}.txt"
    if not ruta.exists():
        disponibles = ", ".join(sorted(p.stem for p in CARPETA.glob("*.txt")))
        raise FileNotFoundError(f"no existe el prompt {version!r}; hay: {disponibles}")
    return ruta


def cargar_prompt(version: str) -> str:
    # Normaliza CRLF: un checkout en Windows no tiene que cambiar el prompt ni su huella.
    texto = ruta_prompt(version).read_bytes().decode("utf-8").replace("\r\n", "\n")
    if not texto.strip():
        raise ValueError(f"el prompt {version!r} está vacío")
    return texto


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def tokens_aproximados(texto: str) -> int:
    """Tokens a 4 caracteres por token. Para el número del informe se usa el tokenizador del modelo
    (`agente.modelo.contar_tokens`), que necesita descargar el modelo."""
    return round(len(texto) / CARACTERES_POR_TOKEN)
