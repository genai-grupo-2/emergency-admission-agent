"""Evaluación completa de una condición (prompt + punto de control) con las normas original, b y c.

Por cada versión de las normas hace lo mismo que la cátedra, en dos procesos separados:

1. arma una carpeta `entradas/` aparte, con sólo los casos y las normas, y corre `python -m admision.correr jugar`
   (el agente nunca tiene a mano las fichas esperadas);
2. corre `python -m admision.correr puntuar` con `practica/esperadas-<norma>.jsonl`.

Todo queda en `corridas/eval/<etiqueta>/<norma>/` (trazas.jsonl con las conversaciones completas, tiempos.json,
resultados.jsonl por caso y resumen.json), más `corridas/eval/<etiqueta>/condicion.json` con el prompt (versión y
sha256), el modelo y su revisión, el commit y los comandos exactos. Las corridas no se pisan.

    python -m evaluacion.evaluar --etiqueta base --prompt catedra
    python -m evaluacion.evaluar --etiqueta prompt-despues --prompt optimizado --casos validacion
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from admision.casos import leer_jsonl
from agente.config import cargar_config
from agente.prompts import cargar_prompt, huella, ruta_prompt, tokens_aproximados
from optimizacion.particion import cargar_particion

RAIZ = Path(__file__).resolve().parent.parent
NORMAS = ["original", "b", "c"]


def _git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def seleccionar_casos(cuales: str) -> list[dict]:
    casos = leer_jsonl(RAIZ / "practica" / "casos.jsonl")
    if cuales == "todos":
        return casos
    ids = set(cargar_particion()[cuales])
    return [c for c in casos if c["id"] in ids]


def entorno_de_la_condicion(prompt: str | None, repo: str | None, revision: str | None,
                            backend: str | None) -> dict:
    extra = {"ADMISION_PROMPT": prompt, "ADMISION_MODELO_REPO": repo, "ADMISION_MODELO_REVISION": revision,
             "ADMISION_BACKEND": backend}
    return {k: v for k, v in extra.items() if v}


def evaluar(etiqueta: str, casos: list[dict], normas: list[str], extra_env: dict, cuales: str) -> dict:
    destino = RAIZ / "corridas" / "eval" / etiqueta
    if destino.exists():
        raise FileExistsError(f"ya existe {destino}: las corridas no se pisan, usen otra --etiqueta")
    env = {**os.environ, **extra_env, "PYTHONUTF8": "1"}
    config = cargar_config(entorno=env)
    texto = cargar_prompt(config["prompt"]["version"])
    condicion = {
        "etiqueta": etiqueta, "casos": cuales, "ids": [c["id"] for c in casos], "normas": normas,
        "prompt": {"version": config["prompt"]["version"], "archivo": str(ruta_prompt(config["prompt"]["version"])
                                                                          .relative_to(RAIZ)).replace("\\", "/"),
                   "sha256": huella(texto), "tokens_aprox": tokens_aproximados(texto)},
        "modelo": config["modelo"], "agente": config["agente"], "buscador": config["buscador"],
        "commit": os.environ.get("ADMISION_COMMIT") or _git("rev-parse", "HEAD"),
        "cambios_sin_commit": (os.environ.get("ADMISION_CAMBIOS_SIN_COMMIT") == "1"
                               if "ADMISION_CAMBIOS_SIN_COMMIT" in os.environ else bool(_git("status", "--porcelain"))),
        "variables": extra_env, "comandos": {}, "codigos_de_salida": {},
    }
    destino.mkdir(parents=True)
    for norma in normas:
        salida = destino / norma
        with tempfile.TemporaryDirectory(prefix="admision-entradas-") as carpeta:
            entradas = Path(carpeta) / "entradas"
            shutil.copytree(RAIZ / "normas" / norma, entradas / "normas" / norma)
            (entradas / "casos.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in casos),
                                                  encoding="utf-8")
            jugar = [sys.executable, "-m", "admision.correr", "jugar", "--entrega", str(RAIZ / "entrega.py"),
                     "--casos", str(entradas / "casos.jsonl"), "--normas", str(entradas / "normas" / norma),
                     "--salida", str(salida)]
            codigo_jugar = subprocess.run(jugar, cwd=RAIZ, env=env).returncode
        puntuar = [sys.executable, "-m", "admision.correr", "puntuar", "--trazas", str(salida / "trazas.jsonl"),
                   "--esperadas", str(RAIZ / "practica" / f"esperadas-{norma}.jsonl"), "--salida", str(salida)]
        codigo_puntuar = (subprocess.run(puntuar, cwd=RAIZ, env=env, stdout=subprocess.DEVNULL).returncode
                          if (salida / "trazas.jsonl").exists() else None)
        condicion["comandos"][norma] = {"jugar": "python -m admision.correr jugar --entrega entrega.py --casos "
                                                 f"entradas/casos.jsonl --normas entradas/normas/{norma} --salida "
                                                 f"corridas/eval/{etiqueta}/{norma}",
                                        "puntuar": f"python -m admision.correr puntuar --trazas corridas/eval/"
                                                   f"{etiqueta}/{norma}/trazas.jsonl --esperadas practica/"
                                                   f"esperadas-{norma}.jsonl --salida corridas/eval/{etiqueta}/{norma}"}
        condicion["codigos_de_salida"][norma] = {"jugar": codigo_jugar, "puntuar": codigo_puntuar}
    condicion["casos_sha256"] = hashlib.sha256(
        "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in casos).encode("utf-8")).hexdigest()
    (destino / "condicion.json").write_text(json.dumps(condicion, ensure_ascii=False, indent=2), encoding="utf-8")
    return condicion


def resumen_de(etiqueta: str) -> dict:
    """{norma: resumen.json o None} de una corrida ya hecha."""
    carpeta = RAIZ / "corridas" / "eval" / etiqueta
    return {n: json.loads((carpeta / n / "resumen.json").read_text(encoding="utf-8"))
            if (carpeta / n / "resumen.json").exists() else None for n in NORMAS}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--prompt", help="versión en prompts/ o ruta a un .txt (por defecto, la de configuracion.json)")
    ap.add_argument("--modelo-repo")
    ap.add_argument("--modelo-revision")
    ap.add_argument("--backend", choices=["hf", "falso"])
    ap.add_argument("--casos", choices=["todos", "validacion", "optimizacion"], default="todos")
    ap.add_argument("--ids", nargs="+", help="sólo estos casos (por ejemplo, para una demo)")
    ap.add_argument("--normas", nargs="+", choices=NORMAS, default=NORMAS)
    a = ap.parse_args(argv)
    casos = seleccionar_casos(a.casos)
    if a.ids:
        casos = [c for c in casos if c["id"] in set(a.ids)]
        if len(casos) != len(set(a.ids)):
            ap.error("algún id no está entre los casos elegidos")
    extra = entorno_de_la_condicion(a.prompt, a.modelo_repo, a.modelo_revision, a.backend)
    condicion = evaluar(a.etiqueta, casos, a.normas, extra, ",".join(a.ids) if a.ids else a.casos)
    resumen = resumen_de(a.etiqueta)
    print(json.dumps({n: (r and {"resueltos": r["resueltos"], "casos": r["casos"], "error": r.get("error")})
                      for n, r in resumen.items() if n in a.normas}, ensure_ascii=False, indent=2))
    fallas = [n for n, c in condicion["codigos_de_salida"].items() if c["jugar"] or c["puntuar"]]
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
