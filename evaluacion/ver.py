"""Muestra un caso de una corrida: la conversación con el modelo, lo que trajo cada búsqueda, la ficha y los 9 controles.

    python -m evaluacion.ver --corrida demo --norma b --caso pev-001
"""

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _buscar(ruta: Path, caso: str) -> dict:
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        fila = json.loads(linea)
        if fila["caso"] == caso:
            return fila
    raise KeyError(f"el caso {caso} no está en {ruta}")


def mostrar(corrida: str, norma: str, caso: str) -> str:
    carpeta = RAIZ / "corridas" / "eval" / corrida / norma
    traza = _buscar(carpeta / "trazas.jsonl", caso)
    salida = [f"# {caso} · normas {norma} · corrida {corrida}", "", "## Conversación"]
    for m in traza["mensajes"]:
        if m["role"] != "system":
            salida += [f"[{m['role']}] {m['content']}", ""]
    salida.append("## Ficha registrada")
    salida.append(json.dumps(traza["decision"], ensure_ascii=False, indent=2) if traza["decision"] else "(sin ficha)")
    if (carpeta / "resultados.jsonl").exists():
        r = _buscar(carpeta / "resultados.jsonl", caso)
        salida += ["", f"## Controles: {'RESUELTO' if r['resuelto'] else 'no resuelto'} "
                       f"({sum(r['controles'].values())}/9)"]
        salida += [f"- {'ok ' if ok else 'MAL'} {k}" for k, ok in r["controles"].items()]
    return "\n".join(salida)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corrida", required=True)
    ap.add_argument("--norma", required=True, choices=["original", "b", "c"])
    ap.add_argument("--caso", required=True)
    a = ap.parse_args(argv)
    print(mostrar(a.corrida, a.norma, a.caso))


if __name__ == "__main__":
    main()
