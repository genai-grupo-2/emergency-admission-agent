"""Corre en Modal, en una A100 de 40 GB, cualquier módulo del repo que necesite el modelo (optimizar el prompt, evaluar,
la matriz) y trae a la máquina local lo que escribió en `corridas/`.

    modal run modal_app.py --comando "optimizacion.optimizar --nombre busqueda-01"
    modal run modal_app.py --comando "evaluacion.evaluar --etiqueta base --prompt catedra"

Requisitos: `modal setup` y un secreto de Modal llamado `huggingface` con `HF_TOKEN` (lectura del modelo base y del
repositorio del grupo). Los pesos se cachean en el volumen `admision-hf-cache`. Las versiones de la imagen están fijas;
cuando el grupo fije las dependencias de inferencia en pyproject.toml/uv.lock (#2, #4), la imagen tiene que usar esas."""

import io
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

import modal

RAIZ = Path(__file__).resolve().parent
VERSIONES = ["torch==2.14.1", "transformers==5.20.2", "accelerate==1.15.0", "pyyaml==6.0.3"]

app = modal.App("emergency-admission-agent")
imagen = (modal.Image.debian_slim(python_version="3.12")
          .pip_install(*VERSIONES)
          .env({"PYTHONUTF8": "1", "HF_HOME": "/cache/hf"})
          .add_local_dir(RAIZ, "/repo", ignore=[".venv", ".git", "corridas", "**/__pycache__"]))
cache = modal.Volume.from_name("admision-hf-cache", create_if_missing=True)


@app.function(image=imagen, gpu="A100-40GB", timeout=24 * 3600, volumes={"/cache": cache},
              secrets=[modal.Secret.from_name("huggingface")])
def ejecutar(argumentos: list[str], entorno: dict) -> bytes:
    resultado = subprocess.run(["python", "-m", *argumentos], cwd="/repo", env={**os.environ, **entorno})
    cache.commit()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        if Path("/repo/corridas").exists():
            tar.add("/repo/corridas", arcname="corridas")
    if resultado.returncode:
        print(f"el comando terminó con código {resultado.returncode}; se traen igual las corridas")
    return buffer.getvalue()


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


@app.local_entrypoint()
def main(comando: str):
    entorno = {"ADMISION_COMMIT": _git("rev-parse", "HEAD"),
               "ADMISION_CAMBIOS_SIN_COMMIT": "1" if _git("status", "--porcelain") else "",
               **{k: v for k, v in os.environ.items() if k.startswith("ADMISION_") and k != "ADMISION_COMMIT"}}
    datos = ejecutar.remote(shlex.split(comando), entorno)
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as tar:
        tar.extractall(RAIZ, filter="data")
    print("corridas copiadas a", RAIZ / "corridas")
