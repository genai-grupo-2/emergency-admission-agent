"""Regenera clasificación, justificaciones y evidencia de costumbres del historial."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from datos.costumbres import desvios_costumbres, inferir_costumbres, redactar_costumbres
from datos.inspeccionar import CSV, HISTORIAL, inspeccionar
from datos.normas import cargar_parametros, comprobar_normas


def clasificar_fila(fila, traza, parametros, costumbres):
    errores = comprobar_normas(fila, traza, parametros)
    # Los errores normativos prevalecen sobre las costumbres.
    desvios = [] if errores else desvios_costumbres(fila, costumbres)
    return {"id": fila["id"], "tipo": "error" if errores else "ruido" if desvios else "correcta",
            "errores_normas": errores, "desvios_costumbres": desvios}


def escribir_json(ruta: Path, objeto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(objeto, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha256(ruta: Path):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def generar(raiz: Path):
    inspeccion = inspeccionar(raiz)
    if inspeccion["errores"]:
        raise ValueError("Las fuentes no pasan la inspección. Ejecutar datos.inspeccionar y revisar el diagnóstico.")
    with (raiz / CSV).open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    trazas = [json.loads(linea) for linea in (raiz / HISTORIAL).read_text(encoding="utf-8-sig").splitlines()]
    parametros = cargar_parametros(raiz / "normas/original")
    sin_errores = [f for f, t in zip(filas, trazas, strict=True) if not comprobar_normas(f, t, parametros)]
    costumbres = inferir_costumbres(sin_errores)
    resultados = [clasificar_fila(f, t, parametros, costumbres) for f, t in zip(filas, trazas, strict=True)]
    # Todo se valida antes de escribir los entregables.
    assert len(resultados) == 2000 and len({r["id"] for r in resultados}) == 2000
    with (raiz / "historial_clasificado.csv").open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["id", "tipo"], lineterminator="\n")
        escritor.writeheader()
        escritor.writerows({"id": r["id"], "tipo": r["tipo"]} for r in resultados)
    escribir_json(raiz / "datos/evidencia_costumbres.json", costumbres)
    (raiz / "costumbres.md").write_text(redactar_costumbres(costumbres), encoding="utf-8", newline="\n")
    (raiz / "datos/clasificacion_detalle.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in resultados), encoding="utf-8", newline="\n")
    fuentes = [raiz / CSV, raiz / HISTORIAL, *sorted((raiz / "normas/original").glob("*.md")), raiz / "normas/original/parametros.yaml"]
    codigo = [raiz / f"datos/{nombre}.py" for nombre in ("inspeccionar", "normas", "costumbres", "clasificar")]
    resumen = {
        "version": 1, "metodo": "Norma escrita primero, costumbre después; sin etiquetas oficiales de clasificación.",
        "conteos": dict(sorted(Counter(r["tipo"] for r in resultados).items())),
        "fuentes_sha256": {str(p.relative_to(raiz)).replace("\\", "/"): sha256(p) for p in fuentes},
        "codigo_sha256": {str(p.relative_to(raiz)).replace("\\", "/"): sha256(p) for p in codigo},
        "salidas_sha256": {nombre: sha256(raiz / nombre) for nombre in ("historial_clasificado.csv", "costumbres.md", "datos/clasificacion_detalle.jsonl", "datos/evidencia_costumbres.json")},
        "casos_dudosos_sin_resolver": [],
        "limites": [
            "La clasificación es derivada y auditable; no se conoce una etiqueta oficial para medir su exactitud.",
            "No se evalúan minutos o eventos posteriores ausentes de las fuentes.",
            "Si hay circuitos simultáneos o hipótesis de costumbres ambiguas, se detiene y se pide revisión.",
            "El reparto posterior de conversaciones no es un benchmark independiente de la inferencia de costumbres.",
        ],
    }
    escribir_json(raiz / "datos/resumen_clasificacion.json", resumen)
    return resumen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        resumen = generar(args.raiz.resolve())
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Clasificación detenida: {exc}\n")
    print("Historial clasificado:", resumen["conteos"])
    print("Evidencia: costumbres.md y datos/clasificacion_detalle.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
