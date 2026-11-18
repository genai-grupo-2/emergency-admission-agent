import json
import unittest

from datos.ver_demo import paso, recorrido


def _llamada(herramienta, **argumentos):
    return json.dumps({"herramienta": herramienta, "argumentos": argumentos}, ensure_ascii=False)


class RecorridoTest(unittest.TestCase):
    def test_busqueda_muestra_consulta_y_normas(self):
        respuesta = "Resultado de buscar_normativa:\n## NOR-TDE-04 · Ambulancia\n§1. ...\n## NOR-TDE-01 · Dolor\n§1. ..."
        self.assertEqual(paso(_llamada("buscar_normativa", consulta="ambulancia"), respuesta),
                         "`buscar_normativa` «ambulancia» → NOR-TDE-04, NOR-TDE-01")

    def test_triage_resume_los_datos_de_la_admision(self):
        respuesta = ("Resultado de leer_triage:\nPaciente: Laura Correa, 82 años.\nMotivo de consulta: dolor abdominal.\n"
                     "Llegada: en ambulancia.\nAcompañante: ninguno.")
        self.assertEqual(paso(_llamada("leer_triage", paciente_id="P-1"), respuesta),
                         "`leer_triage` → 82 años, dolor abdominal, llegó en ambulancia; acompañante: ninguno")

    def test_respuesta_sin_json_y_ultimo_paso_sin_entorno(self):
        mensajes = [{"role": "system", "content": "s"}, {"role": "user", "content": "pedido"},
                    {"role": "assistant", "content": "no sé"}, {"role": "user", "content": "Respondé con JSON"},
                    {"role": "assistant", "content": _llamada("registrar_decision")}]
        self.assertEqual(recorrido(mensajes), [
            "1. Respuesta sin una llamada a herramienta válida",
            "2. `registrar_decision` → ficha registrada (valores en la tabla de arriba)"])


if __name__ == "__main__":
    unittest.main()
