"""Escribe un Markdown legible por cada caso de la demo, para abrirlo en el Loom: los 9 controles, un recorrido de un
renglón por llamada a herramienta y la conversación completa. Lee la corrida ya hecha; no corre el modelo.

    uv run --locked python -X utf8 -m datos.ver_demo
"""

import argparse
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CASOS = ("pev-011", "pev-050", "pev-015")
_CAMPOS_TRIAGE = ("Documento", "Credencial de cobertura", "Credenciales de cobertura", "Acompañante")


def _por_caso(ruta: Path) -> dict[str, dict]:
    filas = (json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip())
    return {fila["caso"]: fila for fila in filas}


def _triage(texto: str) -> str:
    campos = dict(linea.split(": ", 1) for linea in texto.splitlines() if ": " in linea)
    partes = [campos.get("Paciente", "").rsplit(", ", 1)[-1], campos.get("Motivo de consulta", ""),
              f"llegó {campos.get('Llegada', '')}"]
    partes = [", ".join(p.rstrip(".") for p in partes if p.strip())]
    partes += [f"{campo.lower()}: {campos[campo].rstrip('.')}" for campo in _CAMPOS_TRIAGE if campo in campos]
    return "; ".join(partes)


def paso(llamada: str, respuesta: str | None) -> str:
    """Un renglón del recorrido: qué herramienta llamó el modelo, con qué, y qué le devolvió el entorno."""
    try:
        pedido = json.loads(llamada)
        herramienta, argumentos = pedido["herramienta"], pedido.get("argumentos", {})
    except (json.JSONDecodeError, KeyError, TypeError):
        return "Respuesta sin una llamada a herramienta válida"
    cuerpo = (respuesta or "").strip()
    if cuerpo.startswith("Resultado de"):
        cuerpo = cuerpo.partition("\n")[2].strip()
    primera = cuerpo.splitlines()[0] if cuerpo else ""
    nombre, detalle = f"`{herramienta}`", primera
    if herramienta == "leer_triage":
        detalle = _triage(cuerpo)
    elif herramienta == "buscar_normativa":
        nombre += f" «{argumentos.get('consulta', '')}»"
        detalle = ", ".join(re.findall(r"^## (NOR-[\w-]+)", cuerpo, flags=re.MULTILINE)) or primera
    elif herramienta == "preguntar":
        nombre += f" a {argumentos.get('a_quien', '?')} sobre {argumentos.get('tema', '?')}"
    elif herramienta == "registrar_decision":
        detalle = "ficha registrada (valores en la tabla de arriba)"
    return f"{nombre} → {detalle}" if detalle else nombre


def recorrido(mensajes: list[dict]) -> list[str]:
    pasos = []
    for i, m in enumerate(mensajes):
        if m["role"] != "assistant":
            continue
        siguiente = mensajes[i + 1] if i + 1 < len(mensajes) and mensajes[i + 1]["role"] == "user" else None
        pasos.append(f"{len(pasos) + 1}. {paso(m['content'].strip(), siguiente['content'] if siguiente else None)}")
    return pasos


def mostrar(traza: dict, resultado: dict, titulo: str) -> str:
    salida = [f"# {traza['caso']} · {titulo}", ""]
    controles = resultado["controles"]
    estado = "resuelto" if resultado["resuelto"] else "no resuelto"
    salida += [f"**{sum(controles.values())}/9 controles, {estado}.** "
               f"{resultado['llamadas']} llamadas a herramientas, {resultado['busquedas']} búsquedas.", ""]
    salida += ["| Control | Esperado | Obtenido | |", "| --- | --- | --- | --- |"]
    for control, ok in controles.items():
        esperado = resultado["esperada"].get(control, "—")
        obtenido = resultado["obtenida"].get(control, "—") if resultado["obtenida"] else "—"
        celdas = ["verificar la entidad que corresponde", "ver la conversación"] if control == "verificacion" else [
            f"`{json.dumps(valor, ensure_ascii=False)}`" for valor in (esperado, obtenido)]
        salida.append(f"| {control} | {celdas[0]} | {celdas[1]} | {'ok' if ok else '**MAL**'} |")
    salida += ["", "## Recorrido", ""] + recorrido(traza["mensajes"])
    salida += ["", "## Conversación", ""]
    for i, m in enumerate(traza["mensajes"]):
        if m["role"] == "system":
            continue
        quien = "Modelo" if m["role"] == "assistant" else ("Pedido inicial" if i == 1 else "Entorno")
        salida += [f"**{quien}**", "", "```text", m["content"].strip(), "```", ""]
    return "\n".join(salida)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corrida", type=Path, default=RAIZ / "corridas" / "demo" / "b-sft-catedra-01")
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos" / "demo")
    parser.add_argument("--casos", nargs="+", default=list(CASOS))
    args = parser.parse_args()
    trazas = _por_caso(args.corrida / "trazas.jsonl")
    resultados = _por_caso(args.corrida / "resultados.jsonl")
    args.salida.mkdir(parents=True, exist_ok=True)
    for caso in args.casos:
        texto = mostrar(trazas[caso], resultados[caso], f"normas b · corrida {args.corrida.name}")
        (args.salida / f"{caso}.md").write_text(texto + "\n", encoding="utf-8", newline="\n")
        print(args.salida / f"{caso}.md")


if __name__ == "__main__":
    main()
