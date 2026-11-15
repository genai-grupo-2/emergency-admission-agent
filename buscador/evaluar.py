"""Compara el RAG con las funciones oficiales y guarda evidencia reproducible."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from admision.evaluar_rag import cargar_dataset, evaluar_buscador, evaluar_recuperador
from buscador.bm25 import BuscadorBM25


RAIZ = Path(__file__).resolve().parents[1]


def guardar(ruta, contenido):
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ejecutar(normas, consultas, salida):
    dataset = cargar_dataset(consultas)
    if not dataset or len({d["id"] for d in dataset}) != len(dataset):
        raise ValueError("Se requieren consultas no vacias con IDs unicos")
    salida.mkdir(parents=True, exist_ok=True)
    resultados, detalles, no_aplicables = [], [], []
    normalizar = lambda t: re.sub(r"\s+", " ", t).strip()
    for variante in ("original", "b", "c"):
        for modo in ("seccion", "parrafo"):
            buscador = BuscadorBM25(normas / variante, fragmentacion=modo)
            # Comprobar que el texto esperado es aplicable al corpus de esta variante.
            faltantes = []
            for item in dataset:
                for evidencia in item["evidencia"]:
                    if not any(evidencia["seccion"] == s.id and
                               normalizar(evidencia["texto"]) in normalizar(s.texto)
                               for s in buscador.secciones):
                        faltantes.append(item["id"])
            if faltantes:
                if modo == "seccion":
                    no_aplicables.append({"variante": variante, "consultas": sorted(set(faltantes)),
                                          "motivo": "La evidencia literal del dataset no esta en esta variante"})
                continue
            ranking = {}
            for item in dataset:
                recuperados = buscador.recuperar(item["consulta"], 20)
                ranking[item["consulta"]] = recuperados
                detalles.append({
                    "variante": variante, "fragmentacion": modo, "id": item["id"],
                    "consulta": item["consulta"], "tipo": item.get("tipo"), "evidencia": item["evidencia"],
                    "recuperados": [
                        {"id": f.id, "seccion": f.seccion, "texto": f.texto,
                         "evidencias_cubiertas": [i for i, e in enumerate(item["evidencia"])
                                                  if normalizar(e["texto"]) in normalizar(f.texto)]}
                        for f in recuperados],
                })
            def recuperar(consulta, k):
                return ranking[consulta][:k]
            presupuestos = [evaluar_recuperador(recuperar, dataset, b) for b in (256, 512, 1024)]
            for k in (1, 2, 3, 4):
                buscador.k_entorno = k
                resultados.append({"variante": variante, "fragmentacion": modo,
                                   "k1": buscador.k1, "b": buscador.b,
                                   "entorno": evaluar_buscador(buscador, dataset),
                                   "presupuesto": presupuestos})
    if not resultados:
        raise ValueError("Ninguna variante es compatible con la evidencia del dataset")
    # Verificación independiente mediante el punto de entrada oficial del kit.
    if not any(v["variante"] == "original" for v in no_aplicables):
        comando = [sys.executable, "-X", "utf8", "-m", "admision.evaluar_rag", "--entrega",
                   str(RAIZ / "buscador/entrega_rag.py"), "--normas", str(normas / "original"),
                   "--consultas", str(consultas)]
        oficial = json.loads(subprocess.check_output(comando, cwd=RAIZ, encoding="utf-8"))
        base = next(r for r in resultados if r["variante"] == "original" and
                    r["fragmentacion"] == "seccion" and r["entorno"]["k_entorno"] == 2)
        if oficial != {"entorno": base["entorno"], "presupuesto": base["presupuesto"]}:
            raise ValueError("La evaluacion no coincide con el comando oficial")
        guardar(salida / "oficial-seccion-k2.json", oficial)
    guardar(salida / "resumen.json", resultados)
    with (salida / "recuperaciones.jsonl").open("w", encoding="utf-8") as archivo:
        for fila in detalles:
            archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")
    fuentes = [consultas, *sorted(normas.rglob("*.md")), *sorted(normas.rglob("*.yaml")),
               RAIZ / "admision/evaluar_rag.py", RAIZ / "admision/normas.py",
               RAIZ / "buscador/bm25.py", RAIZ / "buscador/evaluar.py",
               RAIZ / "buscador/entrega_rag.py", RAIZ / "uv.lock"]
    guardar(salida / "manifiesto.json", {
        "commit_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True).strip(),
        "comando": "uv run --locked python -m buscador.evaluar --salida resultados/rag",
        "nota": "Los SHA256 identifican el contenido ejecutado, incluso con cambios aun sin commit.",
        "consultas": len(dataset), "estimacion_tokens": "4 caracteres por token (evaluador del kit)",
        "variantes_no_evaluadas": no_aplicables,
        "fuentes_sha256": {p.relative_to(RAIZ).as_posix() if p.is_relative_to(RAIZ) else str(p):
                           hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes},
    })
    lineas = ["# Evaluación de desarrollo del RAG", "",
              "Generado con `uv run --locked python -m buscador.evaluar --salida resultados/rag`.", "",
              "## Resultados con normas originales", "",
              "| Fragmentación | k | Recall | Precisión | Tokens/consulta | Consultas completas |",
              "|---|---:|---:|---:|---:|---:|",
              "| Referencia de cátedra (mission.md) | 2 | 0.875 | 0.492 | 580 | 51/60 |"]
    for r in resultados:
        if r["variante"] != "original":
            continue
        m = r["entorno"]
        lineas.append(f"| {r['fragmentacion']} | {m['k_entorno']} | {m['recall_evidencia']} | "
                      f"{m['precision']} | {m['tokens_por_consulta']} | "
                      f"{m['consultas_con_toda_la_evidencia']}/{m['consultas']} |")
    lineas += ["", "## Presupuestos fijos con normas originales", "",
               "Los presupuestos usan hasta 20 resultados y recorte por caracteres del kit; no dependen de k_entorno.", "",
               "| Fragmentación | Presupuesto | Recall | Precisión | Tokens/consulta | Consultas completas |",
               "|---|---:|---:|---:|---:|---:|"]
    for r in resultados:
        if r["variante"] == "original" and r["entorno"]["k_entorno"] == 2:
            for m in r["presupuesto"]:
                lineas.append(f"| {r['fragmentacion']} | {m['presupuesto_tokens']} | {m['recall_evidencia']} | "
                              f"{m['precision']} | {m['tokens_por_consulta']} | "
                              f"{m['consultas_con_toda_la_evidencia']}/{m['consultas']} |")
    lineas += ["", "## Alcance y auditoría", "",
               "Todas las métricas y desgloses por tipo de las variantes aplicables están en resumen.json.",
               "Las variantes excluidas por evidencia literal incompatible se registran en manifiesto.json; no se cambian sus respuestas esperadas.",
               "recuperaciones.jsonl conserva el ranking completo usado (hasta 20 fragmentos), su texto y la evidencia cubierta.",
               "Para k_entorno se toman los primeros k; los presupuestos recortan el ranking como hace el evaluador oficial.",
               "manifiesto.json registra los hashes de entradas y código. La selección se hace sobre desarrollo, no sobre test secreto.",
               "Los tokens son una estimación por caracteres, no los del tokenizador de un modelo.",
               "Estos resultados no miden casos resueltos por el agente, latencia GPU ni costo de inferencia.", ""]
    (salida / "INFORME.md").write_text("\n".join(lineas), encoding="utf-8")
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normas", type=Path, default=RAIZ / "normas")
    parser.add_argument("--consultas", type=Path, default=RAIZ / "rag/consultas_dev.jsonl")
    parser.add_argument("--salida", type=Path, default=RAIZ / "resultados/rag")
    args = parser.parse_args()
    resultados = ejecutar(args.normas.resolve(), args.consultas.resolve(), args.salida.resolve())
    print(f"Evaluadas {len(resultados)} configuraciones; resultados en {args.salida}")


if __name__ == "__main__":
    main()
