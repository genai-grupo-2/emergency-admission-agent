"""Inferencia explícita de dos patrones del historial, con evidencia auditable."""

from datos.normas import opciones_cobertura


def inferir_costumbres(filas: list[dict]) -> dict:
    """Usar sólo filas sin violaciones escritas. No usa las trazas de referencia."""
    if len(filas) < 20:
        raise ValueError("Hay muy pocas filas para inferir costumbres con evidencia.")
    candidatos = []
    for umbral in range(min(int(f["edad"]) for f in filas), max(int(f["edad"]) for f in filas) + 2):
        aciertos = sum((f["aviso_al_voluntariado"] == "sí") == (int(f["edad"]) >= umbral and not f["acompanante"]) for f in filas)
        candidatos.append({"edad_minima": umbral, "coincidencias": aciertos})
    candidatos.sort(key=lambda c: (-c["coincidencias"], c["edad_minima"]))
    mejor = candidatos[0]
    if candidatos[1]["coincidencias"] == mejor["coincidencias"]:
        raise ValueError("El umbral de voluntariado es ambiguo; revisar las edades y la evidencia.")
    voluntariado = {"edad_minima": mejor["edad_minima"], "sin_acompanante": True, "grupos": {}}
    for activar in (True, False):
        grupo = [f for f in filas if (int(f["edad"]) >= mejor["edad_minima"] and not f["acompanante"]) == activar]
        apoyo = [f["id"] for f in grupo if (f["aviso_al_voluntariado"] == "sí") == activar]
        contra = [f["id"] for f in grupo if (f["aviso_al_voluntariado"] == "sí") != activar]
        if len(grupo) < 20 or len(apoyo) / len(grupo) < 0.8:
            raise ValueError("El patrón de voluntariado no alcanza apoyo suficiente en ambos grupos.")
        voluntariado["grupos"]["activar" if activar else "no_activar"] = {"apoyo": apoyo, "contraejemplos": contra}
    voluntariado["candidatos"] = candidatos
    voluntariado["sin_avisar_nunca_coincidencias"] = sum(f["aviso_al_voluntariado"] == "no" for f in filas)

    doble = []
    for fila in filas:
        opciones = opciones_cobertura(fila)
        if fila["lesion_trabajo"] == "no" and len(opciones) == 2 and {o.tipo for o in opciones} == {"obra_social", "prepaga"}:
            elegida = next(o for o in opciones if o.entidad == fila["entidad_verificada"])
            doble.append((fila["id"], elegida.tipo))
    apoyo = [identificador for identificador, tipo in doble if tipo == "prepaga"]
    contra = [identificador for identificador, tipo in doble if tipo != "prepaga"]
    if len(doble) < 20 or len(apoyo) / len(doble) < 0.8:
        raise ValueError("No hay apoyo suficiente para preferir prepaga ante doble credencial.")
    return {
        "version": 1,
        "metodo": "Exploración del historial sin violaciones escritas; patrones inferidos, no etiquetas provistas por la cátedra.",
        "minimo_ejemplos_por_grupo": 20,
        "minima_fraccion_apoyo": 0.8,
        "ids_usados": [f["id"] for f in filas],
        "voluntariado": voluntariado,
        "doble_credencial": {"preferencia": "prepaga", "apoyo": apoyo, "contraejemplos": contra},
    }


def desvios_costumbres(fila: dict, costumbres: dict) -> list[dict]:
    desvios = []
    voluntariado = costumbres["voluntariado"]
    esperado = int(fila["edad"]) >= voluntariado["edad_minima"] and not fila["acompanante"]
    observado = fila["aviso_al_voluntariado"] == "sí"
    if esperado != observado:
        desvios.append({"costumbre": "voluntariado", "esperado": esperado, "observado": observado})
    if fila["lesion_trabajo"] == "no":
        opciones = opciones_cobertura(fila)
        if len(opciones) == 2 and {o.tipo for o in opciones} == {"obra_social", "prepaga"}:
            elegida = next(o for o in opciones if o.entidad == fila["entidad_verificada"])
            if elegida.tipo != costumbres["doble_credencial"]["preferencia"]:
                desvios.append({"costumbre": "doble_credencial", "esperado": "prepaga", "observado": elegida.tipo})
    return desvios


def redactar_costumbres(modelo: dict) -> str:
    def evidencia(grupo):
        apoyo, contra = grupo["apoyo"], grupo["contraejemplos"]
        return (f"Coinciden {len(apoyo)} de {len(apoyo) + len(contra)} filas.\n\n"
                f"Ejemplos de apoyo: {', '.join(apoyo[:12]) or '(ninguno)'}.\n\n"
                f"Ejemplos que se apartan: {', '.join(contra[:12]) or '(ninguno)'}.\n\n"
                "Las listas completas están en `datos/evidencia_costumbres.json`.\n")

    v = modelo["voluntariado"]
    return (
        "# Costumbres inferidas del historial\n\n"
        "Generado con `python -X utf8 -m datos.clasificar`. Evidencia completa y búsqueda del umbral en "
        "`datos/evidencia_costumbres.json`. Se consideran sólo las filas que no violan las normas escritas; "
        "una violación escrita siempre se clasifica como `error`, aunque también se aparte de una costumbre.\n\n"
        "Estas son inferencias sobre lo que suelen hacer los operadores. No son normas de la cátedra ni "
        "mediciones de calidad de un modelo. Los contraejemplos se interpretan como ruido únicamente después "
        "de comprobar que no violan una norma. No se usaron respuestas de evaluación.\n\n"
        "## 1. Avisar al voluntariado para pacientes mayores que llegan solos\n\n"
        f"El patrón con más coincidencias es avisar cuando la edad es al menos {v['edad_minima']} años "
        "y el paciente no tiene acompañante. En los demás casos, no avisar. El umbral se obtiene buscando "
        "entre todas las edades observadas y la siguiente; no se copia de un parámetro normativo. "
        "La hipótesis explorada combina edad y ausencia de acompañante. Se exige un mínimo de 20 ejemplos "
        "y 80% de apoyo en cada grupo; si hay empate de umbrales, el proceso pide revisión.\n\n"
        f"El mejor umbral coincide en {v['candidatos'][0]['coincidencias']} de {len(modelo['ids_usados'])} filas, "
        f"frente a {v['sin_avisar_nunca_coincidencias']} si nunca se avisa. "
        f"El segundo umbral candidato es {v['candidatos'][1]['edad_minima']}, "
        f"con {v['candidatos'][1]['coincidencias']} coincidencias.\n\n"
        "### Pacientes en los que el patrón indica avisar\n\n" + evidencia(v["grupos"]["activar"]) + "\n"
        "### Resto de los pacientes\n\n" + evidencia(v["grupos"]["no_activar"]) + "\n"
        "## 2. Preferir la prepaga si se presentan dos credenciales\n\n"
        "Si se presentan una obra social y una prepaga, los operadores suelen verificar la prepaga. "
        "La selección se observa en la entidad verificada; no se deduce del campo final `cobertura`, "
        "que puede ser `sin_cobertura` por una afiliación inactiva o reservada. La regla no se aplica a "
        "accidentes laborales: ahí corresponde la ART por norma escrita. Las normas no establecen "
        "prioridad entre la obra social y la prepaga.\n\n" + evidencia(modelo["doble_credencial"]) + "\n"
        "## Límites y casos que requieren revisión\n\n"
        "El umbral y la preferencia fueron elegidos explorando este historial completo; sus porcentajes "
        "no son una evaluación independiente ni prueban una política universal del hospital. "
        "La evidencia permite auditar la hipótesis y revisarla. No se inventan reglas para escenarios "
        "sin evidencia suficiente. Por ejemplo, box primero es obligatorio por edad o urgencia; "
        "en los demás casos, hacerlo primero no se considera por sí solo una violación. "
        "El CSV no registra minutos de atención ni eventos posteriores de retriage, llegada de documentos "
        "o indicaciones de internación; no se deducen incumplimientos de esos eventos ausentes.\n"
    )
