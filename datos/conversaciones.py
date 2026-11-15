"""Convierte trazas al protocolo de chat del kit, sin corregir ni inventar pasos."""

import hashlib
import json
import re

from admision.ejemplo import primer_mensaje
from datos.inspeccionar import ARGUMENTOS, FICHA


def convertir_traza(traza: dict, sistema: str) -> list[dict]:
    if not isinstance(sistema, str) or not sistema.strip():
        raise ValueError("El mensaje de sistema no puede estar vacío.")
    pasos = traza["pasos"]
    nombres = [p["herramienta"] for p in pasos]
    if not pasos or nombres[0] != "leer_triage" or nombres[-1] != "registrar_decision" or nombres.count("registrar_decision") != 1:
        raise ValueError(f"{traza['id']}: la traza debe empezar leyendo triage y cerrar una sola vez al final")
    if len(pasos) > 40:
        raise ValueError(f"{traza['id']}: supera el límite de herramientas")
    mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": primer_mensaje(traza["paciente_id"])}]
    for orden, paso in enumerate(pasos, 1):
        nombre = paso["herramienta"]
        if nombre not in ARGUMENTOS or type(paso["orden"]) is not int or paso["orden"] != orden:
            raise ValueError(f"{traza['id']}: herramienta u orden inválido")
        if not isinstance(paso["argumentos"], dict) or not isinstance(paso["resultado"], str):
            raise ValueError(f"{traza['id']}: argumentos o resultado inválido")
        llamada = {"herramienta": nombre, "argumentos": paso["argumentos"]}
        mensajes.append({"role": "assistant", "content": json.dumps(llamada, ensure_ascii=False)})
        if nombre != "registrar_decision":
            mensajes.append({"role": "user", "content": f"Resultado de {nombre}:\n{paso['resultado']}"})
        else:
            final = {c: paso["argumentos"][c] for c in FICHA}
            if json.dumps(final, sort_keys=True) != json.dumps(traza["ficha"], sort_keys=True):
                raise ValueError(f"{traza['id']}: la decisión no coincide con la ficha")
    return mensajes


def huella_conversacion(mensajes: list[dict], paciente_id: str) -> str:
    """Agrupa copias que sólo cambian ID/nombre; conserva documentos y números normativos."""
    anonimos = []
    for mensaje in mensajes[1:]:
        contenido = mensaje["content"].replace(paciente_id, "<PACIENTE>")
        contenido = re.sub(r"(?m)^Paciente: .+?(?=, \d+ años\.)", "Paciente: <NOMBRE>", contenido)
        anonimos.append({"role": mensaje["role"], "content": contenido})
    serializado = json.dumps(anonimos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def preparar_registro(traza: dict, fuente: str, sistema: str) -> dict:
    if fuente not in {"historial", "entrenamiento"}:
        raise ValueError("Fuente desconocida")
    mensajes = convertir_traza(traza, sistema)
    original = json.dumps(traza, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": f"{fuente}:{traza['id']}", "fuente": fuente, "id_origen": traza["id"],
        "paciente_id": traza["paciente_id"],
        "traza_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "huella_conversacion": huella_conversacion(mensajes, traza["paciente_id"]),
        "messages": mensajes,
    }
