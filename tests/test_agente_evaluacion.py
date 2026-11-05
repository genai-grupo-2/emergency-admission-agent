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


if __name__ == "__main__":
    unittest.main()
