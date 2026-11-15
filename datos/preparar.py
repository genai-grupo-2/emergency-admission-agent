"""Regenera la inspección, clasificación y conversaciones con particiones provisionales."""

import argparse
import json
from collections import Counter
from pathlib import Path

from admision.ejemplo import mensaje_de_sistema
from datos.clasificar import escribir_json, generar as generar_clasificacion, sha256, sha256_lf
from datos.conversaciones import preparar_registro
from datos.inspeccionar import CSV, HISTORIAL, REFERENCIA, inspeccionar
from datos.particiones import particionar


def generar(raiz: Path, *, semilla=42, fraccion_validacion=0.1, prompt: Path | None = None):
    if not 0 < fraccion_validacion < 1:
        raise ValueError("La fracción de validación debe estar entre 0 y 1.")
    sistema = prompt.read_bytes().decode("utf-8") if prompt else mensaje_de_sistema()
    if not sistema.strip():
        raise ValueError("El prompt no puede estar vacío.")
    inspeccion = inspeccionar(raiz)
    if inspeccion["errores"]:
        raise ValueError("Las fuentes no pasan la inspección de integridad.")
    escribir_json(raiz / "datos/diagnostico.json", inspeccion)
    clasificacion = generar_clasificacion(raiz)
    detalles = [json.loads(linea) for linea in (raiz / "datos/clasificacion_detalle.jsonl").read_text(encoding="utf-8").splitlines()]
    tipos = {r["id"]: r["tipo"] for r in detalles}
    registros = []
    excluidos = []
    for fuente, nombre in (("historial", HISTORIAL), ("entrenamiento", REFERENCIA)):
        for linea in (raiz / nombre).read_text(encoding="utf-8-sig").splitlines():
            traza = json.loads(linea)
            if fuente == "historial" and tipos[traza["id"]] != "correcta":
                excluidos.append({"id": traza["id"], "tipo": tipos[traza["id"]]})
                continue
            registros.append(preparar_registro(traza, fuente, sistema))
    particiones = particionar(registros, semilla=semilla, fraccion_validacion=fraccion_validacion)
    if not all(particiones.values()):
        raise ValueError("Alguna partición quedó vacía; revisar la semilla, fracción y tamaño de los grupos.")
    # La semilla y los grupos determinan el reparto; no se corta una lista al azar por fila.
    salida = raiz / "datos/conversaciones"
    salida.mkdir(parents=True, exist_ok=True)
    perfiles = {}
    for nombre, filas in particiones.items():
        ruta = salida / f"{nombre}.jsonl"
        ruta.write_text("".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas), encoding="utf-8", newline="\n")
        perfiles[nombre] = {
            "archivo": f"datos/conversaciones/{nombre}.jsonl", "sha256": sha256(ruta), "registros": len(filas),
            "por_fuente": dict(sorted(Counter(f["fuente"] for f in filas).items())),
            "grupos": len({f["grupo"] for f in filas}), "ids": [f["id"] for f in filas],
        }
    ruta_sistema = raiz / "datos/prompts/sistema-usado.txt"
    ruta_sistema.parent.mkdir(parents=True, exist_ok=True)
    ruta_sistema.write_text(sistema, encoding="utf-8", newline="")
    fuentes = [CSV, HISTORIAL, REFERENCIA, "historial_clasificado.csv", "datos/resumen_clasificacion.json"]
    codigo = sorted((raiz / "datos").glob("*.py")) + [raiz / "admision/ejemplo.py"]
    manifiesto = {
        "version": 1,
        "estado": "provisional: revisar prompt y particiones con Juan y Juli antes de entrenar",
        "semilla": semilla,
        "fraccion_validacion_objetivo": fraccion_validacion,
        "algoritmo_particion": "Componentes conectadas por paciente_id o huella de conversación; SHA256(semilla:grupo) elige validación si el valor normalizado es menor que la fracción.",
        "criterio_seleccion": "Sólo historial clasificado correcta y las 800 trazas de referencia; se preservan sus herramientas y resultados sin corregirlos.",
        "clasificacion": clasificacion["conteos"],
        "conversaciones": len(registros),
        "por_fuente": dict(sorted(Counter(r["fuente"] for r in registros).items())),
        "excluidos_historial": excluidos,
        "copias_por_huella_adicionales": len(registros) - len({r["huella_conversacion"] for r in registros}),
        "prompt": {"archivo": "datos/prompts/sistema-usado.txt", "sha256": sha256(ruta_sistema),
                   "origen": "archivo_proporcionado" if prompt else "admision.ejemplo.mensaje_de_sistema",
                   "origen_sha256_lf": sha256_lf(prompt) if prompt else sha256_lf(raiz / "admision/ejemplo.py")},
        "fuentes_sha256_lf": {nombre: sha256_lf(raiz / nombre) for nombre in fuentes},
        "codigo_sha256_lf": {str(p.relative_to(raiz)).replace("\\", "/"): sha256_lf(p) for p in codigo},
        "particiones": perfiles,
        "separacion_comprobada": {campo: True for campo in ("id", "paciente_id", "huella_conversacion", "grupo")},
        "longitudes_caracteres": {
            "minima": min(sum(len(m["content"]) for m in r["messages"]) for r in registros),
            "maxima": max(sum(len(m["content"]) for m in r["messages"]) for r in registros),
        },
        "pendientes": [
            "Juan entrega y congela el prompt optimizado antes del entrenamiento.",
            "Acordar con Juan y Juli estas particiones y el esquema messages/metadatos; la fracción real puede diferir del objetivo por los grupos.",
            "Juli comprueba plantilla de chat, tokenización y longitudes con el modelo elegido; aquí se miden caracteres, no tokens.",
            "La validación interna no es el test secreto ni una evaluación independiente del descubrimiento de costumbres.",
            "La demo y sus nueve controles requieren el checkpoint final de Juli y la entrega de Juan/Pía.",
        ],
    }
    escribir_json(raiz / "datos/manifiesto.json", manifiesto)
    return manifiesto


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--fraccion-validacion", type=float, default=0.1)
    parser.add_argument("--prompt", type=Path, help="Archivo UTF-8 con el mensaje de sistema acordado; por defecto usa el ejemplo del kit.")
    args = parser.parse_args(argv)
    try:
        manifiesto = generar(args.raiz.resolve(), semilla=args.semilla,
                             fraccion_validacion=args.fraccion_validacion, prompt=args.prompt)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Preparación detenida: {exc}\n")
    print("Conversaciones:", manifiesto["por_fuente"])
    for nombre, perfil in manifiesto["particiones"].items():
        print(f"  {nombre}: {perfil['registros']}")
    print("Estado:", manifiesto["estado"])
    print("Procedencia y huellas: datos/manifiesto.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
