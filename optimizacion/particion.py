"""Partición de los 50 casos de práctica para optimizar el prompt, por caso: las tres versiones de las normas de un caso
quedan siempre del mismo lado.

- `optimizacion`: los casos con los que el optimizador compara candidatos.
- `validacion`: los casos que el optimizador nunca ve; se usan una sola vez, para la comparación antes/después del
  prompt congelado.

El test secreto de la cátedra no se usa nunca. Regenerar (idéntico con la misma semilla):

    python -m optimizacion.particion --semilla 42 --validacion 20
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

from admision.casos import leer_jsonl

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "practica" / "casos.jsonl"
SALIDA = Path(__file__).resolve().parent / "particion.json"


def particionar(ids: list[str], semilla: int, n_validacion: int) -> dict:
    ordenados = sorted(ids)
    if len(set(ordenados)) != len(ordenados):
        raise ValueError("hay ids de caso repetidos")
    if not 0 < n_validacion < len(ordenados):
        raise ValueError("la validación tiene que tener entre 1 y n-1 casos")
    mezclados = ordenados[:]
    random.Random(semilla).shuffle(mezclados)
    return {"optimizacion": sorted(mezclados[n_validacion:]), "validacion": sorted(mezclados[:n_validacion])}


def cargar_particion(ruta: Path = SALIDA) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--validacion", type=int, default=20)
    a = ap.parse_args(argv)
    datos = CASOS.read_bytes().replace(b"\r\n", b"\n")
    particion = particionar([c["id"] for c in leer_jsonl(CASOS)], a.semilla, a.validacion)
    salida = {"semilla": a.semilla, "casos_sha256": hashlib.sha256(datos).hexdigest(), **particion}
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(particion['optimizacion'])} casos para optimizar y {len(particion['validacion'])} de validación "
          f"en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
