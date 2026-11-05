"""Modelo FALSO y determinista, para probar de punta a punta la entrega y la evaluación sin GPU.

Sigue un guion fijo (triage, cobertura, verificación, una búsqueda y la ficha) leyendo sólo lo que la conversación ya
le mostró. No sabe las normas: sus fichas no sirven como resultado y ningún número del informe sale de acá."""

import json
import re


def _llamada(herramienta: str, **argumentos) -> str:
    return json.dumps({"herramienta": herramienta, "argumentos": argumentos}, ensure_ascii=False)


class ModeloFalso:
    def __call__(self, conversaciones: list[list[dict]]) -> list[str]:
        return [self._responder(c) for c in conversaciones]

    def _responder(self, mensajes: list[dict]) -> str:
        paciente = re.search(r"paciente (\S+)\.", mensajes[1]["content"]).group(1)
        resultados = [m["content"] for m in mensajes[2:] if m["role"] == "user"]
        hechos = len([m for m in mensajes if m["role"] == "assistant"])
        triage = next((r for r in resultados if r.startswith("Resultado de leer_triage")), "")
        if hechos == 0:
            return _llamada("leer_triage", paciente_id=paciente)
        if hechos == 1:
            quien = "paciente" if "Puede responder preguntas: sí" in triage else "acompanante"
            return _llamada("preguntar", paciente_id=paciente, a_quien=quien, tema="cobertura")
        declarada = re.search(r"tiene (.+?) \((obra social|prepaga)\), número de afiliado (\S+?)\.", resultados[-1])
        if hechos == 2 and declarada:
            return _llamada("verificar_afiliacion", entidad=declarada.group(1), numero_afiliado=declarada.group(3))
        if not any(r.startswith("Resultado de buscar_normativa") for r in resultados):
            return _llamada("buscar_normativa", consulta="registro definitivo o provisorio según el documento")
        documento = re.search(r"Documento: presentó \S+ (\S+?)\.", triage)
        return _llamada("registrar_decision", registro="definitivo" if documento else "provisorio",
                        numero_documento=documento.group(1) if documento else None, box_antes_del_registro=False,
                        circuito="ninguno", plazo_circuito_min=None, cobertura="sin_cobertura",
                        entidad_a_notificar=None, aviso_al_voluntariado=False, fundamentos=["NOR-ADM-01"])
