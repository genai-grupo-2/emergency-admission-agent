"""Prueba de humo de la evaluación automatizada con el modelo falso (sin GPU): jugar y puntuar separados."""

import json
import shutil
import unittest
import uuid

from evaluacion.evaluar import RAIZ, evaluar, resumen_de, seleccionar_casos


class EvaluarTest(unittest.TestCase):
    def setUp(self):
        self.etiqueta = f"prueba-{uuid.uuid4().hex[:8]}"
        self.carpeta = RAIZ / "corridas" / "eval" / self.etiqueta

    def tearDown(self):
        shutil.rmtree(self.carpeta, ignore_errors=True)

    def test_deja_trazas_resultados_y_condicion_y_no_pisa(self):
        casos = seleccionar_casos("validacion")[:2]
        condicion = evaluar(self.etiqueta, casos, ["c"], {"ADMISION_BACKEND": "falso"}, "validacion")
        self.assertEqual(condicion["codigos_de_salida"]["c"], {"jugar": 0, "puntuar": 0})
        self.assertEqual(condicion["prompt"]["version"], "catedra")
        trazas = [json.loads(x) for x in (self.carpeta / "c" / "trazas.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([t["caso"] for t in trazas], [c["id"] for c in casos])
        self.assertTrue(all(t["mensajes"][0]["role"] == "system" for t in trazas))
        self.assertEqual(resumen_de(self.etiqueta)["c"]["casos"], 2)
        with self.assertRaises(FileExistsError):
            evaluar(self.etiqueta, casos, ["c"], {"ADMISION_BACKEND": "falso"}, "validacion")

    def test_las_particiones_no_se_cruzan(self):
        v = {c["id"] for c in seleccionar_casos("validacion")}
        o = {c["id"] for c in seleccionar_casos("optimizacion")}
        self.assertFalse(v & o)
        self.assertEqual(len(v | o), len(seleccionar_casos("todos")))


class TablasTest(unittest.TestCase):
    def test_reescribe_entre_marcadores_y_es_idempotente(self):
        from evaluacion.tablas import escribir
        texto = "a\n<!-- tabla:x -->\nvieja\n<!-- /tabla:x -->\nb"
        una = escribir(texto, {"x": "| nueva |"})
        self.assertEqual(una, "a\n<!-- tabla:x -->\n| nueva |\n<!-- /tabla:x -->\nb")
        self.assertEqual(escribir(una, {"x": "| nueva |"}), una)
        with self.assertRaises(KeyError):
            escribir(texto, {"y": "z"})

    def test_sin_corridas_no_hay_numeros_inventados(self):
        from evaluacion.matriz import cargar_matriz, tabla
        filas = tabla(cargar_matriz()).splitlines()[2:6]
        self.assertTrue(all("pendiente" in f or "bloqueado" in f or "/50" in f for f in filas))


if __name__ == "__main__":
    unittest.main()
