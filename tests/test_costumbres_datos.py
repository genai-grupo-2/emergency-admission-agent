import copy
import unittest

from datos.costumbres import desvios_costumbres, inferir_costumbres


class CostumbresTests(unittest.TestCase):
    def setUp(self):
        self.filas = []
        for edad in range(20, 90):
            for acompanante in ("", "su hermana"):
                for repeticion in range(2):
                    self.filas.append({
                        "id": f"CASO-{len(self.filas):04d}", "edad": str(edad), "acompanante": acompanante,
                        "aviso_al_voluntariado": "sí" if edad >= 75 and not acompanante else "no",
                        "lesion_trabajo": "no", "credenciales": "OS de prueba (obra social) 123; Prepaga de prueba (prepaga) 456" if repeticion else "",
                        "cobertura_declarada": "ninguna", "entidad_verificada": "Prepaga de prueba" if repeticion else "",
                    })

    def test_recupera_umbral_y_no_altera_fuentes(self):
        antes = copy.deepcopy(self.filas)
        modelo = inferir_costumbres(self.filas)
        self.assertEqual(modelo["voluntariado"]["edad_minima"], 75)
        self.assertEqual(self.filas, antes)
        self.assertEqual(modelo["doble_credencial"]["contraejemplos"], [])

    def test_contraejemplo_es_ruido_sin_cambiar_la_costumbre(self):
        self.filas[0]["aviso_al_voluntariado"] = "sí"
        modelo = inferir_costumbres(self.filas)
        self.assertEqual(modelo["voluntariado"]["edad_minima"], 75)
        self.assertIn(self.filas[0]["id"], modelo["voluntariado"]["grupos"]["no_activar"]["contraejemplos"])
        self.assertEqual(desvios_costumbres(self.filas[0], modelo)[0]["costumbre"], "voluntariado")

    def test_preferencia_no_depende_del_campo_final_cobertura(self):
        modelo = inferir_costumbres(self.filas)
        fila = copy.deepcopy(self.filas[1])
        fila.update(cobertura="sin_cobertura", entidad_verificada="OS de prueba")
        self.assertEqual(desvios_costumbres(fila, modelo)[0]["costumbre"], "doble_credencial")
        fila["lesion_trabajo"] = "trabajando"
        self.assertEqual(desvios_costumbres(fila, modelo), [])

    def test_no_afirma_costumbre_con_pocos_ejemplos(self):
        with self.assertRaisesRegex(ValueError, "pocas filas"):
            inferir_costumbres(self.filas[:10])

    def test_no_inventa_umbral_si_dos_edades_empatan(self):
        sin_limite = [f for f in self.filas if f["edad"] != "75"]
        with self.assertRaisesRegex(ValueError, "ambiguo"):
            inferir_costumbres(sin_limite)


if __name__ == "__main__":
    unittest.main()
