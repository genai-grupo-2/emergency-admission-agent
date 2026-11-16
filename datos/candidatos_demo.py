"""Lista los casos de práctica que sirven para la demo, mirando sólo la nota de triage (`practica/casos.jsonl`).

La demo pide un caso con circuito tiempo-dependiente y otro que se decida por una costumbre, sobre normas `b` o `c`.
Acá se eligen candidatos por las características del caso, sin leer las respuestas esperadas ni corridas de ningún
modelo: cuál se muestra se decide después, con la corrida del modelo final.

    uv run --locked python -X utf8 -m datos.candidatos_demo
"""

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MOTIVOS_TIEMPO_DEPENDIENTES = {
    "dolor torácico": "ecg",
    "signos neurológicos focales de inicio súbito": "codigo_acv",
}
# Umbral de la costumbre del voluntariado inferido del historial (costumbres.md); no es un parámetro de las normas.
EDAD_VOLUNTARIADO = 75


def circuito_probable(caso: dict) -> str | None:
    if caso["sepsis"] != "no":
        return "codigo_sepsis"
    return MOTIVOS_TIEMPO_DEPENDIENTES.get(caso["motivo"])


def doble_credencial(caso: dict) -> bool:
    tipos = {credencial[0] for credencial in caso["credenciales"]}
    return {"obra_social", "prepaga"} <= tipos and caso["trabajo"] is None


def voluntariado(caso: dict) -> bool:
    return caso["edad"] >= EDAD_VOLUNTARIADO and caso["acompanante"] is None


def resumir(caso: dict) -> dict:
    return {
        "id": caso["id"],
        "edad": caso["edad"],
        "nivel": caso["nivel"],
        "motivo": caso["motivo"],
        "llegada": caso["llegada"],
        "acompanante": caso["acompanante"],
        "credenciales": [credencial[0] for credencial in caso["credenciales"]],
        "circuito_probable": circuito_probable(caso),
        "costumbre_voluntariado": voluntariado(caso),
        "costumbre_doble_credencial": doble_credencial(caso),
    }


def candidatos(casos: list[dict]) -> dict:
    resumidos = [resumir(caso) for caso in casos]
    con_circuito = [r for r in resumidos if r["circuito_probable"]]
    con_costumbre = [r for r in resumidos if r["costumbre_voluntariado"] or r["costumbre_doble_credencial"]]
    return {
        "criterio": {
            "fuente": "practica/casos.jsonl; no se leen respuestas esperadas ni corridas de modelos",
            "tiempo_dependiente": "dolor torácico, signos neurológicos focales de inicio súbito o sospecha de sepsis",
            "ambulancia": "llegada en ambulancia: permite mostrar la reducción del plazo",
            "costumbre_voluntariado": f"edad de al menos {EDAD_VOLUNTARIADO} años y sin acompañante",
            "costumbre_doble_credencial": "obra social y prepaga presentadas, sin accidente laboral",
        },
        "casos_revisados": len(resumidos),
        # Primero los que llegan en ambulancia; después por ID.
        "tiempo_dependiente": sorted(con_circuito, key=lambda r: (r["llegada"] != "en ambulancia", r["id"])),
        # Primero los que no activan circuito: ahí la costumbre es lo que decide el caso.
        "costumbre": sorted(con_costumbre, key=lambda r: (r["circuito_probable"] is not None, r["id"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--casos", type=Path, default=RAIZ / "practica" / "casos.jsonl")
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos" / "candidatos_demo.json")
    args = parser.parse_args()
    with args.casos.open(encoding="utf-8") as archivo:
        casos = [json.loads(linea) for linea in archivo if linea.strip()]
    resultado = candidatos(casos)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"{len(resultado['tiempo_dependiente'])} candidatos tiempo-dependientes y "
        f"{len(resultado['costumbre'])} por costumbre en {args.salida}"
    )


if __name__ == "__main__":
    main()
