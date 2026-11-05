"""Comprueba procedencia, conversaciones y separación de los entregables generados."""

import argparse
import csv
import json
from pathlib import Path

from datos.clasificar import sha256, sha256_lf
from datos.conversaciones import preparar_registro
from datos.inspeccionar import HISTORIAL, REFERENCIA
from datos.particiones import particionar


def verificar(raiz: Path):
    raiz = raiz.resolve()

    def ruta(nombre):
        resultado = (raiz / nombre).resolve()
        if not resultado.is_relative_to(raiz):
            raise ValueError("Un archivo del manifiesto está fuera del repositorio.")
        return resultado

    manifiesto = json.loads(ruta("datos/manifiesto.json").read_text(encoding="utf-8"))
    resumen = json.loads(ruta("datos/resumen_clasificacion.json").read_text(encoding="utf-8"))
    for documento in (manifiesto, resumen):
        for clave in ("fuentes_sha256_lf", "codigo_sha256_lf"):
            for nombre, huella in documento[clave].items():
                if sha256_lf(ruta(nombre)) != huella:
                    raise ValueError(f"Cambió una fuente o el código: {nombre}. Regenerar y revisar los resultados.")
    for nombre, huella in resumen["salidas_sha256"].items():
        if sha256(ruta(nombre)) != huella:
            raise ValueError(f"Cambió un entregable de clasificación: {nombre}")
    sistema_path = ruta(manifiesto["prompt"]["archivo"])
    if sha256(sistema_path) != manifiesto["prompt"]["sha256"]:
        raise ValueError("El prompt no coincide con el registrado.")
    sistema = sistema_path.read_bytes().decode("utf-8")
    with ruta("historial_clasificado.csv").open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != ["id", "tipo"]:
            raise ValueError("La clasificación no tiene exactamente las columnas id,tipo.")
        etiquetas = list(lector)
    if len(etiquetas) != 2000 or len({e["id"] for e in etiquetas}) != 2000:
        raise ValueError("La clasificación no cubre las 2.000 admisiones únicas.")
    tipos = {e["id"]: e["tipo"] for e in etiquetas}
    originales = {}
    for fuente, nombre in (("historial", HISTORIAL), ("entrenamiento", REFERENCIA)):
        for linea in ruta(nombre).read_text(encoding="utf-8-sig").splitlines():
            traza = json.loads(linea)
            if fuente == "entrenamiento" or tipos[traza["id"]] == "correcta":
                originales[f"{fuente}:{traza['id']}"] = (fuente, traza)
    particiones = {}
    for nombre, perfil in manifiesto["particiones"].items():
        archivo = ruta(perfil["archivo"])
        if sha256(archivo) != perfil["sha256"]:
            raise ValueError(f"Cambió el archivo de conversaciones: {nombre}")
        filas = [json.loads(linea) for linea in archivo.read_text(encoding="utf-8").splitlines()]
        if len(filas) != perfil["registros"] or [f["id"] for f in filas] != perfil["ids"]:
            raise ValueError(f"Las cantidades o IDs no coinciden: {nombre}")
        for fila in filas:
            if fila["id"] not in originales:
                raise ValueError(f"Conversación no seleccionada por el criterio de curado: {fila['id']}")
            fuente, traza = originales[fila["id"]]
            esperado = preparar_registro(traza, fuente, sistema)
            obtenido = {k: v for k, v in fila.items() if k != "grupo"}
            if json.dumps(obtenido, sort_keys=True) != json.dumps(esperado, sort_keys=True):
                raise ValueError(f"Los mensajes o la procedencia no coinciden con la traza: {fila['id']}")
        particiones[nombre] = filas
    todas = [fila for filas in particiones.values() for fila in filas]
    ids = [f["id"] for f in todas]
    if len(ids) != len(set(ids)) or set(ids) != set(originales) or len(ids) != manifiesto["conversaciones"]:
        raise ValueError("Faltan conversaciones seleccionadas o hay duplicados.")
    reproducidas = particionar(todas, semilla=manifiesto["semilla"], fraccion_validacion=manifiesto["fraccion_validacion_objetivo"])
    if reproducidas != particiones:
        raise ValueError("La semilla y los grupos no reproducen el reparto registrado.")
    return {"conversaciones": len(todas), "particiones": {k: len(v) for k, v in particiones.items()},
            "resultado": "ok", "estado": manifiesto["estado"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        resultado = verificar(args.raiz)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Verificación fallida: {exc}\n")
    print("Verificación:", resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
