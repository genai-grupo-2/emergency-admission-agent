"""Arma una condición de la matriz juntando corridas ya hechas, sin volver a jugar ningún caso.

La matriz pide los 50 casos de práctica. «base» y «solo prompt» ya se jugaron, partidos en dos: los 30 casos de la
partición de optimización (dentro de la búsqueda, `corridas/prompt/<búsqueda>/<sha12>/`) y los 20 de validación
(`corridas/eval/prompt-antes` y `prompt-despues`). Este módulo junta las trazas de las partes y las vuelve a puntuar con
`admision.correr puntuar`, igual que `evaluacion.evaluar`. Antes controla que:

- las partes usen el mismo prompt (misma huella) y el mismo modelo y revisión;
- entre todas cubran exactamente los casos pedidos, sin repetir ninguno, en cada norma;
- ninguna parte haya fallado ni tenga cambios sin commit.

Lo que puede diferir entre partes (el lote, el commit, la máquina) queda anotado en `condicion.json`, en `partes`.

    python -m evaluacion.componer --etiqueta matriz-base \\
        --partes corridas/prompt/busqueda-01/f23f5921894f corridas/eval/prompt-antes
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from agente.prompts import CARPETA, cargar_prompt, huella, tokens_aproximados
from evaluacion.evaluar import NORMAS, RAIZ, _git, resumen_de, seleccionar_casos


def _leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _rel(ruta: Path) -> str:
    return str(ruta.resolve().relative_to(RAIZ)).replace("\\", "/")


def describir_parte(carpeta: Path) -> dict:
    """Prompt, modelo, commit y casos de una parte: una evaluación (`condicion.json`) o un candidato de la búsqueda
    (`prompt.txt` dentro de una carpeta cuyo padre tiene `corrida.json`)."""
    carpeta = Path(carpeta)
    if (carpeta / "condicion.json").exists():
        c = _leer(carpeta / "condicion.json")
        fallas = [n for n, s in c["codigos_de_salida"].items() if s["jugar"] or s["puntuar"]]
        return {"ruta": _rel(carpeta), "tipo": "evaluacion", "prompt_sha256": c["prompt"]["sha256"],
                "modelo": c["modelo"], "commit": c["commit"], "cambios_sin_commit": c["cambios_sin_commit"],
                "normas": c["normas"], "fallas": fallas}
    if (carpeta / "prompt.txt").exists() and (carpeta.parent / "corrida.json").exists():
        meta = _leer(carpeta.parent / "corrida.json")
        texto = (carpeta / "prompt.txt").read_bytes().decode("utf-8").replace("\r\n", "\n")
        fila = next((f for f in map(json.loads, (carpeta.parent / "candidatos.jsonl").read_text(encoding="utf-8")
                                    .splitlines()) if f["sha256"].startswith(carpeta.name)), None)
        return {"ruta": _rel(carpeta), "tipo": "candidato de la búsqueda", "prompt_sha256": huella(texto),
                "modelo": meta["modelo"], "commit": meta["commit"], "cambios_sin_commit": meta["cambios_sin_commit"],
                "normas": meta["normas"], "fallas": ["error del candidato"] if fila is None or fila["error"] else []}
    raise FileNotFoundError(f"{carpeta} no es una evaluación (condicion.json) ni un candidato de una búsqueda")


def componer(etiqueta: str, partes: list[Path], cuales: str = "todos", normas: list[str] = NORMAS,
             exigir_commit_limpio: bool = True) -> dict:
    destino = RAIZ / "corridas" / "eval" / etiqueta
    if destino.exists():
        raise FileExistsError(f"ya existe {destino}: las corridas no se pisan, usen otra --etiqueta")
    info = [describir_parte(p) for p in partes]
    problemas = [f"{i['ruta']}: {', '.join(i['fallas'])}" for i in info if i["fallas"]]
    if exigir_commit_limpio:
        problemas += [f"{i['ruta']}: tiene cambios sin commit" for i in info if i["cambios_sin_commit"]]
    problemas += [f"{i['ruta']}: no tiene la norma {n}" for i in info for n in normas if n not in i["normas"]]
    if len({i["prompt_sha256"] for i in info}) != 1:
        problemas.append("las partes usan prompts distintos")
    if len({(i["modelo"]["repo"], i["modelo"]["revision"]) for i in info}) != 1:
        problemas.append("las partes usan modelos o revisiones distintas")
    if problemas:
        raise ValueError("no se pueden juntar estas partes:\n- " + "\n- ".join(problemas))

    casos = seleccionar_casos(cuales)
    pedidos = [c["id"] for c in casos]
    trazas_por_norma = {}
    for norma in normas:
        filas, por_parte = [], []
        for p in partes:
            lineas = (Path(p) / norma / "trazas.jsonl").read_text(encoding="utf-8").splitlines()
            por_parte.append([json.loads(x)["caso"] for x in lineas])
            filas += lineas
        ids = [i for ids in por_parte for i in ids]
        if len(ids) != len(set(ids)) or set(ids) != set(pedidos):
            raise ValueError(f"en {norma} las partes no cubren exactamente los casos {cuales!r}: "
                             f"{len(ids)} trazas, {len(set(ids))} casos distintos, faltan "
                             f"{sorted(set(pedidos) - set(ids))}")
        orden = {i: k for k, i in enumerate(pedidos)}
        trazas_por_norma[norma] = sorted(filas, key=lambda x: orden[json.loads(x)["caso"]])
        for i, ids_parte in zip(info, por_parte):
            i.setdefault("casos_por_norma", {})[norma] = sorted(ids_parte)

    # El prompt se identifica por la huella: se busca qué versión de prompts/ la tiene.
    sha = info[0]["prompt_sha256"]
    textos = {p.stem: cargar_prompt(p.stem) for p in CARPETA.glob("*.txt")}
    version = next((v for v, t in textos.items() if huella(t) == sha), None)
    comando = "python -m evaluacion.componer --etiqueta " + etiqueta + " --partes " + " ".join(i["ruta"] for i in info)
    condicion = {
        "etiqueta": etiqueta, "compuesta": True, "casos": cuales, "ids": pedidos, "normas": normas,
        "prompt": {"version": version, "archivo": f"prompts/{version}.txt" if version else None, "sha256": sha,
                   "tokens_aprox": tokens_aproximados(textos[version]) if version else None},
        "modelo": {k: info[0]["modelo"][k] for k in ("backend", "repo", "revision", "dtype")},
        "partes": info, "commit": _git("rev-parse", "HEAD"), "cambios_sin_commit": bool(_git("status", "--porcelain")),
        "variables": {}, "comandos": {"componer": comando}, "codigos_de_salida": {},
    }
    destino.mkdir(parents=True)
    for norma in normas:
        salida = destino / norma
        salida.mkdir()
        (salida / "trazas.jsonl").write_text("".join(x + "\n" for x in trazas_por_norma[norma]), encoding="utf-8",
                                             newline="\n")
        tiempos = [_leer(Path(p) / norma / "tiempos.json") for p in partes]
        jugar = round(sum(t["jugar_lote"] for t in tiempos), 3)
        (salida / "tiempos.json").write_text(json.dumps({
            "casos": len(pedidos), "construir_buscador": round(sum(t["construir_buscador"] for t in tiempos), 3),
            "construir_agente": round(sum(t["construir_agente"] for t in tiempos), 3), "error": None,
            "jugar_lote": jugar, "jugar_lote_por_caso": round(jugar / len(pedidos), 3),
            "partes": [{"ruta": i["ruta"], **t} for i, t in zip(info, tiempos)]}, ensure_ascii=False, indent=2),
            encoding="utf-8", newline="\n")
        puntuar = [sys.executable, "-m", "admision.correr", "puntuar", "--trazas", str(salida / "trazas.jsonl"),
                   "--esperadas", str(RAIZ / "practica" / f"esperadas-{norma}.jsonl"), "--salida", str(salida)]
        codigo = subprocess.run(puntuar, cwd=RAIZ, env={**os.environ, "PYTHONUTF8": "1"},
                                stdout=subprocess.DEVNULL).returncode
        condicion["codigos_de_salida"][norma] = {"jugar": None, "puntuar": codigo}
        condicion["comandos"][norma] = {"puntuar": f"python -m admision.correr puntuar --trazas corridas/eval/{etiqueta}/"
                                                   f"{norma}/trazas.jsonl --esperadas practica/esperadas-{norma}.jsonl "
                                                   f"--salida corridas/eval/{etiqueta}/{norma}"}
    condicion["casos_sha256"] = hashlib.sha256(
        "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in casos).encode("utf-8")).hexdigest()
    (destino / "condicion.json").write_text(json.dumps(condicion, ensure_ascii=False, indent=2), encoding="utf-8",
                                            newline="\n")
    return condicion


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--partes", nargs="+", type=Path, required=True)
    ap.add_argument("--casos", choices=["todos", "validacion", "optimizacion"], default="todos")
    a = ap.parse_args(argv)
    condicion = componer(a.etiqueta, a.partes, a.casos)
    resumen = resumen_de(a.etiqueta)
    print(json.dumps({n: r and {"resueltos": r["resueltos"], "casos": r["casos"]} for n, r in resumen.items()},
                     ensure_ascii=False, indent=2))
    return 1 if any(c["puntuar"] for c in condicion["codigos_de_salida"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
