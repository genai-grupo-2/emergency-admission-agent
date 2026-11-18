"""Arma el subconjunto de casos de práctica que se juega para la demo, a partir de `datos/candidatos_demo.json`.

Entran los tiempo-dependientes que llegan en ambulancia y los de costumbre sin circuito. Así se gasta poca GPU y no
se repite la corrida completa de la matriz. Copia las líneas de `practica/casos.jsonl` tal cual y en su orden. No lee
respuestas esperadas.

    uv run --locked python -X utf8 -m datos.casos_demo
"""

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def elegir(candidatos: dict) -> list[str]:
    ambulancia = [c["id"] for c in candidatos["tiempo_dependiente"] if c["llegada"] == "en ambulancia"]
    sin_circuito = [c["id"] for c in candidatos["costumbre"] if c["circuito_probable"] is None]
    return sorted(set(ambulancia) | set(sin_circuito))


def filtrar(lineas: list[str], ids: list[str]) -> list[str]:
    elegidas = [linea for linea in lineas if linea.strip() and json.loads(linea)["id"] in ids]
    faltan = set(ids) - {json.loads(linea)["id"] for linea in elegidas}
    if faltan:
        raise KeyError(f"no están en los casos: {sorted(faltan)}")
    return elegidas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidatos", type=Path, default=RAIZ / "datos" / "candidatos_demo.json")
    parser.add_argument("--casos", type=Path, default=RAIZ / "practica" / "casos.jsonl")
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos" / "demo" / "casos.jsonl")
    args = parser.parse_args()
    ids = elegir(json.loads(args.candidatos.read_text(encoding="utf-8")))
    lineas = args.casos.read_text(encoding="utf-8").splitlines(keepends=True)
    elegidas = filtrar(lineas, ids)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text("".join(l if l.endswith("\n") else l + "\n" for l in elegidas), encoding="utf-8",
                           newline="\n")
    print(f"{len(elegidas)} casos en {args.salida}: {', '.join(ids)}")


if __name__ == "__main__":
    main()
