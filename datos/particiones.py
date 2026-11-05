"""Particiones estables por grupos, sin pacientes ni conversaciones compartidos."""

import hashlib


def particionar(registros: list[dict], *, semilla=42, fraccion_validacion=0.1) -> dict:
    if not 0 < fraccion_validacion < 1:
        raise ValueError("La fracción de validación debe estar entre 0 y 1, sin incluirlos.")
    ordenados = sorted(registros, key=lambda r: r["id"])
    if len({r["id"] for r in ordenados}) != len(ordenados):
        raise ValueError("Hay IDs de conversación duplicados.")
    padres = list(range(len(ordenados)))

    def raiz(i):
        while padres[i] != i:
            padres[i] = padres[padres[i]]
            i = padres[i]
        return i

    vistos = {}
    for i, registro in enumerate(ordenados):
        for campo in ("paciente_id", "huella_conversacion"):
            clave = (campo, registro[campo])
            if clave in vistos:
                a, b = raiz(i), raiz(vistos[clave])
                padres[max(a, b)] = min(a, b)
            else:
                vistos[clave] = i
    grupos = {}
    for i, registro in enumerate(ordenados):
        grupos.setdefault(raiz(i), []).append(registro)
    salida = {"train": [], "validacion": []}
    for miembros in grupos.values():
        identificador = hashlib.sha256("\n".join(r["id"] for r in miembros).encode("utf-8")).hexdigest()
        sorteo = int(hashlib.sha256(f"{semilla}:{identificador}".encode("utf-8")).hexdigest(), 16) / 2**256
        particion = "validacion" if sorteo < fraccion_validacion else "train"
        salida[particion].extend({**r, "grupo": identificador} for r in miembros)
    for registros_particion in salida.values():
        registros_particion.sort(key=lambda r: r["id"])
    for campo in ("id", "paciente_id", "huella_conversacion", "grupo"):
        if {r[campo] for r in salida["train"]} & {r[campo] for r in salida["validacion"]}:
            raise AssertionError(f"Filtración entre particiones: {campo}")
    return salida
