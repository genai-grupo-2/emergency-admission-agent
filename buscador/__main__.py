"""Inspección manual del RAG sin cargar un modelo."""

import argparse
import json
from pathlib import Path

from .bm25 import BuscadorBM25


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normas", type=Path, required=True)
    parser.add_argument("--consulta", required=True)
    parser.add_argument("--k", type=int, default=2)
    parser.add_argument("--fragmentacion", choices=("seccion", "parrafo"), default="seccion")
    args = parser.parse_args()
    buscador = BuscadorBM25(args.normas, fragmentacion=args.fragmentacion)
    resultados = buscador.recuperar(args.consulta, args.k)
    print(json.dumps([{"id": f.id, "seccion": f.seccion, "texto": f.texto} for f in resultados],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
