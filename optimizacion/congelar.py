"""Congela el prompt elegido por una corrida de optimización: lo copia a `prompts/<version>.txt` con su procedencia en
`prompts/<version>.json`. Es el archivo que se entrega a Cande (conversaciones) y a Juli (entrenamiento).

    python -m optimizacion.congelar --corrida busqueda-01                # el mejor de la corrida
    python -m optimizacion.congelar --corrida busqueda-01 --sha <sha256>  # otro candidato de la corrida

Un prompt congelado no se pisa: para cambiarlo después del entrenamiento hay que congelar otra versión."""

import argparse
import json
from pathlib import Path

from agente.prompts import CARPETA, huella
from optimizacion.bloques import armar

RAIZ = Path(__file__).resolve().parent.parent


def congelar(corrida: Path, version: str, sha: str | None = None) -> dict:
    filas = [json.loads(x) for x in (corrida / "candidatos.jsonl").read_text(encoding="utf-8").splitlines() if x]
    if sha is None:
        resumen = json.loads((corrida / "resumen.json").read_text(encoding="utf-8"))
        if not resumen.get("mejor"):
            raise ValueError(f"la corrida {corrida.name} no tiene un mejor candidato")
        sha = resumen["mejor"]["sha256"]
    fila = next((f for f in filas if f["sha256"] == sha), None)
    if fila is None:
        raise KeyError(f"no hay ningún candidato {sha} en {corrida.name}")
    texto = (corrida / sha[:12] / "prompt.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    if huella(texto) != sha or armar(fila["bloques"]) != texto:
        raise ValueError("el prompt guardado no coincide con su huella o con sus bloques")
    destino = CARPETA / f"{version}.txt"
    if destino.exists():
        raise FileExistsError(f"ya existe {destino.name}: un prompt congelado no se pisa")
    destino.write_text(texto, encoding="utf-8", newline="\n")
    corrida_meta = json.loads((corrida / "corrida.json").read_text(encoding="utf-8"))
    procedencia = {"version": version, "sha256": sha, "corrida": f"corridas/prompt/{corrida.name}",
                   "commit_de_la_corrida": corrida_meta.get("commit"), "bloques": fila["bloques"],
                   "tokens": fila["tokens"], "resueltos_en_optimizacion": fila["resueltos"],
                   "episodios_en_optimizacion": fila["episodios"], "puntaje": fila["puntaje"]}
    (CARPETA / f"{version}.json").write_text(json.dumps(procedencia, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    return procedencia


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corrida", required=True, help="nombre de la carpeta en corridas/prompt/")
    ap.add_argument("--version", default="optimizado")
    ap.add_argument("--sha")
    a = ap.parse_args(argv)
    print(json.dumps(congelar(RAIZ / "corridas" / "prompt" / a.corrida, a.version, a.sha), ensure_ascii=False,
                     indent=2))


if __name__ == "__main__":
    main()
