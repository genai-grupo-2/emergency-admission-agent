"""Comparación antes/después de optimizar el prompt, con el modelo sin entrenar y el mismo protocolo: casos resueltos
por los 9 controles en cada versión de las normas, tokens del prompt y contexto por caso. Lee dos corridas de
`evaluacion.evaluar` (no corre nada) y devuelve una tabla en Markdown.

    python -m evaluacion.evaluar --etiqueta prompt-antes   --prompt catedra    --casos validacion
    python -m evaluacion.evaluar --etiqueta prompt-despues --prompt optimizado --casos validacion
    python -m optimizacion.comparar --antes prompt-antes --despues prompt-despues
"""

import argparse
import json
from pathlib import Path

from evaluacion.evaluar import NORMAS, resumen_de

RAIZ = Path(__file__).resolve().parent.parent
PENDIENTE = "pendiente de correr"


def _condicion(etiqueta: str) -> dict | None:
    ruta = RAIZ / "corridas" / "eval" / etiqueta / "condicion.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def fila(nombre: str, etiqueta: str) -> list[str]:
    condicion, resumen = _condicion(etiqueta), resumen_de(etiqueta)
    if condicion is None:
        return [nombre, *[PENDIENTE] * (len(NORMAS) + 3)]
    celdas = [nombre]
    for n in NORMAS:
        r = resumen[n]
        celdas.append(f"{r['resueltos']}/{r['casos']}" if r else ("—" if n not in condicion["normas"] else PENDIENTE))
    hechos = [r for r in resumen.values() if r]
    contexto = round(sum(r["caracteres_de_contexto_por_caso"] for r in hechos) / len(hechos) / 4) if hechos else None
    celdas += [str(condicion["prompt"]["tokens_aprox"]), str(contexto) if contexto is not None else PENDIENTE,
               f"`{etiqueta}` · prompt `{condicion['prompt']['sha256'][:12]}` · commit `{(condicion['commit'] or '?')[:7]}`"]
    return celdas


def tabla(antes: str, despues: str) -> str:
    encabezado = ["Prompt", *[f"Resueltos ({n})" for n in NORMAS], "Tokens del prompt (aprox.)",
                  "Contexto por caso (tokens aprox.)", "Corrida"]
    filas = [encabezado, ["---"] * len(encabezado), fila("Antes (cátedra)", antes), fila("Después (optimizado)", despues)]
    return "\n".join("| " + " | ".join(f) + " |" for f in filas)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--antes", default="prompt-antes")
    ap.add_argument("--despues", default="prompt-despues")
    a = ap.parse_args(argv)
    print(tabla(a.antes, a.despues))


if __name__ == "__main__":
    main()
