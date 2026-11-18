"""Pruebas de la configuración de entrenamiento y del manifiesto de la corrida (sin GPU)."""

import json
import tempfile
import unittest
from pathlib import Path

from entrenar import config as cfg
from entrenar.config import RAIZ
from entrenar.manifiesto import Manifiesto


class TestConfig(unittest.TestCase):
    def test_la_configuracion_del_repositorio_es_valida_y_usa_el_modelo_base_del_grupo(self):
        c = cfg.cargar(RAIZ / "entrenar/configs/sft-catedra.json")
        self.assertEqual(c["prompt"]["version"], "catedra")
        self.assertEqual(c["modelo"]["repo"], "google/gemma-4-E4B-it")
        self.assertEqual(len(c["modelo"]["revision"]), 40)

    def test_falta_un_campo_obligatorio(self):
        with self.assertRaisesRegex(KeyError, "datos.train"):
            cfg.completar({"nombre": "x", "modelo": {"repo": "a", "revision": "b"}, "lora": {"modulos": "m"},
                           "datos": {"validacion": "v"}})

    def test_nombre_invalido(self):
        base = json.loads((RAIZ / "entrenar/configs/sft-catedra.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "nombre"):
            cfg.completar({**base, "nombre": "../fuera"})

    def test_ensayo_no_pisa_la_corrida_real_ni_sube_nada(self):
        base = cfg.cargar(RAIZ / "entrenar/configs/sft-catedra.json")
        base["subir_checkpoints_a"] = "grupo/repo"
        e = cfg.para_ensayo(base)
        self.assertNotEqual(e["nombre"], base["nombre"])
        self.assertIsNone(e["subir_checkpoints_a"])
        self.assertEqual(base["epocas"], 1)  # no modifica el original


class TestManifiesto(unittest.TestCase):
    def test_checkpoints_se_actualizan_y_quedan_ordenados(self):
        with tempfile.TemporaryDirectory() as t:
            m = Manifiesto(Path(t) / "a" / "manifiesto.json", {"nombre": "x", "estado": "en_curso"})
            m.agregar_checkpoint(paso=68, perdida_validacion=0.5)
            m.agregar_checkpoint(paso=34, perdida_validacion=0.7)
            m.actualizar_checkpoint(34, hf={"repo": "g/r", "revision": "abc"})
            leido = json.loads((Path(t) / "a" / "manifiesto.json").read_text(encoding="utf-8"))
            self.assertEqual([c["paso"] for c in leido["checkpoints"]], [34, 68])
            self.assertEqual(leido["checkpoints"][0]["hf"]["revision"], "abc")
            with self.assertRaises(KeyError):
                m.actualizar_checkpoint(99, x=1)

    def test_una_corrida_fallida_deja_el_motivo(self):
        with tempfile.TemporaryDirectory() as t:
            m = Manifiesto(Path(t) / "manifiesto.json", {"estado": "en_curso"})
            try:
                raise MemoryError("CUDA out of memory")
            except MemoryError as e:
                m.fallar(e)
            leido = json.loads((Path(t) / "manifiesto.json").read_text(encoding="utf-8"))
            self.assertEqual(leido["estado"], "fallida")
            self.assertIn("out of memory", leido["error"]["mensaje"])
            self.assertIn("fin", leido)

    def test_retomar_conserva_lo_anterior(self):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "manifiesto.json"
            Manifiesto(ruta, {"estado": "pausada", "semilla": 42}).agregar_checkpoint(paso=34)
            otra = Manifiesto.retomar(ruta)
            self.assertEqual(otra.datos["semilla"], 42)
            self.assertEqual(len(otra.datos["checkpoints"]), 1)


if __name__ == "__main__":
    unittest.main()
