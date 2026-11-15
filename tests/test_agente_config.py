"""Pruebas de la configuración: lo que se pisa por variable de entorno queda en la parte `modelo`."""

import unittest

from agente.config import cargar_config


class TestConfig(unittest.TestCase):
    def test_por_defecto_no_pisa_device_map_ni_lote(self):
        modelo = cargar_config(entorno={})["modelo"]
        self.assertNotIn("device_map", modelo)
        self.assertEqual(modelo["lote"], 50)

    def test_device_map_y_lote_por_variable_de_entorno(self):
        modelo = cargar_config(entorno={"ADMISION_DEVICE_MAP": "auto", "ADMISION_LOTE": "8"})["modelo"]
        self.assertEqual(modelo["device_map"], "auto")
        self.assertEqual(modelo["lote"], 8)


if __name__ == "__main__":
    unittest.main()
