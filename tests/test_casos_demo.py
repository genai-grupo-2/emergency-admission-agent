import json
import unittest

from datos.casos_demo import elegir, filtrar


def candidato(id_, llegada="por sus propios medios", circuito=None):
    return {"id": id_, "llegada": llegada, "circuito_probable": circuito}


class CasosDemoTest(unittest.TestCase):
    def test_elige_ambulancia_y_costumbre_sin_circuito(self):
        candidatos = {
            "tiempo_dependiente": [candidato("pev-002", "en ambulancia", "ecg"), candidato("pev-003", circuito="ecg")],
            "costumbre": [candidato("pev-005"), candidato("pev-004", circuito="ecg"), candidato("pev-002", "en ambulancia", "ecg")],
        }
        self.assertEqual(elegir(candidatos), ["pev-002", "pev-005"])

    def test_filtra_en_orden_y_sin_tocar_las_lineas(self):
        lineas = [json.dumps({"id": f"pev-00{i}", "x": i}) + "\n" for i in range(1, 5)]
        self.assertEqual(filtrar(lineas, ["pev-003", "pev-001"]), [lineas[0], lineas[2]])

    def test_falla_si_falta_un_caso(self):
        with self.assertRaises(KeyError):
            filtrar([json.dumps({"id": "pev-001"}) + "\n"], ["pev-009"])


if __name__ == "__main__":
    unittest.main()
