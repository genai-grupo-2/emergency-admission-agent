"""El espacio de búsqueda del prompt: el mensaje de sistema se arma con bloques, en un orden fijo, y cada bloque tiene
variantes (o se omite). Un candidato es una elección de variante por bloque.

El candidato `catedra` reproduce byte por byte el mensaje de sistema del ejemplo de la cátedra (la línea de base).
Ningún bloque trae números de las normas: en el test cambian, así que el agente los tiene que buscar."""

from admision.ejemplo import mensaje_de_sistema

_IDENTIDAD, _HERRAMIENTAS, _FORMATO, _NORMAS = mensaje_de_sistema().split("\n\n")

BLOQUES: dict[str, dict[str, str]] = {
    "identidad": {
        "catedra": _IDENTIDAD,
        "corta": "Sos el agente de admisión de la guardia del Hospital General de Prueba: completás la ficha de "
                 "admisión de cada paciente según las normas del hospital. No tomás decisiones clínicas.",
    },
    "procedimiento": {
        "pasos": "Cómo trabajar:\n"
                 "1. Leé el triage.\n"
                 "2. Averiguá la cobertura: credenciales del triage o, si no hay, preguntá al paciente (o al "
                 "acompañante si el paciente no puede responder). Si se lesionó trabajando o en el trayecto, "
                 "preguntá por la ART.\n"
                 "3. Verificá la afiliación con la entidad y el número que correspondan según las normas.\n"
                 "4. Buscá en las normas lo que decide cada campo y registrá la ficha.",
    },
    "herramientas": {
        "catedra": _HERRAMIENTAS,
        "compacta": "Herramientas (argumentos):\n"
                    "- leer_triage(paciente_id)\n"
                    "- preguntar(paciente_id, a_quien: paciente|acompanante, tema: cobertura|art)\n"
                    "- verificar_afiliacion(entidad, numero_afiliado; en una ART, el CUIL)\n"
                    "- buscar_normativa(consulta): devuelve las secciones de las normas más relevantes\n"
                    "- registrar_decision(registro: definitivo|provisorio, numero_documento: tal como figura o "
                    "null, box_antes_del_registro: bool, circuito: ecg|codigo_acv|codigo_sepsis|ninguno, "
                    "plazo_circuito_min: minutos desde el ingreso o null, cobertura: "
                    "obra_social|prepaga|art|sin_cobertura, entidad_a_notificar: nombre o null, "
                    "aviso_al_voluntariado: bool, fundamentos: [códigos de sección]); termina el caso",
    },
    "formato": {
        "catedra": _FORMATO,
        "corto": 'Respondé cada turno sólo con un JSON: {"herramienta": "<nombre>", "argumentos": {...}}. '
                 "Una herramienta por turno; registrar_decision termina el caso.",
    },
    "normas": {
        "catedra": _NORMAS,
        "consultas": "Las normas que deciden la ficha son NOR-ADM (registro), NOR-COB (coberturas) y NOR-TDE "
                     "(circuitos tiempo-dependientes); hay secciones de otras áreas que no aplican. Los plazos, "
                     "edades y niveles cambian: tomalos siempre de lo que devuelve buscar_normativa, nunca de memoria.",
    },
    "costumbres": {
        "historial": "Costumbres del hospital, no escritas en las normas: si el paciente tiene 75 años o más y "
                     "llegó sin acompañante, se avisa al voluntariado; si presentó una credencial de obra social y "
                     "otra de prepaga, se verifica la prepaga.",
    },
}
ORDEN = list(BLOQUES)
OMITIR = "-"  # variante que deja el bloque afuera

SEMILLAS: dict[str, dict[str, str]] = {
    "catedra": {"identidad": "catedra", "procedimiento": OMITIR, "herramientas": "catedra", "formato": "catedra",
                "normas": "catedra", "costumbres": OMITIR},
    "catedra+costumbres": {"identidad": "catedra", "procedimiento": OMITIR, "herramientas": "catedra",
                           "formato": "catedra", "normas": "catedra", "costumbres": "historial"},
    "compacto": {"identidad": "corta", "procedimiento": "pasos", "herramientas": "compacta", "formato": "corto",
                 "normas": "consultas", "costumbres": "historial"},
}


def variantes(bloque: str) -> list[str]:
    return [*BLOQUES[bloque], OMITIR]


def armar(candidato: dict[str, str]) -> str:
    faltan = [b for b in ORDEN if b not in candidato]
    if faltan:
        raise KeyError(f"al candidato le faltan bloques: {faltan}")
    for bloque in ("herramientas", "formato"):  # sin esto el modelo no sabe el protocolo
        if candidato[bloque] == OMITIR:
            raise ValueError(f"el bloque {bloque!r} no se puede omitir")
    return "\n\n".join(BLOQUES[b][candidato[b]] for b in ORDEN if candidato[b] != OMITIR)


def vecinos(candidato: dict[str, str]) -> list[tuple[str, dict[str, str]]]:
    """Los candidatos que cambian un solo bloque, con la mutación que los produce, en orden determinista."""
    salida = []
    for bloque in ORDEN:
        for v in variantes(bloque):
            if v != candidato[bloque] and not (bloque in ("herramientas", "formato") and v == OMITIR):
                salida.append((f"{bloque}={v}", {**candidato, bloque: v}))
    return salida
