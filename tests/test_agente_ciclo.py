"""Pruebas del ciclo del agente con el entorno real del kit y un modelo guionado (sin GPU ni torch).

    python -m unittest discover -s tests -p "test_agente_*.py" -v
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from admision.casos import cargar_casos
from admision.entorno import Entorno, VistaDelAgente
from agente.ciclo import NO_ENTENDI, Agente

RAIZ = Path(__file__).resolve().parent.parent
CASOS = {c.paciente_id: c for c in cargar_casos(RAIZ / "practica" / "casos.jsonl")[:3]}
A, B, C = list(CASOS)


class BuscadorFijo:
    k_entorno = 2

    def recuperar(self, consulta, k):
        return ["## NOR-ADM-01 · Registro"]


def llamada(herramienta, **argumentos):
    return json.dumps({"herramienta": herramienta, "argumentos": argumentos})


def ficha(**cambios):
    f = dict(registro="provisorio", numero_documento=None, box_antes_del_registro=False, circuito="ninguno",
             plazo_circuito_min=None, cobertura="sin_cobertura", entidad_a_notificar=None,
             aviso_al_voluntariado=False)
    return llamada("registrar_decision", **{**f, **cambios})


class ModeloGuionado:
    """Una lista de respuestas por paciente; un Exception en la lista se lanza en ese turno. Guarda lo que recibe."""

    def __init__(self, guiones):
        self.guiones = {k: list(v) for k, v in guiones.items()}
        self.lotes = []

    def __call__(self, conversaciones):
        self.lotes.append(len(conversaciones))
        respuestas = []
        for c in conversaciones:
            paciente = next(p for p in self.guiones if p in c[1]["content"])
            if not self.guiones[paciente]:
                raise AssertionError(f"se agotó el guion de {paciente}")
            r = self.guiones[paciente].pop(0)
            if isinstance(r, Exception):
                raise r
            respuestas.append(r)
        return respuestas


def entornos(*pacientes):
    reales = [Entorno(CASOS[p], BuscadorFijo()) for p in pacientes]
    return reales, [VistaDelAgente(e.paciente_id, e.paso) for e in reales]


def jugar(guiones, *pacientes, **opciones):
    reales, vistas = entornos(*pacientes)
    agente = Agente(ModeloGuionado(guiones), "Sistema de prueba.", **opciones)
    return agente, reales, agente.jugar_lote(vistas)


class CicloTest(unittest.TestCase):
    def test_registrar_decision_cierra_el_caso(self):
        agente, (e,), (conv,) = jugar({A: [llamada("leer_triage", paciente_id=A), ficha()]}, A)
        self.assertEqual(e.decision["registro"], "provisorio")
        self.assertEqual([m["role"] for m in conv], ["system", "user", "assistant", "user", "assistant"])
        self.assertEqual(conv[-1]["content"], ficha())
        self.assertEqual(agente.informe[0]["fin"], "registrada")

    def test_conversaciones_en_el_orden_del_lote(self):
        guiones = {A: [llamada("leer_triage", paciente_id=A)] * 3 + [ficha()], B: [ficha()],
                   C: [llamada("leer_triage", paciente_id=C), ficha()]}
        agente, reales, convs = jugar(guiones, A, B, C)
        self.assertEqual([c[1]["content"].split()[6].rstrip(".") for c in convs], [A, B, C])
        self.assertEqual([len(c) for c in convs], [2 + 4 * 2 - 1, 3, 5])
        self.assertEqual(agente.modelo_lote.lotes, [3, 2, 1, 1])
        self.assertTrue(all(e.decision is not None for e in reales))

    def test_json_invalido_pide_corregir_y_sigue(self):
        _, (e,), (conv,) = jugar({A: ["no sé", ficha()]}, A)
        self.assertEqual(conv[3]["content"], NO_ENTENDI)
        self.assertIsNotNone(e.decision)

    def test_tres_json_invalidos_seguidos_cierran_sin_gastar_llamadas(self):
        agente, (e,), (conv,) = jugar({A: ["a", "{roto", "```json\n{}\n```"]}, A)
        self.assertEqual(agente.informe[0]["fin"], "sin_json")
        self.assertEqual(e.log, [])
        self.assertEqual(conv[-1]["role"], "assistant")

    def test_herramienta_desconocida_no_gasta_llamada(self):
        _, (e,), (conv,) = jugar({A: [llamada("consultar_medico"), ficha()]}, A)
        self.assertIn("no existe la herramienta", conv[3]["content"])
        self.assertIn("registrar_decision", conv[3]["content"])
        self.assertEqual([x["herramienta"] for x in e.log], ["registrar_decision"])

    def test_argumentos_que_no_son_objeto(self):
        for argumentos in ([A], None, A):
            with self.subTest(argumentos=argumentos):
                malo = json.dumps({"herramienta": "leer_triage", "argumentos": argumentos})
                _, (e,), (conv,) = jugar({A: [malo, ficha()]}, A)
                self.assertIn('"argumentos" tiene que ser un objeto', conv[3]["content"])
                self.assertEqual(len(e.log), 1)

    def test_error_de_argumentos_del_entorno_vuelve_como_observacion(self):
        _, (e,), (conv,) = jugar({A: [ficha(registro="quizas"), ficha()]}, A)
        self.assertTrue(conv[3]["content"].startswith("Resultado de registrar_decision:\nError:"))
        self.assertEqual([x["valida"] for x in e.log], [False, True])

    def test_aviso_de_llamadas_restantes_y_cierre_con_la_ultima(self):
        guion = [llamada("leer_triage", paciente_id=A)] * 39 + [ficha()]
        agente, (e,), (conv,) = jugar({A: guion}, A)
        avisos = [m["content"] for m in conv if m["role"] == "user" and "Te quedan" in m["content"]]
        self.assertEqual(len(avisos), 5)
        self.assertIn("Te quedan 5 llamadas", avisos[0])
        self.assertEqual(len(e.log), 40)
        self.assertIsNotNone(e.decision)
        self.assertEqual(agente.informe[0]["fin"], "registrada")

    def test_con_una_llamada_sola_acepta_solo_registrar(self):
        guion = [llamada("leer_triage", paciente_id=A)] * 41
        agente, (e,), (conv,) = jugar({A: guion}, A, max_turnos=41)
        self.assertEqual(len(e.log), 39)
        self.assertIsNone(e.decision)
        self.assertIn("una sola llamada", conv[-1]["content"])
        self.assertEqual(agente.informe[0]["fin"], "max_turnos")

    def test_tope_de_40_del_entorno_termina_el_caso(self):
        guion = [llamada("leer_triage", paciente_id=A)] * 40
        agente, (e,), _ = jugar({A: guion}, A, max_llamadas=41)  # el agente no frena: frena el entorno
        self.assertEqual(len(e.log), 40)
        self.assertTrue(e.terminado)
        self.assertEqual(agente.informe[0]["fin"], "terminado")

    def test_caso_ya_terminado(self):
        vista = VistaDelAgente(A, lambda h, a: ("El caso ya terminó.", True))
        agente = Agente(ModeloGuionado({A: [llamada("leer_triage", paciente_id=A)]}), "S.")
        (conv,) = agente.jugar_lote([vista])
        self.assertEqual(agente.informe[0]["fin"], "terminado")
        self.assertEqual(conv[-1]["role"], "assistant")

    def test_falla_del_modelo_en_un_caso_no_corta_el_lote(self):
        agente, (ea, eb), (ca, cb) = jugar({A: [RuntimeError("sin memoria")] * 2, B: [ficha()]}, A, B)
        self.assertEqual(agente.informe[0]["fin"], "error_modelo")
        self.assertIn("sin memoria", agente.informe[0]["error"])
        self.assertEqual(len(ca), 2)
        self.assertIsNotNone(eb.decision)

    def test_falla_del_entorno_en_un_caso_no_corta_el_lote(self):
        def roto(h, a):
            raise OSError("se cayó")
        _, (eb,) = entornos(B)
        vistas = [VistaDelAgente(A, roto), VistaDelAgente(B, eb.paso)]
        agente = Agente(ModeloGuionado({A: [llamada("leer_triage", paciente_id=A)], B: [ficha()]}), "S.")
        agente.jugar_lote(vistas)
        self.assertEqual([x["fin"] for x in agente.informe], ["error_entorno", "registrada"])

    def test_lote_vacio(self):
        self.assertEqual(Agente(ModeloGuionado({}), "S.").jugar_lote([]), [])

    def test_no_importa_torch(self):
        codigo = "import sys, agente.ciclo, entrega; assert 'torch' not in sys.modules"
        r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
