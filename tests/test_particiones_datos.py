import copy
import unittest

from datos.particiones import particionar


class ParticionesTests(unittest.TestCase):
    def registros(self):
        return [{"id": f"caso-{i:03d}", "paciente_id": f"P-{i}", "huella_conversacion": f"huella-{i}"} for i in range(64)]

    def test_mismo_paciente_o_contenido_quedan_juntos_incluso_transitivamente(self):
        registros = self.registros()
        registros[1]["paciente_id"] = registros[0]["paciente_id"]
        registros[2]["huella_conversacion"] = registros[1]["huella_conversacion"]
        particiones = particionar(registros, fraccion_validacion=0.5)
        ubicacion = {r["id"]: nombre for nombre, filas in particiones.items() for r in filas}
        self.assertEqual(ubicacion["caso-000"], ubicacion["caso-001"])
        self.assertEqual(ubicacion["caso-001"], ubicacion["caso-002"])
        self.assertEqual(sum(map(len, particiones.values())), 64)
        self.assertTrue(all(particiones.values()))

    def test_independiente_del_orden_y_fuentes_sin_cambios(self):
        registros = self.registros()
        antes = copy.deepcopy(registros)
        self.assertEqual(particionar(registros), particionar(list(reversed(registros))))
        self.assertEqual(registros, antes)
        self.assertNotEqual(particionar(registros, semilla=42), particionar(registros, semilla=43))

    def test_rechaza_identificadores_duplicados(self):
        registros = self.registros()
        registros.append(copy.deepcopy(registros[0]))
        with self.assertRaisesRegex(ValueError, "duplicados"):
            particionar(registros)

    def test_rechaza_fraccion_invalida(self):
        for fraccion in (0, 1, -0.1, 2, float("nan")):
            with self.subTest(fraccion=fraccion), self.assertRaises(ValueError):
                particionar(self.registros(), fraccion_validacion=fraccion)


if __name__ == "__main__":
    unittest.main()
