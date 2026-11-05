"""Genera las tablas del informe desde lo que está en `corridas/` (nunca a mano) y las escribe en INFORME.md, entre los
marcadores `<!-- tabla:<nombre> -->` y `<!-- /tabla:<nombre> -->`. Lo que no se corrió figura como pendiente.

    python -m evaluacion.tablas            # reescribe las tablas de INFORME.md
    python -m evaluacion.tablas --mostrar  # sólo las imprime

Tablas:
- `semillas`: largo de los prompts de partida del optimizador (sale del código, no necesita GPU);
- `prompt`: antes/después de optimizar, en la partición de validación (`optimizacion.comparar`);
- `matriz`: 4 condiciones × 3 normas con la referencia de la cátedra (`evaluacion.matriz`);
- `controles`: acierto por control en cada condición y norma, para ver qué control falla;
- `regresiones`: casos que resuelve la base y no otra condición, por norma;
- `trazabilidad`: de qué comando, commit, checkpoint y prompt sale cada corrida citada."""

import argparse
import json
import re
from pathlib import Path

from admision.comparar import CONTROLES
from agente.prompts import tokens_aproximados
from evaluacion.evaluar import NORMAS, resumen_de
from evaluacion.matriz import cargar_matriz, etiqueta
from evaluacion.matriz import tabla as tabla_matriz
from optimizacion.bloques import SEMILLAS, armar
from optimizacion.comparar import tabla as tabla_prompt

RAIZ = Path(__file__).resolve().parent.parent
INFORME = RAIZ / "INFORME.md"


def _md(filas: list[list[str]]) -> str:
    return "\n".join("| " + " | ".join(f) + " |" for f in [filas[0], ["---"] * len(filas[0]), *filas[1:]])


def _corridas() -> list[str]:
    carpeta = RAIZ / "corridas" / "eval"
    return sorted(p.name for p in carpeta.iterdir() if (p / "condicion.json").exists()) if carpeta.exists() else []


def tabla_semillas() -> str:
    filas = [["Semilla", "Caracteres", "Tokens (aprox., 4 caracteres por token)"]]
    for nombre, bloques in SEMILLAS.items():
        texto = armar(bloques)
        filas.append([nombre, str(len(texto)), str(tokens_aproximados(texto))])
    return _md(filas)


def tabla_controles(matriz: dict) -> str:
    filas = [["Condición", "Normas", *CONTROLES]]
    for c in matriz["condiciones"]:
        for n, r in resumen_de(etiqueta(c)).items():
            if r:
                filas.append([c["nombre"], n, *[f"{r['por_control'][k]:.2f}" for k in CONTROLES]])
    return _md(filas) if len(filas) > 1 else "Pendiente de correr: no hay corridas de la matriz todavía."


def _resueltos(etiqueta_: str, norma: str) -> set[str] | None:
    ruta = RAIZ / "corridas" / "eval" / etiqueta_ / norma / "resultados.jsonl"
    if not ruta.exists():
        return None
    return {r["caso"] for r in map(json.loads, ruta.read_text(encoding="utf-8").splitlines()) if r["resuelto"]}


def tabla_regresiones(matriz: dict) -> str:
    base, otras = matriz["condiciones"][0], matriz["condiciones"][1:]
    filas = [["Condición", "Normas", "Resuelve la base y no esta", "Resuelve esta y no la base"]]
    for c in otras:
        for n in NORMAS:
            a, b = _resueltos(etiqueta(base), n), _resueltos(etiqueta(c), n)
            if a is not None and b is not None:
                filas.append([c["nombre"], n, ", ".join(sorted(a - b)) or "ninguno", ", ".join(sorted(b - a)) or "ninguno"])
    return _md(filas) if len(filas) > 1 else "Pendiente de correr: hacen falta la base y al menos otra condición."


def tabla_trazabilidad() -> str:
    filas = [["Corrida", "Casos", "Prompt (versión · sha256)", "Modelo · revisión", "Commit", "Comando"]]
    for e in _corridas():
        c = json.loads((RAIZ / "corridas" / "eval" / e / "condicion.json").read_text(encoding="utf-8"))
        args = " ".join(f"{k}={v}" for k, v in c["variables"].items())
        filas.append([f"`{e}`", c["casos"], f"{c['prompt']['version']} · `{c['prompt']['sha256'][:12]}`",
                      f"{c['modelo']['repo']} · `{str(c['modelo']['revision'])[:12]}`", f"`{(c['commit'] or '?')[:7]}`"
                      + (" (con cambios sin commit)" if c["cambios_sin_commit"] else ""),
                      f"`{args} python -m evaluacion.evaluar --etiqueta {e} --casos {c['casos']}`"])
    return _md(filas) if len(filas) > 1 else "Todavía no hay corridas de evaluación en `corridas/eval/`."


def generar() -> dict[str, str]:
    matriz = cargar_matriz()
    return {"semillas": tabla_semillas(), "prompt": tabla_prompt("prompt-antes", "prompt-despues"),
            "matriz": tabla_matriz(matriz), "controles": tabla_controles(matriz),
            "regresiones": tabla_regresiones(matriz), "trazabilidad": tabla_trazabilidad()}


def escribir(texto: str, tablas: dict[str, str]) -> str:
    for nombre, contenido in tablas.items():
        patron = re.compile(rf"(<!-- tabla:{nombre} -->).*?(<!-- /tabla:{nombre} -->)", re.S)
        if not patron.search(texto):
            raise KeyError(f"INFORME.md no tiene los marcadores de la tabla {nombre!r}")
        texto = patron.sub(lambda m: f"{m.group(1)}\n{contenido}\n{m.group(2)}", texto)
    return texto


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mostrar", action="store_true")
    a = ap.parse_args(argv)
    tablas = generar()
    if a.mostrar:
        print("\n\n".join(f"## {k}\n\n{v}" for k, v in tablas.items()))
        return
    INFORME.write_text(escribir(INFORME.read_text(encoding="utf-8"), tablas), encoding="utf-8", newline="\n")
    print(f"tablas actualizadas en {INFORME.name}: {', '.join(tablas)}")


if __name__ == "__main__":
    main()
