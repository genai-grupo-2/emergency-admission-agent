import unittest

from datos.candidatos_demo import candidatos, circuito_probable, doble_credencial, voluntariado


def caso(**cambios):
    base = {
        "id": "pev-900",
        "edad": 40,
        "nivel": 3,
        "motivo": "cefalea",
        "sepsis": "no",
        "llegada": "por sus propios medios",
        "acompanante": "su hermana Laura",
        "credenciales": [],
        "trabajo": None,
    }
    return base | cambios


class CandidatosDemoTest(unittest.TestCase):
    def test_circuito_por_motivo_y_por_sepsis(self):
        self.assertIsNone(circuito_probable(caso()))
        self.assertEqual(circuito_probable(caso(motivo="dolor torácico")), "ecg")
        self.assertEqual(
            circuito_probable(caso(motivo="signos neurológicos focales de inicio súbito")), "codigo_acv"
        )
        self.assertEqual(circuito_probable(caso(sepsis="probable")), "codigo_sepsis")

    def test_voluntariado_exige_edad_y_ausencia_de_acompanante(self):
        self.assertTrue(voluntariado(caso(edad=75, acompanante=None)))
        self.assertFalse(voluntariado(caso(edad=74, acompanante=None)))
        self.assertFalse(voluntariado(caso(edad=80)))

    def test_doble_credencial_excluye_accidente_laboral(self):
        dos = [["obra_social", "OS", "1"], ["prepaga", "PP", "2"]]
        self.assertTrue(doble_credencial(caso(credenciales=dos)))
        self.assertFalse(doble_credencial(caso(credenciales=dos, trabajo="trabajando")))
        self.assertFalse(doble_credencial(caso(credenciales=dos[:1])))

    def test_orden_ambulancia_primero_y_costumbre_sin_circuito_primero(self):
        casos = [
            caso(id="pev-901", motivo="dolor torácico", edad=80, acompanante=None),
            caso(id="pev-902", motivo="dolor torácico", llegada="en ambulancia"),
            caso(id="pev-903", edad=80, acompanante=None),
            caso(id="pev-904"),
        ]
        resultado = candidatos(casos)
        self.assertEqual([r["id"] for r in resultado["tiempo_dependiente"]], ["pev-902", "pev-901"])
        self.assertEqual([r["id"] for r in resultado["costumbre"]], ["pev-903", "pev-901"])
        self.assertEqual(resultado["casos_revisados"], 4)


if __name__ == "__main__":
    unittest.main()
