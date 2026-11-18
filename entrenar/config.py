"""Configuración de un entrenamiento: un JSON en `entrenar/configs/`, completado con valores por defecto y validado.

Todo lo que cambia el resultado (datos, prompt, semilla, hiperparámetros) está en el JSON, y el JSON completo queda
en el manifiesto de la corrida y en W&B. `--ensayo` achica la corrida para comprobar memoria y plumbing; no sirve
para reportar."""

import copy
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DEFECTOS = {
    "modelo": {"dtype": "bfloat16", "device_map": "auto", "cuantizacion": "ninguna"},
    "prompt": {"version": "catedra"},
    "datos": {"max_tokens": 8192},
    "lora": {"r": 16, "alpha": 32, "dropout": 0.05},
    "optimizador": {"lr": 2e-4, "weight_decay": 0.0, "warmup_pasos": 10, "acumulacion": 16, "max_norma_grad": 1.0},
    "epocas": 2,
    "semilla": 42,
    "guardar_cada": 34,
    "evaluar_cada": 68,
    "max_horas": 10.5,
    "wandb": {"proyecto": "emergency-admission-agent", "entidad": None},
    "subir_checkpoints_a": None,
}
OBLIGATORIAS = [("nombre",), ("modelo", "repo"), ("modelo", "revision"), ("datos", "train"), ("datos", "validacion"),
                ("lora", "modulos")]
CUANTIZACIONES = ("ninguna", "nf4")


def _mezclar(base: dict, extra: dict) -> dict:
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _mezclar(base[clave], valor)
        else:
            base[clave] = valor
    return base


def completar(crudo: dict) -> dict:
    config = _mezclar(copy.deepcopy(DEFECTOS), copy.deepcopy(crudo))
    for ruta in OBLIGATORIAS:
        valor = config
        for clave in ruta:
            valor = valor.get(clave) if isinstance(valor, dict) else None
        if not valor:
            raise KeyError(f"falta {'.'.join(ruta)} en la configuración")
    nombre = config["nombre"]
    if not nombre.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"nombre inválido {nombre!r}: sólo letras, números, - y _")
    if config["modelo"]["cuantizacion"] not in CUANTIZACIONES:
        raise ValueError(f"cuantizacion debe ser una de {CUANTIZACIONES}")
    if config["modelo"]["dtype"] not in ("bfloat16", "float16"):
        raise ValueError("dtype debe ser bfloat16 o float16")
    for clave in ("epocas", "guardar_cada", "evaluar_cada"):
        if int(config[clave]) < 1:
            raise ValueError(f"{clave} debe ser >= 1")
    if int(config["optimizador"]["acumulacion"]) < 1:
        raise ValueError("optimizador.acumulacion debe ser >= 1")
    return config


def cargar(ruta) -> dict:
    return completar(json.loads(Path(ruta).read_text(encoding="utf-8")))


def para_ensayo(config: dict) -> dict:
    """Misma configuración, pero corta: pocos casos y pocos pasos, para comprobar memoria y el flujo completo."""
    config = copy.deepcopy(config)
    config["nombre"] = f"{config['nombre']}-ensayo"
    config["optimizador"]["acumulacion"] = 2
    config["optimizador"]["warmup_pasos"] = 1
    config["epocas"] = 1
    config["guardar_cada"] = 2
    config["evaluar_cada"] = 2
    config["ensayo"] = {"max_train": 8, "max_validacion": 4, "max_pasos": 4}
    config["subir_checkpoints_a"] = None
    return config
