"""Comprueba la integridad de las fuentes; no clasifica decisiones del operador.

Ejecutar desde la raíz: python -X utf8 -m datos.inspeccionar
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

CSV = "historial/historial.csv"
HISTORIAL = "historial/trazas.jsonl"
REFERENCIA = "entrenamiento/trazas.jsonl"
COLUMNAS = (
    "id", "fecha", "operador", "edad", "nivel", "motivo", "nota_enfermeria",
    "sospecha_sepsis", "llegada", "documento_tipo", "documento_numero",
    "credenciales", "puede_responder", "acompanante", "lesion_trabajo",
    "cobertura_declarada", "art_declarada", "entidad_verificada",
    "numero_verificado", "respuesta_verificacion", "registro", "numero_documento",
    "box_antes_del_registro", "circuito", "plazo_circuito_min", "cobertura",
    "entidad_a_notificar", "aviso_al_voluntariado",
)
OPCIONALES_CSV = {
    "documento_tipo", "documento_numero", "credenciales", "acompanante",
    "cobertura_declarada", "art_declarada", "entidad_verificada",
    "numero_verificado", "respuesta_verificacion", "numero_documento",
    "plazo_circuito_min", "entidad_a_notificar",
}
FICHA = (
    "registro", "numero_documento", "box_antes_del_registro", "circuito",
    "plazo_circuito_min", "cobertura", "entidad_a_notificar", "aviso_al_voluntariado",
)
BOOLEANOS_FICHA = {"box_antes_del_registro", "aviso_al_voluntariado"}
NULABLES_FICHA = {"numero_documento", "entidad_a_notificar", "plazo_circuito_min"}
DOMINIOS_FICHA = {
    "registro": {"definitivo", "provisorio"},
    "circuito": {"ecg", "codigo_acv", "codigo_sepsis", "ninguno"},
    "cobertura": {"obra_social", "prepaga", "art", "sin_cobertura"},
}
ARGUMENTOS = {
    "leer_triage": {"paciente_id"},
    "preguntar": {"paciente_id", "a_quien", "tema"},
    "verificar_afiliacion": {"entidad", "numero_afiliado"},
    "buscar_normativa": {"consulta"},
    "registrar_decision": set(FICHA),
}


def _grupos_repetidos(pares):
    grupos = {}
    for clave, identificador in pares:
        if clave:
            grupos.setdefault(clave, []).append(identificador)
    return {clave: ids for clave, ids in sorted(grupos.items()) if len(ids) > 1}


def _objeto_sin_claves_repetidas(pares):
    objeto = {}
    for clave, valor in pares:
        if clave in objeto:
            raise ValueError(f"Clave JSON repetida: {clave}")
        objeto[clave] = valor
    return objeto


def inspeccionar(raiz: Path, *, n_historial=2000, n_referencia=800) -> dict:
    """Devuelve un informe determinista. Las cantidades permiten fixtures de prueba."""
    informe = {
        "version": 1,
        "alcance": "Integridad y correspondencia de fuentes; no evalúa normas ni costumbres.",
        "cantidades_esperadas": {CSV: n_historial, HISTORIAL: n_historial, REFERENCIA: n_referencia},
        "archivos": {},
        "errores": [],
        "advertencias": [],
    }

    def error(codigo, archivo, detalle, registro=None):
        hallazgo = {"codigo": codigo, "archivo": archivo, "detalle": detalle}
        if registro is not None:
            hallazgo["registro"] = registro
        informe["errores"].append(hallazgo)

    def cargar(nombre):
        try:
            contenido = (raiz / nombre).read_bytes()
        except OSError as exc:
            error("archivo_inaccesible", nombre, type(exc).__name__)
            return None
        informe["archivos"][nombre] = {
            "bytes": len(contenido),
            "sha256": hashlib.sha256(contenido).hexdigest(),
        }
        try:
            return contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            error("codificacion", nombre, "El archivo no es UTF-8 válido.")
            return None

    def revisar_ids(filas, nombre, esperados):
        ids = [fila.get("id") for fila in filas]
        if len(filas) != len(esperados):
            error("cantidad_registros", nombre, {"esperados": len(esperados), "observados": len(filas)})
        repetidos = {k: v for k, v in Counter(x for x in ids if isinstance(x, str)).items() if v > 1}
        if repetidos:
            error("ids_duplicados", nombre, repetidos)
        presentes = {x for x in ids if isinstance(x, str)}
        faltantes, inesperados = sorted(esperados - presentes), sorted(presentes - esperados)
        if faltantes or inesperados:
            error("cobertura_ids", nombre, {"faltantes": faltantes, "inesperados": inesperados})
        informe["archivos"][nombre].update({"registros": len(filas), "ids_unicos": len(presentes)})

    def revisar_ficha(ficha, nombre, posicion):
        if not isinstance(ficha, dict) or set(ficha) != set(FICHA):
            error("esquema_ficha", nombre, "Se esperan exactamente los ocho campos de la ficha.", posicion)
            return
        for campo, valor in ficha.items():
            valido = isinstance(valor, str) and bool(valor.strip())
            if campo in BOOLEANOS_FICHA:
                valido = type(valor) is bool
            elif campo == "plazo_circuito_min":
                valido = type(valor) is int and valor > 0
            elif campo in DOMINIOS_FICHA:
                valido = isinstance(valor, str) and valor in DOMINIOS_FICHA[campo]
            if campo in NULABLES_FICHA and valor is None:
                valido = True
            if not valido:
                error("tipo_ficha", nombre, {"campo": campo, "valor": valor}, posicion)

    texto = cargar(CSV)
    filas_csv = []
    if texto is not None:
        # newline='' preserva campos citados con saltos de línea, como hace un archivo CSV.
        lector = csv.DictReader(io.StringIO(texto, newline=""), strict=True)
        try:
            if lector.fieldnames != list(COLUMNAS):
                error("columnas_csv", CSV, {"esperadas": list(COLUMNAS), "observadas": lector.fieldnames})
            filas_csv = list(lector)
        except csv.Error as exc:
            error("csv_invalido", CSV, str(exc))
        for posicion, fila in enumerate(filas_csv, 1):
            if None in fila or any(valor is None for valor in fila.values()):
                error("ancho_csv", CSV, "La fila tiene columnas de más o de menos.", posicion)
            for campo in COLUMNAS:
                valor = fila.get(campo)
                if campo not in OPCIONALES_CSV and (not isinstance(valor, str) or not valor.strip()):
                    error("campo_requerido", CSV, campo, posicion)
            for campo in ("puede_responder", "box_antes_del_registro", "aviso_al_voluntariado"):
                if fila.get(campo) not in {"sí", "no"}:
                    error("booleano_csv", CSV, campo, posicion)
            for campo, minimo, maximo in (("edad", 0, None), ("nivel", 1, 5), ("plazo_circuito_min", 1, None)):
                valor = fila.get(campo)
                if campo == "plazo_circuito_min" and valor == "":
                    continue
                if not isinstance(valor, str) or not valor.isdecimal() or int(valor) < minimo or (maximo is not None and int(valor) > maximo):
                    error("numero_csv", CSV, campo, posicion)
            for campo, dominio in DOMINIOS_FICHA.items():
                if fila.get(campo) not in dominio:
                    error("dominio_csv", CSV, campo, posicion)
            try:
                datetime.strptime(fila.get("fecha", ""), "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                error("fecha_csv", CSV, "Se espera AAAA-MM-DD HH:MM.", posicion)
        revisar_ids(filas_csv, CSV, {f"H-{i:04d}" for i in range(1, n_historial + 1)})
        informe["archivos"][CSV].update({
            "columnas": lector.fieldnames,
            "vacios_por_columna": {c: sum(f.get(c) == "" for f in filas_csv) for c in COLUMNAS},
            "columnas_con_vacios_permitidos": sorted(OPCIONALES_CSV),
            "filas_repetidas_sin_id_fecha_operador": list(_grupos_repetidos(
                (json.dumps({k: f.get(k) for k in COLUMNAS if k not in {"id", "fecha", "operador"}}, sort_keys=True), f.get("id"))
                for f in filas_csv
            ).values()),
        })

    fuentes_trazas = {}
    for nombre, cantidad, prefijo, ancho in ((HISTORIAL, n_historial, "H", 4), (REFERENCIA, n_referencia, "E", 3)):
        texto = cargar(nombre)
        trazas = []
        fuentes_trazas[nombre] = trazas
        if texto is None:
            continue
        for posicion, linea in enumerate(texto.splitlines(), 1):
            try:
                traza = json.loads(linea, object_pairs_hook=_objeto_sin_claves_repetidas)
            except (ValueError, RecursionError) as exc:
                error("json_invalido", nombre, str(exc), posicion)
                continue
            if not isinstance(traza, dict):
                error("esquema_traza", nombre, "Cada línea debe ser un objeto JSON.", posicion)
                continue
            trazas.append(traza)
            campos = {"id", "paciente_id", "pasos", "ficha"}
            if nombre == HISTORIAL:
                campos |= {"fecha", "operador"}
            if set(traza) != campos:
                error("esquema_traza", nombre, {"esperados": sorted(campos), "observados": sorted(traza)}, posicion)
            for campo in campos - {"pasos", "ficha"}:
                if not isinstance(traza.get(campo), str) or not traza[campo].strip():
                    error("campo_requerido", nombre, campo, posicion)
            revisar_ficha(traza.get("ficha"), nombre, posicion)
            pasos = traza.get("pasos")
            if not isinstance(pasos, list) or not 1 <= len(pasos) <= 40:
                error("cantidad_pasos", nombre, "Se esperan entre 1 y 40 pasos.", posicion)
                continue
            herramientas = []
            for orden, paso in enumerate(pasos, 1):
                if not isinstance(paso, dict) or set(paso) != {"orden", "herramienta", "argumentos", "resultado"}:
                    error("esquema_paso", nombre, {"paso": orden}, posicion)
                    continue
                if type(paso["orden"]) is not int or paso["orden"] != orden:
                    error("orden_pasos", nombre, {"paso": orden, "orden_observado": paso["orden"]}, posicion)
                herramienta, argumentos = paso["herramienta"], paso["argumentos"]
                if not isinstance(herramienta, str) or herramienta not in ARGUMENTOS:
                    error("herramienta_desconocida", nombre, {"paso": orden}, posicion)
                    continue
                herramientas.append(herramienta)
                if not isinstance(paso["resultado"], str):
                    error("tipo_resultado", nombre, {"paso": orden}, posicion)
                if not isinstance(argumentos, dict):
                    error("tipo_argumentos", nombre, {"paso": orden}, posicion)
                    continue
                adicionales = {"fundamentos"} if herramienta == "registrar_decision" else set()
                if not ARGUMENTOS[herramienta] <= set(argumentos) or set(argumentos) - ARGUMENTOS[herramienta] - adicionales:
                    error("campos_argumentos", nombre, {"paso": orden}, posicion)
                if herramienta == "registrar_decision":
                    ficha_argumentos = {c: argumentos[c] for c in FICHA if c in argumentos}
                    revisar_ficha(ficha_argumentos, nombre, posicion)
                    # JSON distingue true de 1, a diferencia de la igualdad de dicts en Python.
                    if json.dumps(ficha_argumentos, sort_keys=True) != json.dumps(traza.get("ficha"), sort_keys=True):
                        error("registro_difiere_ficha", nombre, {"paso": orden}, posicion)
                    if "fundamentos" in argumentos and (not isinstance(argumentos["fundamentos"], list) or not all(isinstance(x, str) for x in argumentos["fundamentos"])):
                        error("tipo_fundamentos", nombre, {"paso": orden}, posicion)
                else:
                    for campo, valor in argumentos.items():
                        if not isinstance(valor, str) or not valor.strip():
                            error("tipo_argumento", nombre, {"paso": orden, "campo": campo}, posicion)
                    if "paciente_id" in argumentos and argumentos["paciente_id"] != traza.get("paciente_id"):
                        error("paciente_distinto", nombre, {"paso": orden}, posicion)
                    if herramienta == "preguntar" and (argumentos.get("a_quien") not in ("paciente", "acompanante") or argumentos.get("tema") not in ("cobertura", "art")):
                        error("dominio_preguntar", nombre, {"paso": orden}, posicion)
            if not herramientas or herramientas[0] != "leer_triage" or herramientas[-1] != "registrar_decision" or herramientas.count("registrar_decision") != 1:
                error("inicio_fin_traza", nombre, "Se espera leer_triage al inicio y un único registrar_decision al final.", posicion)
        revisar_ids(trazas, nombre, {f"{prefijo}-{i:0{ancho}d}" for i in range(1, cantidad + 1)})
        grupos = _grupos_repetidos((t.get("paciente_id"), t.get("id")) for t in trazas if isinstance(t.get("paciente_id"), str))
        pasos_validos = [t["pasos"] for t in trazas if isinstance(t.get("pasos"), list)]
        informe["archivos"][nombre].update({
            "esquemas_traza": [
                {"campos": list(campos), "registros": cantidad_esquema}
                for campos, cantidad_esquema in sorted(Counter(tuple(sorted(t)) for t in trazas).items())
            ],
            "campos_ficha": list(FICHA),
            "pasos_por_traza": dict(sorted(Counter(len(p) for p in pasos_validos).items())),
            "llamadas_por_herramienta": dict(sorted(Counter(
                p["herramienta"] for pasos in pasos_validos for p in pasos
                if isinstance(p, dict) and isinstance(p.get("herramienta"), str)
            ).items())),
            "paciente_ids_repetidos": grupos,
            "trazas_repetidas_sin_id_fecha_operador": list(_grupos_repetidos(
                (json.dumps({k: v for k, v in t.items() if k not in {"id", "fecha", "operador"}}, sort_keys=True), t.get("id")) for t in trazas
            ).values()),
        })
        if grupos:
            informe["advertencias"].append({
                "codigo": "paciente_id_repetido", "archivo": nombre,
                "grupos": len(grupos), "apariciones_adicionales": sum(len(ids) - 1 for ids in grupos.values()),
                "detalle": "No implica admisiones duplicadas: relacionar el historial por id de admisión y revisar contenido antes de particionar.",
            })

    trazas_historial = fuentes_trazas[HISTORIAL]
    mismos_ids = [f.get("id") for f in filas_csv] == [t.get("id") for t in trazas_historial]
    if not mismos_ids:
        error("orden_historial", HISTORIAL, "Los IDs del CSV y de las trazas no coinciden en el mismo orden.")
    comparadas = 0
    trazas_por_id = {t["id"]: t for t in trazas_historial if isinstance(t.get("id"), str)}
    for posicion, fila in enumerate(filas_csv, 1):
        traza = trazas_por_id.get(fila.get("id"))
        if traza is None:
            continue
        for campo in ("fecha", "operador"):
            if fila.get(campo) != traza.get(campo):
                error("metadatos_no_coinciden", HISTORIAL, {"id": fila.get("id"), "campo": campo}, posicion)
        ficha = traza.get("ficha")
        if not isinstance(ficha, dict):
            continue
        for campo in FICHA:
            valor = fila.get(campo)
            if campo in BOOLEANOS_FICHA:
                normalizado = {"sí": True, "no": False}.get(valor, "valor_inválido")
            elif campo in NULABLES_FICHA and valor == "":
                normalizado = None
            elif campo == "plazo_circuito_min" and isinstance(valor, str) and valor.isdecimal():
                normalizado = int(valor)
            else:
                normalizado = valor
            if type(normalizado) is not type(ficha.get(campo)) or normalizado != ficha.get(campo):
                error("csv_difiere_ficha", HISTORIAL, {"id": fila.get("id"), "campo": campo}, posicion)
        comparadas += 1
    informe["correspondencia"] = {"ids_en_el_mismo_orden": mismos_ids, "fichas_comparadas": comparadas, "campos_por_ficha": len(FICHA)}
    informe["resultado"] = "ok" if not informe["errores"] else "errores"
    return informe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1], help="Raíz del kit a inspeccionar.")
    parser.add_argument("--salida", type=Path, default=Path("datos/diagnostico.json"), help="Ruta del informe, relativa a --raiz si no es absoluta.")
    args = parser.parse_args(argv)
    salida = args.salida if args.salida.is_absolute() else args.raiz / args.salida
    fuentes = {(args.raiz / nombre).resolve() for nombre in (CSV, HISTORIAL, REFERENCIA)}
    if salida.resolve() in fuentes:
        parser.error("La salida no puede sobrescribir una fuente de datos.")
    informe = inspeccionar(args.raiz)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Inspección: {informe['resultado']}. Errores: {len(informe['errores'])}. Advertencias: {len(informe['advertencias'])}.")
    for nombre, perfil in informe["archivos"].items():
        print(f"  {nombre}: {perfil.get('registros', 0)} registros.")
    print(f"Diagnóstico guardado en {salida}")
    return 1 if informe["errores"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
