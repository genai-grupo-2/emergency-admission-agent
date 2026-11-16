"""La matriz del informe (mission.md, Parte 4): 4 condiciones × 3 versiones de las normas sobre los 50 casos de práctica,
al lado de la referencia de la cátedra.

Las condiciones están en `evaluacion/matriz.json`. Para que la comparación sea válida, «solo entrenamiento» y «ambos»
usan dos checkpoints con la misma configuración de entrenamiento (datos, semilla, épocas) que sólo difieren en el
mensaje de sistema de las conversaciones: el de la cátedra y el optimizado. Esos dos checkpoints los publica Juli (#4);
hasta entonces su `modelo_repo`/`modelo_revision` es null y la condición figura como bloqueada.

    python -m evaluacion.matriz                       # sólo la tabla, con lo que ya está corrido
    python -m evaluacion.matriz --correr base "solo prompt"   # corre lo que falte (en Modal: modal_app.py)
"""

import argparse
import json
import sys
from pathlib import Path

from agente.prompts import CARPETA
from evaluacion.evaluar import NORMAS, entorno_de_la_condicion, evaluar, resumen_de, seleccionar_casos

RAIZ = Path(__file__).resolve().parent.parent
RUTA = Path(__file__).resolve().parent / "matriz.json"


def cargar_matriz(ruta: Path = RUTA) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def etiqueta(condicion: dict) -> str:
    return "matriz-" + condicion["nombre"].replace(" ", "-")


def estado(condicion: dict) -> str | None:
    """None si se puede correr; si no, por qué no."""
    if not condicion["modelo_repo"] or not condicion["modelo_revision"]:
        return "bloqueado: falta el checkpoint de Juli (#4)"
    if not (CARPETA / f"{condicion['prompt']}.txt").exists():
        return f"bloqueado: falta congelar el prompt {condicion['prompt']!r}"
    return None


def tabla(matriz: dict) -> str:
    encabezado = ["Condición", *[f"Normas {n}" for n in NORMAS], "Corrida"]
    filas = [encabezado, ["---"] * len(encabezado)]
    for c in matriz["condiciones"]:
        motivo, resumen = estado(c), resumen_de(etiqueta(c))
        celdas = [c["nombre"]]
        for n in NORMAS:
            r = resumen[n]
            celdas.append(f"{r['resueltos']}/{r['casos']}" if r else (motivo or "pendiente de correr"))
        hecho = (RAIZ / "corridas" / "eval" / etiqueta(c) / "condicion.json").exists()
        celdas.append(f"`corridas/eval/{etiqueta(c)}`" if hecho else "—")
        filas.append(celdas)
    for nombre, valores in matriz["referencia_catedra"].items():
        filas.append([f"Referencia de la cátedra, {nombre}", *[f"{valores[n]}/50" for n in NORMAS], "mission.md"])
    return "\n".join("| " + " | ".join(f) + " |" for f in filas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--correr", nargs="*", help="condiciones a correr (sin nombres: todas las que se puedan)")
    a = ap.parse_args(argv)
    matriz = cargar_matriz()
    codigo = 0
    if a.correr is not None:
        pedidas = [c for c in matriz["condiciones"] if not a.correr or c["nombre"] in a.correr]
        for c in pedidas:
            motivo = estado(c)
            if motivo or (RAIZ / "corridas" / "eval" / etiqueta(c)).exists():
                print(f"{c['nombre']}: {motivo or 'ya corrida, no se repite'}", file=sys.stderr)
                codigo = codigo or (1 if motivo else 0)
                continue
            extra = entorno_de_la_condicion(c["prompt"], c["modelo_repo"], c["modelo_revision"], None)
            evaluar(etiqueta(c), seleccionar_casos(matriz["casos"]), NORMAS, extra, matriz["casos"])
    print(tabla(matriz))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
