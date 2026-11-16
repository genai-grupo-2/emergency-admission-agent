"""Optimización del mensaje de sistema con el modelo SIN entrenar, antes del entrenamiento (mission.md, Parte 3).

Estrategia: búsqueda local por bloques (`optimizacion/bloques.py`). Se evalúan las semillas (la primera es el prompt de
la cátedra), y desde la mejor se prueban todos los candidatos que cambian un solo bloque; si alguno mejora el puntaje,
se pasa a él y se repite, hasta que ninguno mejora o se acaba el presupuesto de evaluaciones.

- Puntaje = casos resueltos / episodios − λ · tokens del prompt / 1000. λ se fija antes de correr (por defecto 0,05:
  1.000 tokens de prompt valen 5 puntos de tasa de resolución). Desempata la media de controles y después el largo.
- Cada evaluación juega con `admision.correr` los casos de la partición `optimizacion` con las normas pedidas y los
  puntúa recién después de jugar. La partición `validacion` y el test no se usan acá.
- Decodificación greedy: con el mismo commit, modelo, revisión y partición la búsqueda repite los mismos candidatos.
- Todo queda en `corridas/prompt/<nombre>/`: `candidatos.jsonl` (una fila por candidato, también los que fallaron),
  el prompt y las trazas completas de cada evaluación, y `resumen.json` con el mejor y la frontera resueltos/tokens.

Por qué no DSPy/GEPA: el agente es un protocolo JSON de varios turnos con herramientas, que no encaja en un
`dspy.Module` sin reescribirlo, y GEPA necesita un modelo que reflexione sobre los errores: el Gemma sin entrenar
propone malas mutaciones y uno externo choca con la regla de no usar servicios externos. La búsqueda por bloques es
chica, determinista y auditable, y optimiza también el largo, que la cátedra valora.

    python -m optimizacion.optimizar --nombre busqueda-01 --normas original b c --max-evaluaciones 24
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from admision.casos import cargar_casos
from admision.correr import correr
from agente.ciclo import Agente
from agente.config import cargar_config
from agente.prompts import huella, tokens_aproximados
from optimizacion.bloques import SEMILLAS, armar, vecinos
from optimizacion.particion import cargar_particion

RAIZ = Path(__file__).resolve().parent.parent


def puntaje(evaluacion: dict, tokens: int, lam: float) -> float | None:
    """None si la evaluación falló: el candidato queda registrado pero no compite."""
    if evaluacion.get("error") or not evaluacion.get("episodios"):
        return None
    return round(evaluacion["resueltos"] / evaluacion["episodios"] - lam * tokens / 1000, 6)


def _clave(fila: dict) -> tuple:
    p = -math.inf if fila["puntaje"] is None else fila["puntaje"]
    return (p, fila.get("parcial_medio") or 0, -fila["tokens"])


def frontera(filas: list[dict]) -> list[dict]:
    """Candidatos no dominados en (más resueltos, menos tokens)."""
    validas = [f for f in filas if f["puntaje"] is not None]
    return sorted(({"sha256": f["sha256"], "resueltos": f["resueltos"], "tokens": f["tokens"]} for f in validas
                   if not any(o["resueltos"] >= f["resueltos"] and o["tokens"] <= f["tokens"] and
                              (o["resueltos"], -o["tokens"]) != (f["resueltos"], -f["tokens"]) for o in validas)),
                  key=lambda x: x["tokens"])


def buscar(evaluar, contar_tokens, lam: float, max_evaluaciones: int, registrar=lambda fila: None,
           semillas: dict = SEMILLAS) -> dict:
    """`evaluar(texto, sha)` devuelve {"episodios", "resueltos", "parcial_medio", ...} o levanta una excepción.
    `registrar(fila)` recibe cada candidato evaluado, en orden. Devuelve el mejor, la historia y el motivo de fin."""
    vistos: dict[str, dict] = {}

    def probar(bloques, padre, mutacion):
        texto = armar(bloques)
        sha = huella(texto)
        if sha in vistos:
            return vistos[sha]
        if len(vistos) >= max_evaluaciones:
            return None
        inicio = time.perf_counter()
        try:
            ev, error = evaluar(texto, sha), None
        except Exception as e:  # una evaluación que falla queda registrada y la búsqueda sigue
            ev, error = {}, f"{type(e).__name__}: {e}"
        tokens = contar_tokens(texto)
        fila = {"n": len(vistos) + 1, "sha256": sha, "padre": padre, "mutacion": mutacion, "bloques": bloques,
                "tokens": tokens, "tokens_aprox": tokens_aproximados(texto), "caracteres": len(texto),
                "episodios": ev.get("episodios"), "resueltos": ev.get("resueltos"),
                "parcial_medio": ev.get("parcial_medio"), "por_norma": ev.get("por_norma"),
                "error": error or ev.get("error"), "segundos": round(time.perf_counter() - inicio, 1)}
        fila["puntaje"] = puntaje({**ev, "error": fila["error"]}, tokens, lam)
        vistos[sha] = fila
        registrar(fila)
        return fila

    actual = None
    for nombre, bloques in semillas.items():
        fila = probar(bloques, None, f"semilla:{nombre}")
        if fila and (actual is None or _clave(fila) > _clave(actual)):
            actual = fila
    motivo = "sin mejora"
    while actual is not None:
        mejor_vecino = None
        for mutacion, bloques in vecinos(actual["bloques"]):
            fila = probar(bloques, actual["sha256"], mutacion)
            if fila is None:
                motivo = "presupuesto agotado"
                break
            if mejor_vecino is None or _clave(fila) > _clave(mejor_vecino):
                mejor_vecino = fila
        if mejor_vecino is None or _clave(mejor_vecino) <= _clave(actual):
            break
        actual = mejor_vecino
        if motivo == "presupuesto agotado":
            break
    historia = sorted(vistos.values(), key=lambda f: f["n"])
    return {"mejor": actual, "motivo_fin": motivo, "evaluados": len(historia), "frontera": frontera(historia),
            "historia": historia}


def _sha_archivo(ruta: Path) -> str | None:
    return hashlib.sha256(ruta.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if ruta.exists() else None


def _git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def metadatos(config: dict, normas: list[str], lam: float, particion: dict) -> dict:
    # En Modal no viaja .git: el commit lo pasa modal_app.py por variable de entorno.
    commit = os.environ.get("ADMISION_COMMIT") or _git("rev-parse", "HEAD")
    sucio = (os.environ["ADMISION_CAMBIOS_SIN_COMMIT"] == "1" if "ADMISION_CAMBIOS_SIN_COMMIT" in os.environ
             else bool(_git("status", "--porcelain")))
    return {"commit": commit, "cambios_sin_commit": sucio,
            "uv_lock_sha256": _sha_archivo(RAIZ / "uv.lock"), "modelo": config["modelo"], "agente": config["agente"],
            "buscador": config["buscador"], "normas": normas, "lambda": lam, "decodificacion": "greedy",
            "particion": {"nombre": "optimizacion", "semilla": particion["semilla"],
                          "casos_sha256": particion["casos_sha256"], "ids": particion["optimizacion"]}}


class Evaluador:
    """Juega y puntúa un prompt con el modelo cargado una sola vez. Escribe las trazas en `carpeta/<sha12>/<norma>/`."""

    def __init__(self, modelo, config: dict, ids: list[str], normas: list[str], carpeta: Path):
        import entrega

        self.modelo, self.config, self.normas, self.carpeta = modelo, config, normas, carpeta
        self.construir_buscador = entrega.construir_buscador
        todos = cargar_casos(RAIZ / "practica" / "casos.jsonl")
        self.casos = [c for c in todos if c.id in set(ids)]
        if len(self.casos) != len(ids):
            raise ValueError("la partición nombra casos que no están en practica/casos.jsonl")

    def __call__(self, texto: str, sha: str) -> dict:
        destino = self.carpeta / sha[:12]
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "prompt.txt").write_text(texto, encoding="utf-8", newline="\n")
        cfg = self.config["agente"]
        entrega = SimpleNamespace(construir_buscador=self.construir_buscador,
                                  construir_agente=lambda: Agente(self.modelo, texto, **cfg))
        por_norma, errores = {}, []
        for norma in self.normas:
            _, resumen = correr(entrega, self.casos, RAIZ / "practica" / f"esperadas-{norma}.jsonl",
                                RAIZ / "normas" / norma, destino / norma)
            por_norma[norma] = {k: resumen.get(k) for k in ("resueltos", "parcial_medio", "sin_decision",
                                                            "caracteres_de_contexto_por_caso")}
            if resumen.get("error"):
                errores.append(f"{norma}: {resumen['error']}")
        episodios = len(self.casos) * len(self.normas)
        return {"episodios": episodios, "resueltos": sum(r["resueltos"] for r in por_norma.values()),
                "parcial_medio": round(sum(r["parcial_medio"] * len(self.casos) for r in por_norma.values())
                                       / episodios, 3),
                "por_norma": por_norma, "error": "; ".join(errores) or None}


def main(argv=None) -> None:
    from agente.modelo import construir_modelo

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nombre", required=True, help="carpeta de la corrida en corridas/prompt/")
    ap.add_argument("--normas", nargs="+", default=["original", "b", "c"], choices=["original", "b", "c"])
    ap.add_argument("--lambda", dest="lam", type=float, default=0.05)
    ap.add_argument("--max-evaluaciones", type=int, default=24)
    ap.add_argument("--limite-casos", type=int, default=None, help="sólo para ensayos: los primeros N casos")
    a = ap.parse_args(argv)

    carpeta = RAIZ / "corridas" / "prompt" / a.nombre
    if (carpeta / "candidatos.jsonl").exists():
        ap.error(f"ya existe {carpeta}: las corridas no se pisan, usen otro --nombre")
    carpeta.mkdir(parents=True)
    config, particion = cargar_config(), cargar_particion()
    ids = particion["optimizacion"][:a.limite_casos] if a.limite_casos else particion["optimizacion"]
    assert not set(ids) & set(particion["validacion"]), "la validación no se usa para optimizar"
    meta = {**metadatos(config, a.normas, a.lam, particion), "limite_casos": a.limite_casos,
            "max_evaluaciones": a.max_evaluaciones}
    (carpeta / "corrida.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    modelo = construir_modelo(config["modelo"])
    contar = ((lambda t: modelo.contar_tokens([{"role": "system", "content": t}]))
              if hasattr(modelo, "contar_tokens") else tokens_aproximados)
    evaluar = Evaluador(modelo, config, ids, a.normas, carpeta)

    def registrar(fila):
        with open(carpeta / "candidatos.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"[{fila['n']}] {fila['mutacion']}: {fila['resueltos']}/{fila['episodios']} resueltos, "
              f"{fila['tokens']} tokens, puntaje {fila['puntaje']}", flush=True)

    resultado = buscar(evaluar, contar, a.lam, a.max_evaluaciones, registrar)
    resumen = {k: v for k, v in resultado.items() if k != "historia"}
    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mejor": resumen["mejor"]["sha256"] if resumen["mejor"] else None,
                      "motivo_fin": resumen["motivo_fin"], "evaluados": resumen["evaluados"]}, indent=2))


if __name__ == "__main__":
    main()
