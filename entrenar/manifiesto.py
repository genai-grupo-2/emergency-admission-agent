"""Manifiesto de una corrida: `corridas/entrenamiento/<nombre>/manifiesto.json`.

Es lo que hace auditable cada entrenamiento (mission.md, Auditabilidad): archivos exactos de datos con su sha256, el
prompt, la configuración completa, la semilla, el commit, el entorno, la corrida de W&B y cada punto de control con su
pérdida y su revisión en Hugging Face. Se reescribe entero y de forma atómica en cada cambio, así queda consistente
aunque la corrida se corte. Las corridas que fallan o se pausan también dejan su manifiesto, con el motivo."""

import json
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def contexto_git() -> dict:
    """`correr_kaggle.py` anota el commit antes de correr; si no, se pregunta a git."""
    commit = os.environ.get("ADMISION_COMMIT") or _git("rev-parse", "HEAD")
    if "ADMISION_CAMBIOS_SIN_COMMIT" in os.environ:
        sucio = bool(os.environ["ADMISION_CAMBIOS_SIN_COMMIT"])
    else:
        sucio = bool(_git("status", "--porcelain"))
    return {"commit": commit, "rama": _git("rev-parse", "--abbrev-ref", "HEAD"), "cambios_sin_commit": sucio}


def versiones() -> dict:
    resultado = {"python": sys.version.split()[0], "so": platform.platform()}
    for paquete in ("torch", "transformers", "peft", "accelerate", "wandb", "huggingface_hub", "bitsandbytes"):
        try:
            resultado[paquete] = __import__(paquete).__version__
        except Exception:  # no instalado, o no importa en esta máquina
            resultado[paquete] = None
    return resultado


class Manifiesto:
    def __init__(self, ruta: Path, inicial: dict):
        self.ruta = Path(ruta)
        self.datos = dict(inicial)
        self.datos.setdefault("checkpoints", [])
        self.datos.setdefault("sesiones", [])
        self.guardar()

    @classmethod
    def retomar(cls, ruta: Path) -> "Manifiesto":
        m = cls.__new__(cls)
        m.ruta = Path(ruta)
        m.datos = json.loads(m.ruta.read_text(encoding="utf-8"))
        return m

    def guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".json.tmp")
        temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporal, self.ruta)

    def actualizar(self, **campos):
        self.datos.update(campos)
        self.guardar()

    def agregar_checkpoint(self, **entrada):
        self.datos["checkpoints"] = [c for c in self.datos["checkpoints"] if c["paso"] != entrada["paso"]]
        self.datos["checkpoints"].append(entrada)
        self.datos["checkpoints"].sort(key=lambda c: c["paso"])
        self.guardar()

    def actualizar_checkpoint(self, paso: int, **campos):
        for c in self.datos["checkpoints"]:
            if c["paso"] == paso:
                c.update(campos)
                return self.guardar()
        raise KeyError(f"el manifiesto no tiene el checkpoint del paso {paso}")

    def terminar(self, estado: str, **campos):
        self.datos.update(estado=estado, fin=ahora(), **campos)
        self.guardar()

    def fallar(self, error: BaseException):
        self.terminar("interrumpida" if isinstance(error, KeyboardInterrupt) else "fallida",
                      error={"tipo": type(error).__name__, "mensaje": str(error)[:2000],
                             "traza": "".join(traceback.format_exception(error))[-4000:]})
