"""Corre en un notebook de Kaggle con 2×T4 (sin tarjeta) cualquier módulo del repo que necesite el modelo, igual que
`modal_app.py` en Modal: anota el commit antes de correr, reparte Gemma entre las dos GPU y deja el entorno y un zip
de `corridas/` en /kaggle/working para bajarlo.

    python correr_kaggle.py --comando "optimizacion.optimizar --nombre ensayo-kaggle-01 --limite-casos 3 ..."

Por qué Kaggle: en Modal ninguna GPU se habilita sin tarjeta. Diferencias con la A100 de 40 GB, que se documentan en el
informe: Gemma 4 E4B en bf16 (unos 16 GB) no entra en una T4, así que los pesos se reparten entre las dos
(`ADMISION_DEVICE_MAP=auto`), y la T4 no tiene bf16 nativo, así que es más lenta y la generación en lote puede mover
algún caso. Los tiempos de estas corridas no sirven para la Parte 5, que pide la A100.

Requisitos: el notebook clona el repo, instala con uv y deja `HF_TOKEN` en el entorno (secreto de Kaggle). Ver
`kaggle/README.md`."""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SALIDA = Path(os.environ.get("KAGGLE_SALIDA", "/kaggle/working"))


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


def _salida(*comando) -> str:
    try:
        return subprocess.run(comando, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def entorno_de_la_maquina() -> dict:
    import torch
    import transformers

    return {"gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
            "nvidia_smi": _salida("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv"),
            "torch": torch.__version__, "cuda_de_torch": torch.version.cuda,
            "bf16_nativo": torch.cuda.is_bf16_supported(including_emulation=False),
            "transformers": transformers.__version__, "python": sys.version.split()[0]}


def main():
    p = argparse.ArgumentParser(description="Corre un módulo del repo en Kaggle y empaqueta corridas/.")
    p.add_argument("--comando", required=True, help='módulo y argumentos, como en modal_app.py')
    p.add_argument("--lote", default=os.environ.get("ADMISION_LOTE", ""), help="pisa el lote del modelo")
    args = p.parse_args()

    # El commit y si hay cambios se anotan antes de correr: después `corridas/` tiene archivos nuevos.
    entorno = {"ADMISION_COMMIT": _git("rev-parse", "HEAD"),
               "ADMISION_CAMBIOS_SIN_COMMIT": "1" if _git("status", "--porcelain") else "",
               "ADMISION_DEVICE_MAP": os.environ.get("ADMISION_DEVICE_MAP", "auto"),
               "PYTHONUTF8": "1"}
    if args.lote:
        entorno["ADMISION_LOTE"] = args.lote
    # Lo que el notebook fijó por fuera (modelo, prompt, backend) también queda anotado, sin credenciales.
    heredadas = {k: v for k, v in os.environ.items() if k.startswith("ADMISION_") and k not in entorno and v}
    inicio = datetime.now(timezone.utc)
    registro = {"comando": f"python -m {args.comando}", "inicio": inicio.isoformat(timespec="seconds"),
                "variables": {**heredadas, **entorno}, "maquina": entorno_de_la_maquina()}
    codigo = subprocess.run([sys.executable, "-m", *shlex.split(args.comando)], cwd=RAIZ,
                            env={**os.environ, **entorno}).returncode
    registro["codigo_de_salida"] = codigo
    registro["segundos"] = round((datetime.now(timezone.utc) - inicio).total_seconds())

    nombre = f"kaggle-{inicio.strftime('%Y%m%d-%H%M%S')}"
    carpeta = RAIZ / "corridas" / "entornos"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{nombre}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_ = shutil.make_archive(str(SALIDA / f"corridas-{nombre}"), "zip", RAIZ, "corridas")
    print(f"código de salida {codigo}; entorno en corridas/entornos/{nombre}.json; bajen {zip_}")
    sys.exit(codigo)


if __name__ == "__main__":
    main()
