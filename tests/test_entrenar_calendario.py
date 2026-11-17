"""Pruebas del orden de los datos, el calendario de aprendizaje y la reanudación (sin GPU)."""

import tempfile
import unittest
from pathlib import Path

from entrenar import entrenar as e


class TestOrden(unittest.TestCase):
    def test_cada_epoca_usa_todas_las_conversaciones_una_vez(self):
        n, acum = 64, 16
        orden = {}
        vistos = []
        for paso in range(e.pasos_por_epoca(n, acum)):
            vistos += e.lote_del_paso(orden, n, 42, acum, paso)
        self.assertEqual(sorted(vistos), list(range(n)))

    def test_reanudar_da_los_mismos_lotes_que_seguir_de_largo(self):
        n, acum = 100, 8
        completo = [e.lote_del_paso({}, n, 7, acum, p) for p in range(30)]
        reanudado = {}
        despues = [e.lote_del_paso(reanudado, n, 7, acum, p) for p in range(17, 30)]  # sin haber visto 0..16
        self.assertEqual(completo[17:], despues)

    def test_otra_semilla_cambia_el_orden_y_las_epocas_difieren(self):
        self.assertNotEqual(e.orden_de_la_epoca(50, 1, 0), e.orden_de_la_epoca(50, 2, 0))
        self.assertNotEqual(e.orden_de_la_epoca(50, 1, 0), e.orden_de_la_epoca(50, 1, 1))
        self.assertEqual(e.orden_de_la_epoca(50, 1, 0), e.orden_de_la_epoca(50, 1, 0))

    def test_sobran_menos_que_un_lote_y_se_descartan(self):
        self.assertEqual(e.pasos_por_epoca(2176, 16), 136)
        self.assertEqual(e.pasos_por_epoca(5, 16), 1)


class TestLR(unittest.TestCase):
    def test_calienta_y_baja_a_la_decima_parte(self):
        total, warmup = 100, 10
        self.assertAlmostEqual(e.factor_de_lr(0, total, warmup), 0.1)
        self.assertAlmostEqual(e.factor_de_lr(9, total, warmup), 1.0)
        self.assertAlmostEqual(e.factor_de_lr(10, total, warmup), 1.0)
        self.assertAlmostEqual(e.factor_de_lr(100, total, warmup), 0.1)
        valores = [e.factor_de_lr(p, total, warmup) for p in range(10, 101)]
        self.assertEqual(valores, sorted(valores, reverse=True))


class TestCheckpoints(unittest.TestCase):
    def test_el_ultimo_checkpoint_es_el_de_mayor_paso_con_estado(self):
        with tempfile.TemporaryDirectory() as t:
            carpeta = Path(t)
            for paso, con_estado in ((34, True), (68, True), (102, False)):
                d = carpeta / f"paso-{paso:05d}"
                d.mkdir()
                if con_estado:
                    (d / "estado.pt").write_bytes(b"x")
            self.assertEqual(e.ultimo_checkpoint(carpeta).name, "paso-00068")
            self.assertIsNone(e.ultimo_checkpoint(carpeta / "no-existe"))


class TestArgumentos(unittest.TestCase):
    def test_sin_wandb_solo_se_permite_en_ensayos(self):
        with self.assertRaises(SystemExit):
            e.principal(["--config", "entrenar/configs/sft-catedra.json", "--sin-wandb"])

    def test_solo_datos_valida_sin_gpu_ni_escribir_corridas(self):
        antes = set(e.CARPETA_CORRIDAS.glob("*")) if e.CARPETA_CORRIDAS.exists() else set()
        self.assertEqual(e.principal(["--config", str(e.RAIZ / "entrenar/configs/sft-catedra.json"), "--solo-datos"]), 0)
        despues = set(e.CARPETA_CORRIDAS.glob("*")) if e.CARPETA_CORRIDAS.exists() else set()
        self.assertEqual(antes, despues)


if __name__ == "__main__":
    unittest.main()
