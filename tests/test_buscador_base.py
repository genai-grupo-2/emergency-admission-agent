"""Compatibilidad del BM25 de Juan antes de modificar su estrategia."""

from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from buscador.bm25 import BuscadorBM25


RAIZ = Path(__file__).resolve().parents[1]


class BuscadorBaseTests(unittest.TestCase):
    def test_contrato_y_corpus_completo_en_las_tres_variantes(self):
        for variante in ("original", "b", "c"):
            with self.subTest(variante=variante):
                buscador = BuscadorBM25(RAIZ / "normas" / variante)
                self.assertEqual(len(buscador.secciones), 20)
                self.assertTrue(any(s.id.startswith("NOR-INT") for s in buscador.secciones))
                resultado = buscador.recuperar("dolor torácico electrocardiograma", 2)
                self.assertEqual(len(resultado), buscador.k_entorno)
                self.assertTrue(all(isinstance(s.texto, str) and s.texto for s in resultado))
                self.assertEqual(resultado[0].id, "NOR-TDE-01")

    def test_lee_parametros_de_una_carpeta_ajena_al_repo(self):
        with tempfile.TemporaryDirectory() as temporal:
            normas = Path(temporal) / "normas"
            shutil.copytree(RAIZ / "normas/original", normas)
            archivo = normas / "parametros.yaml"
            datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
            for parametro in datos["parametros"]:
                if parametro["codigo"] == "P-TDE-1":
                    parametro["valor"] = 137
            archivo.write_text(yaml.safe_dump(datos), encoding="utf-8")
            buscador = BuscadorBM25(normas)
            textos = [s.texto for s in buscador.recuperar("electrocardiograma dolor torácico", 20)]
            self.assertTrue(any("P-TDE-1 = 137 min" in texto for texto in textos))

    def test_acentos_y_resultado_determinista(self):
        buscador = BuscadorBM25(RAIZ / "normas/original")
        ids = lambda q: [s.id for s in buscador.recuperar(q, 3)]
        self.assertEqual(ids("dolor torácico"), ids("DOLOR TORACICO"))
        self.assertEqual(ids("dolor torácico"), ids("dolor torácico"))
        self.assertEqual(buscador.recuperar("dolor", 0), [])
        resultados = buscador.recuperar("dolor", 100)
        self.assertLessEqual(len(resultados), 20)
        self.assertEqual(len({s.id for s in resultados}), len(resultados))

    def test_carpeta_sin_secciones_falla_explicitamente(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            shutil.copy(RAIZ / "normas/original/parametros.yaml", carpeta)
            with self.assertRaises(FileNotFoundError):
                BuscadorBM25(carpeta)


if __name__ == "__main__":
    unittest.main()
