"""Carga, validación y tokenización de las conversaciones de entrenamiento (`datos/conversaciones/*.jsonl`).

No usa torch: recibe cualquier tokenizador con `apply_chat_template(mensajes, tokenize=False,
add_generation_prompt=...)` y `__call__(texto, add_special_tokens=False)["input_ids"]`, así se prueba sin GPU.

Qué se valida antes de gastar GPU:
- el mensaje de sistema de cada conversación es EXACTAMENTE el prompt de la configuración (el acordado con Juan);
- la forma system, (user, assistant)+, y la última respuesta es `registrar_decision` (sin nada después);
- ningún id, grupo ni huella está en entrenamiento y validación a la vez;
- ninguna conversación reproduce un caso de práctica (el contenido del triage, no sólo el id del paciente: los ids
  `P-xxxx` son al azar y algunos coinciden por casualidad sin ser el mismo paciente).

La pérdida se calcula sólo sobre los mensajes del asistente (herramienta + argumentos, incluido el cierre del turno,
para que aprenda a parar). Qué tokens son del asistente se averigua con la plantilla de chat del propio modelo: el
texto de la conversación hasta el turno `i` con `add_generation_prompt=True` es el prefijo del texto hasta el turno
`i` inclusive; si esa propiedad no se cumple para alguna conversación, se corta en vez de entrenar con una máscara
corrida."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class DatosInvalidos(ValueError):
    pass


def sha256_archivo(ruta) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def leer_conversaciones(ruta) -> list[dict]:
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for n, linea in enumerate(f, 1):
            if linea.strip():
                try:
                    filas.append(json.loads(linea))
                except json.JSONDecodeError as e:
                    raise DatosInvalidos(f"{ruta}:{n}: JSON inválido ({e})") from e
    return filas


def _forma_valida(mensajes: list[dict]) -> str | None:
    if len(mensajes) < 3 or len(mensajes) % 2 == 0:
        return "debe ser system seguido de pares user/assistant"
    if mensajes[0]["role"] != "system":
        return "el primer mensaje no es system"
    for i, m in enumerate(mensajes[1:], 1):
        esperado = "user" if i % 2 == 1 else "assistant"
        if m["role"] != esperado:
            return f"el mensaje {i} es {m['role']} y se esperaba {esperado}"
    try:
        ultimo = json.loads(mensajes[-1]["content"])
    except json.JSONDecodeError:
        return "la última respuesta no es JSON"
    if not isinstance(ultimo, dict) or ultimo.get("herramienta") != "registrar_decision":
        return "la última respuesta no es registrar_decision"
    return None


def validar(entrenamiento: list[dict], validacion: list[dict], prompt: str, casos_practica: list[dict] | None = None):
    """Devuelve un resumen; levanta DatosInvalidos con TODOS los problemas encontrados."""
    problemas = []
    for nombre, filas in (("train", entrenamiento), ("validacion", validacion)):
        if not filas:
            problemas.append(f"{nombre}: no hay conversaciones")
        ids = [f["id"] for f in filas]
        if len(set(ids)) != len(ids):
            problemas.append(f"{nombre}: hay ids repetidos")
        for f in filas:
            mensajes = f["messages"]
            if mensajes and mensajes[0]["content"] != prompt:
                problemas.append(f"{nombre}:{f['id']}: el mensaje de sistema no es el prompt de la configuración")
            motivo = _forma_valida(mensajes)
            if motivo:
                problemas.append(f"{nombre}:{f['id']}: {motivo}")
    for clave in ("id", "grupo", "huella_conversacion"):
        comunes = {f[clave] for f in entrenamiento} & {f[clave] for f in validacion}
        if comunes:
            problemas.append(
                f"{len(comunes)} {clave} en entrenamiento y validación a la vez, por ejemplo {sorted(comunes)[0]}")
    coincidencias_de_id = 0
    if casos_practica:
        por_paciente = {c["paciente_id"]: c for c in casos_practica}
        for nombre, filas in (("train", entrenamiento), ("validacion", validacion)):
            for f in filas:
                caso = por_paciente.get(f["paciente_id"])
                if not caso:
                    continue
                coincidencias_de_id += 1
                triage = f["messages"][3]["content"] if len(f["messages"]) > 3 else ""
                if f"{caso['edad']} años" in triage and caso["motivo"] in triage:
                    problemas.append(f"{nombre}:{f['id']}: reproduce el caso de práctica {caso['id']}")
    if problemas:
        mostrados = "\n  - ".join(problemas[:20])
        resto = f"\n  ... y {len(problemas) - 20} más" if len(problemas) > 20 else ""
        raise DatosInvalidos(f"{len(problemas)} problemas en los datos:\n  - {mostrados}{resto}")
    return {"train": len(entrenamiento), "validacion": len(validacion),
            "ids_de_paciente_que_coinciden_con_practica_sin_ser_el_mismo_caso": coincidencias_de_id}


@dataclass
class Ejemplo:
    id: str
    ids: list[int]
    mascara: list[bool]  # True: el token es del asistente y entra en la pérdida

    @property
    def n_supervisados(self) -> int:
        return sum(self.mascara)


def _plantilla(tokenizador, mensajes, generacion: bool) -> str:
    return tokenizador.apply_chat_template(mensajes, tokenize=False, add_generation_prompt=generacion)


def _ids(tokenizador, texto: str) -> list[int]:
    return list(tokenizador(texto, add_special_tokens=False)["input_ids"])


def tokenizar(tokenizador, fila: dict) -> Ejemplo:
    mensajes = fila["messages"]
    ids = _ids(tokenizador, _plantilla(tokenizador, mensajes, False))
    mascara = [False] * len(ids)
    for i, m in enumerate(mensajes):
        if m["role"] != "assistant":
            continue
        antes = _ids(tokenizador, _plantilla(tokenizador, mensajes[:i], True))
        hasta = _ids(tokenizador, _plantilla(tokenizador, mensajes[: i + 1], False))
        if ids[: len(antes)] != antes or ids[: len(hasta)] != hasta or len(hasta) <= len(antes):
            raise DatosInvalidos(f"{fila['id']}: la plantilla de chat no es prefijo-estable en el turno {i}; "
                                 "la máscara de la pérdida quedaría corrida")
        for k in range(len(antes), len(hasta)):
            mascara[k] = True
    return Ejemplo(fila["id"], ids, mascara)


def construir_ejemplos(tokenizador, filas: list[dict], max_tokens: int):
    """Tokeniza todo y descarta (y cuenta) lo que supera `max_tokens`: nada se trunca en silencio."""
    ejemplos, descartados = [], []
    for fila in filas:
        e = tokenizar(tokenizador, fila)
        (descartados if len(e.ids) > max_tokens else ejemplos).append(e)
    largos = sorted(len(e.ids) for e in ejemplos + descartados)
    estadisticas = {
        "conversaciones": len(filas), "usadas": len(ejemplos), "descartadas_por_largo": [e.id for e in descartados],
        "tokens_totales": sum(largos), "tokens_supervisados": sum(e.n_supervisados for e in ejemplos),
        "tokens_max": largos[-1] if largos else 0, "tokens_mediana": largos[len(largos) // 2] if largos else 0,
    }
    return ejemplos, estadisticas
