"""Verifica, desde un entorno limpio y sin reentrenar, que el checkpoint PUBLICADO se carga como lo carga la cátedra.

    export HF_TOKEN=...   # de lectura alcanza
    python -m entrenar.verificar_carga --repo <usuario-o-org>/<repo> --revision <hash>

Hace lo mismo que la cátedra: `entrega.construir_agente()` con `ADMISION_MODELO_REPO` y `ADMISION_MODELO_REVISION`, y
comprueba que
1. el modelo se carga UNA sola vez (se cuentan las llamadas a `from_pretrained` de los pesos);
2. genera una respuesta que es JSON de herramienta válido para el primer paso de un caso (leer_triage);
3. cuánta VRAM usa y en cuánto tiempo carga (para Pía), y en qué GPU corrió.

El resultado queda en `corridas/entrenamiento/verificacion-<revision>.json`. Para evaluar de punta a punta, el comando
de Juan: `ADMISION_MODELO_REPO=... ADMISION_MODELO_REVISION=... python -m evaluacion.evaluar --etiqueta <x>`."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def principal(argv=None) -> int:
    p = argparse.ArgumentParser(description="Comprueba la carga del checkpoint publicado.")
    p.add_argument("--repo", required=True)
    p.add_argument("--revision", required=True, help="hash del commit publicado")
    args = p.parse_args(argv)
    if len(args.revision) < 40:
        p.error("--revision tiene que ser el hash completo del commit, no una rama")
    os.environ["ADMISION_MODELO_REPO"] = args.repo
    os.environ["ADMISION_MODELO_REVISION"] = args.revision
    os.environ["ADMISION_BACKEND"] = "hf"

    import torch
    import transformers

    cargas = []
    originales = {}
    for clase in ("AutoModelForCausalLM", "AutoModelForImageTextToText"):
        original = getattr(transformers, clase).from_pretrained
        originales[clase] = original

        def contado(*a, _o=original, _c=clase, **k):
            cargas.append(_c)
            return _o(*a, **k)

        getattr(transformers, clase).from_pretrained = contado

    from entrega import construir_agente

    t0 = time.monotonic()
    agente = construir_agente()
    segundos = time.monotonic() - t0
    modelo = agente.modelo_lote
    conversacion = [{"role": "system", "content": agente.sistema},
                    {"role": "user", "content": "Ingresó a la guardia el paciente P-0000. Completá su ficha de admisión."}]
    respuesta = modelo([conversacion])[0]
    try:
        herramienta = json.loads(respuesta).get("herramienta")
    except json.JSONDecodeError:
        herramienta = None
    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    resultado = {
        "repo": args.repo, "revision": args.revision, "verificado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cargas_del_modelo": len(cargas), "una_sola_carga": len(cargas) == 1,
        "primera_herramienta": herramienta, "respuesta_es_json_de_herramienta": herramienta == "leer_triage",
        "segundos_de_carga": round(segundos, 1), "gpus": gpus,
        "vram_pico_gib": [round(torch.cuda.max_memory_allocated(i) / 2**30, 2) for i in range(len(gpus))],
        "respuesta": respuesta[:300],
    }
    destino = RAIZ / "corridas" / "entrenamiento" / f"verificacion-{args.revision[:12]}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["una_sola_carga"] and resultado["respuesta_es_json_de_herramienta"] else 1


if __name__ == "__main__":
    sys.exit(principal())
