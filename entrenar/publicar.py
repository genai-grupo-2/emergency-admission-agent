"""Fusiona un checkpoint LoRA con el modelo base y lo publica en el repositorio PRIVADO de Hugging Face del grupo.

    python -m entrenar.publicar --nombre sft-catedra-01 --paso 272 --repo <usuario-o-org>/<repo>

Se publican pesos completos fusionados en bf16: `entrega.py` los carga con `ADMISION_MODELO_REPO` y
`ADMISION_MODELO_REVISION` sin ningún cambio de código y en una sola carga (`agente/modelo.py`). Junto a los pesos
quedan el adaptador original (`adaptador/`, con el modelo base y su revisión en su `adapter_config.json`) y
`ENTRENAMIENTO.json` con la procedencia (corrida, paso, datos, prompt, semilla, commit, W&B).

La revisión que importa es el hash del commit que devuelve Hugging Face: se anota en el manifiesto de la corrida y en
`corridas/entrenamiento/<nombre>/publicacion-paso-<N>.json`, y se le entrega a Juan, Pía y Cande. Cada checkpoint que
se cita en el informe se publica con este mismo comando (un paso por vez; el repo guarda cada uno como un commit).

Fusionar redondea a bf16: lo que se evalúa y lo que se publica es el modelo fusionado, así que los números del informe
corresponden exactamente a lo que carga la cátedra."""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from entrenar.manifiesto import Manifiesto, ahora

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CORRIDAS = RAIZ / "corridas" / "entrenamiento"


def ficha(manifiesto: dict, paso: int, checkpoint: dict) -> dict:
    """Procedencia que viaja con el modelo publicado."""
    return {
        "corrida": manifiesto["nombre"], "paso": paso, "semilla": manifiesto["semilla"],
        "modelo_base": {"repo": manifiesto["config"]["modelo"]["repo"],
                        "revision": manifiesto["config"]["modelo"]["revision"]},
        "prompt": manifiesto["datos"]["prompt"], "datos": {k: manifiesto["datos"][k] for k in ("train", "validacion")},
        "git": manifiesto["git"], "wandb": manifiesto.get("wandb"),
        "perdida_validacion": checkpoint.get("perdida_validacion"),
        "config": manifiesto["config"],
    }


def publicar(nombre: str, paso: int, repo: str, carpeta_checkpoints: Path | None, privado: bool = True) -> dict:
    import torch
    import transformers
    from huggingface_hub import HfApi
    from peft import PeftModel

    ruta_manifiesto = CARPETA_CORRIDAS / nombre / "manifiesto.json"
    manifiesto = Manifiesto.retomar(ruta_manifiesto)
    checkpoint = next((c for c in manifiesto.datos["checkpoints"] if c["paso"] == paso), None)
    if checkpoint is None:
        pasos = [c["paso"] for c in manifiesto.datos["checkpoints"]]
        raise SystemExit(f"la corrida {nombre} no tiene el paso {paso}; tiene {pasos}")
    adaptador = Path(checkpoint["ruta"]) if carpeta_checkpoints is None else carpeta_checkpoints / f"paso-{paso:05d}"
    modelo_base = manifiesto.datos["config"]["modelo"]
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("falta HF_TOKEN (con permiso de escritura sobre el repositorio del grupo)")
    if not (adaptador / "adapter_model.safetensors").exists():
        # Sesión nueva sin los checkpoints locales: se baja el adaptador que el entrenamiento copió a Hugging Face,
        # en la revisión exacta que quedó anotada en el manifiesto.
        copia = checkpoint.get("hf_adaptador")
        if not copia:
            raise SystemExit(f"no está el adaptador en {adaptador} ni hay copia en Hugging Face anotada en el manifiesto")
        from huggingface_hub import snapshot_download

        descarga = Path(tempfile.mkdtemp(prefix="adaptador-"))
        snapshot_download(copia["repo"], revision=copia["revision"], token=token, local_dir=str(descarga),
                          allow_patterns=[f"adaptadores/{nombre}/paso-{paso:05d}/*"])
        adaptador = descarga / "adaptadores" / nombre / f"paso-{paso:05d}"
        print(f"adaptador bajado de {copia['repo']} @ {copia['revision'][:10]}", flush=True)
        if not (adaptador / "adapter_model.safetensors").exists():
            raise SystemExit(f"la copia en Hugging Face no tiene el adaptador del paso {paso}")

    # Misma clase que el entrenamiento y que agente/modelo.py, así lo publicado se recarga igual.
    argumentos = dict(revision=modelo_base["revision"], token=token, dtype=getattr(torch, modelo_base["dtype"]),
                      device_map="cpu")
    try:
        base = transformers.AutoModelForCausalLM.from_pretrained(modelo_base["repo"], **argumentos)
    except ValueError:
        base = transformers.AutoModelForImageTextToText.from_pretrained(modelo_base["repo"], **argumentos)
    fusionado = PeftModel.from_pretrained(base, str(adaptador)).merge_and_unload()
    tokenizador = transformers.AutoTokenizer.from_pretrained(modelo_base["repo"], revision=modelo_base["revision"],
                                                             token=token)
    with tempfile.TemporaryDirectory() as t:
        salida = Path(t)
        fusionado.save_pretrained(salida, safe_serialization=True)
        tokenizador.save_pretrained(salida)
        shutil.copytree(adaptador, salida / "adaptador", ignore=shutil.ignore_patterns("estado.pt"))
        (salida / "ENTRENAMIENTO.json").write_text(
            json.dumps(ficha(manifiesto.datos, paso, checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")
        api = HfApi(token=token)
        api.create_repo(repo, private=privado, exist_ok=True)
        info = api.upload_folder(repo_id=repo, folder_path=str(salida), repo_type="model",
                                 commit_message=f"{nombre} paso {paso} (pesos fusionados bf16 + adaptador)")
    publicacion = {"repo": repo, "revision": info.oid, "paso": paso, "corrida": nombre, "privado": privado,
                   "publicado": ahora(), "carga": {"ADMISION_MODELO_REPO": repo, "ADMISION_MODELO_REVISION": info.oid}}
    manifiesto.actualizar_checkpoint(paso, hf=publicacion)
    destino = CARPETA_CORRIDAS / nombre / f"publicacion-paso-{paso}.json"
    destino.write_text(json.dumps(publicacion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"publicado: {repo} @ {info.oid}\n  ADMISION_MODELO_REPO={repo}\n  ADMISION_MODELO_REVISION={info.oid}")
    return publicacion


def principal(argv=None) -> int:
    p = argparse.ArgumentParser(description="Fusiona un checkpoint LoRA y lo sube al repo privado de Hugging Face.")
    p.add_argument("--nombre", required=True, help="nombre de la corrida (corridas/entrenamiento/<nombre>)")
    p.add_argument("--paso", type=int, required=True)
    p.add_argument("--repo", required=True, help="<usuario-o-org>/<repo> privado del grupo")
    p.add_argument("--checkpoints", help="carpeta con los paso-NNNNN (por defecto, la ruta del manifiesto)")
    args = p.parse_args(argv)
    publicar(args.nombre, args.paso, args.repo, Path(args.checkpoints) if args.checkpoints else None)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
