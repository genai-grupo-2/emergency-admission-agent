"""Comprobaciones de normas escritas para las admisiones estáticas del historial.

Estas funciones preparan datos offline. No son el agente ni un buscador RAG.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Afiliacion:
    entidad: str
    tipo: str
    numero: str


def cargar_parametros(ruta_normas: Path) -> dict:
    contenido = yaml.safe_load((ruta_normas / "parametros.yaml").read_text(encoding="utf-8"))
    return {p["codigo"]: p["valor"] for p in contenido["parametros"]}


def opciones_cobertura(fila: dict) -> list[Afiliacion]:
    """La credencial reemplaza la consulta; ninguna prioridad entre entidades se inventa aquí."""
    texto = fila["credenciales"] or fila["cobertura_declarada"]
    if not texto or texto == "ninguna":
        return []
    opciones = []
    for parte in texto.split("; "):
        coincidencia = re.fullmatch(r"(.+) \((obra social|prepaga)\) (.+)", parte)
        if not coincidencia:
            raise ValueError(f"{fila['id']}: cobertura no reconocida: {parte}")
        entidad, tipo, numero = coincidencia.groups()
        opciones.append(Afiliacion(entidad, tipo.replace(" ", "_"), numero))
    return opciones


def art_declarada(fila: dict) -> Afiliacion:
    coincidencia = re.fullmatch(r"(.+) CUIL (.+)", fila["art_declarada"])
    if not coincidencia:
        raise ValueError(f"{fila['id']}: ART no reconocida")
    return Afiliacion(coincidencia[1], "art", coincidencia[2])


def comprobar_normas(fila: dict, traza: dict, parametros: dict) -> list[dict]:
    """Registra violaciones con evidencia, sin aplicar costumbres.

    El CSV y las trazas describen una admisión sin eventos posteriores de retriage
    o llegada de documentos. No se infieren tiempos de atención que no estén registrados.
    """
    errores = []
    ficha = traza["ficha"]

    def comparar(campo, esperado, norma):
        if type(ficha[campo]) is not type(esperado) or ficha[campo] != esperado:
            errores.append({"norma": norma, "campo": campo, "esperado": esperado, "observado": ficha[campo]})

    def procedimiento(campo, esperado, observado, norma):
        errores.append({"norma": norma, "campo": campo, "esperado": esperado, "observado": observado})

    edad, nivel = int(fila["edad"]), int(fila["nivel"])
    extranjero_urgente = fila["documento_tipo"] in {"pasaporte", "cédula"} and nivel <= parametros["P-ADM-3"]
    registro = "definitivo" if fila["documento_tipo"] and not extranjero_urgente else "provisorio"
    comparar("registro", registro, "NOR-ADM-03 §1-3" if extranjero_urgente else "NOR-ADM-01 §2-3")
    comparar("numero_documento", fila["documento_numero"] or None, "NOR-ADM-03 §1" if extranjero_urgente else "NOR-ADM-01 §2-3")
    if edad >= parametros["P-ADM-2"]:
        comparar("box_antes_del_registro", True, "NOR-ADM-02 §1-2")
    elif nivel <= parametros["P-ADM-1"]:
        comparar("box_antes_del_registro", True, "NOR-ADM-01 §4")
    # En los demás casos la norma permite registrar mientras espera; no prohíbe box primero.

    motivo, sospecha = fila["motivo"], fila["sospecha_sepsis"]
    disparadores = [motivo == "dolor torácico", motivo == "signos neurológicos focales de inicio súbito", sospecha != "no"]
    if sum(disparadores) > 1:
        raise ValueError(f"{fila['id']}: hay circuitos simultáneos; requiere revisión, no una precedencia inventada")
    circuito, plazo, norma = "ninguno", None, "NOR-TDE-01 §3; NOR-TDE-02 §3; NOR-TDE-03 §3"
    if disparadores[0]:
        circuito, plazo, norma = "ecg", parametros["P-TDE-1"], "NOR-TDE-01 §1"
    elif disparadores[1]:
        circuito, plazo, norma = "codigo_acv", parametros["P-TDE-2"], "NOR-TDE-02 §1"
    elif disparadores[2]:
        if sospecha not in {"probable", "con signos de shock", "posible, sin signos de shock"}:
            raise ValueError(f"{fila['id']}: categoría de sepsis desconocida")
        codigo = "P-TDE-4" if sospecha == "posible, sin signos de shock" else "P-TDE-3"
        circuito, plazo, norma = "codigo_sepsis", parametros[codigo], "NOR-TDE-03 §1"
    comparar("circuito", circuito, norma)
    if plazo is not None and fila["llegada"] == "en ambulancia":
        plazo -= parametros["P-TDE-5"]
        norma += "; NOR-TDE-04 §1-3"
    comparar("plazo_circuito_min", plazo, norma)

    laboral = fila["lesion_trabajo"] != "no"
    opciones = [art_declarada(fila)] if laboral else opciones_cobertura(fila)
    elegida = next((o for o in opciones if o.entidad == fila["entidad_verificada"] and o.numero == fila["numero_verificado"]), None)
    verificaciones = [p for p in traza["pasos"] if p["herramienta"] == "verificar_afiliacion"]
    norma_cobertura = "NOR-COB-02 §5" if laboral else "NOR-COB-02 §2"
    if opciones and elegida is None:
        procedimiento("verificacion", [{"entidad": o.entidad, "numero": o.numero} for o in opciones],
                      {"entidad": fila["entidad_verificada"], "numero": fila["numero_verificado"]}, norma_cobertura)
    for paso in verificaciones:
        argumentos = paso["argumentos"]
        if not any(o.entidad == argumentos["entidad"] and o.numero == argumentos["numero_afiliado"] for o in opciones):
            procedimiento("verificacion", "Una afiliación informada y permitida", argumentos, norma_cobertura)
    if elegida and not any(p["argumentos"] == {"entidad": elegida.entidad, "numero_afiliado": elegida.numero} for p in verificaciones):
        procedimiento("verificacion", {"entidad": elegida.entidad, "numero_afiliado": elegida.numero}, "No se verificó", norma_cobertura)
    if not opciones and (fila["entidad_verificada"] or verificaciones):
        procedimiento("verificacion", "Sin afiliación informada para verificar", fila["entidad_verificada"], "NOR-COB-01 §1-4")

    if laboral:
        comparar("cobertura", "art", "NOR-COB-02 §5; NOR-COB-03 §1")
        comparar("entidad_a_notificar", opciones[0].entidad, "NOR-COB-02 §5")
    elif elegida:
        reservada = elegida.numero.endswith(str(parametros["P-COB-2"]))
        if reservada:
            comparar("cobertura", "sin_cobertura", "NOR-COB-04 §1-4")
            comparar("entidad_a_notificar", elegida.entidad, "NOR-COB-04 §1-3")
        elif fila["respuesta_verificacion"] == "activa":
            comparar("cobertura", elegida.tipo, "NOR-COB-02 §3")
            comparar("entidad_a_notificar", elegida.entidad, "NOR-COB-02 §3")
        elif fila["respuesta_verificacion"] == "inactiva":
            comparar("cobertura", "sin_cobertura", "NOR-COB-03 §1")
            comparar("entidad_a_notificar", None, "NOR-COB-03 §4")
        else:
            raise ValueError(f"{fila['id']}: falta una respuesta de verificación reconocida")
    elif not opciones:
        comparar("cobertura", "sin_cobertura", "NOR-COB-03 §1")
        comparar("entidad_a_notificar", None, "NOR-COB-02 §3; NOR-COB-03 §4")

    interlocutor = "paciente" if fila["puede_responder"] == "sí" else "acompanante" if fila["acompanante"] else None
    temas = (["cobertura"] if not fila["credenciales"] and interlocutor else []) + (["art"] if laboral and interlocutor else [])
    preguntas = [p for p in traza["pasos"] if p["herramienta"] == "preguntar"]
    for tema in temas:
        consultas = [p for p in preguntas if p["argumentos"]["tema"] == tema and p["argumentos"]["a_quien"] == interlocutor]
        antes_de = min((p["orden"] for p in verificaciones), default=10**9)
        if not any(p["orden"] < antes_de for p in consultas):
            procedimiento("preguntar", {"tema": tema, "a_quien": interlocutor, "antes_de_verificar": True},
                          "Consulta ausente o posterior a la verificación", "NOR-COB-01 §1-2,5")
    for pregunta in preguntas:
        if pregunta["argumentos"]["a_quien"] != interlocutor:
            procedimiento("preguntar", interlocutor or "No preguntar sin interlocutor disponible", pregunta["argumentos"], "NOR-COB-01 §2-3")
    return errores
