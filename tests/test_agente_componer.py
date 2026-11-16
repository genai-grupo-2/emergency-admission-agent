"""Juntar corridas ya hechas en una condiciÃ³n de la matriz (con el modelo falso, sin GPU)."""

import json
import shutil
import unittest
import uuid

from evaluacion.componer import componer
from evaluacion.evaluar import RAIZ, evaluar, resumen_de, seleccionar_casos

FALSO = {"ADMISION_BACKEND": "falso"}


class ComponerTest(unittest.TestCase):
    def setUp(self):
        self.prefijo = f"prueba-{uuid.uuid4().hex[:8]}"
        self.creadas = []

    def tearDown(self):
        for e in self.creadas:
            shutil.rmtree(RAIZ / "corridas" / "eval" / e, ignore_errors=True)

    def _correr(self, nombre, cuales, extra=FALSO, normas=("c",)):
        e = f"{self.prefijo}-{nombre}"
        self.creadas.append(e)
        evaluar(e, seleccionar_casos(cuales), list(normas), extra, cuales)
        return RAIZ / "corridas" / "eval" / e

    def _etiqueta(self, nombre):
        e = f"{self.prefijo}-{nombre}"
        self.creadas.append(e)
        return e

    def test_junta_optimizacion_y_validacion_en_los_50_casos(self):
        partes = [self._correr("opt", "optimizacion"), self._correr("val", "validacion")]
        e = self._etiqueta("todos")
        condicion = componer(e, partes, "todos", ["c"], exigir_commit_limpio=False)
        self.assertTrue(condicion["compuesta"])
        self.assertEqual(condicion["codigos_de_salida"]["c"]["puntuar"], 0)
        self.assertEqual(resumen_de(e)["c"]["casos"], 50)
        trazas = (RAIZ / "corridas" / "eval" / e / "c" / "trazas.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(t)["caso"] for t in trazas], [c["id"] for c in seleccionar_casos("todos")])
        self.assertEqual(condicion["prompt"]["version"], "catedra")
        with self.assertRaises(FileExistsError):
            componer(e, partes, "todos", ["c"], exigir_commit_limpio=False)

    def test_rechaza_si_faltan_casos(self):
        partes = [self._correr("val", "validacion")]
        with self.assertRaises(ValueError):
            componer(self._etiqueta("incompleta"), partes, "todos", ["c"], exigir_commit_limpio=False)

    def test_rechaza_prompts_distintos(self):
        partes = [self._correr("opt", "optimizacion", {**FALSO, "ADMISION_PROMPT": "optimizado"}),
                  self._correr("val", "validacion")]
        with self.assertRaises(ValueError):
            componer(self._etiqueta("mezcla"), partes, "todos", ["c"], exigir_commit_limpio=False)


if __name__ == "__main__":
    unittest.main()
