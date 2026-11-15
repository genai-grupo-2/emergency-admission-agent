"""Comportamiento del buscador y conservación del conocimiento variable."""

from pathlib import Path
import unittest

from admision.normas import cargar_normas
from buscador.bm25 import BuscadorBM25


RAIZ = Path(__file__).resolve().parents[1]


class BuscadorTests(unittest.TestCase):
    def test_consultas_vacias_o_sin_coincidencias(self):
        buscador = BuscadorBM25(RAIZ / "normas/original")
        for consulta in ("", " \t\n", "¿?!", "xyzsincoincidencias"):
            with self.subTest(consulta=consulta):
                self.assertEqual(buscador.recuperar(consulta, 2), [])
        with self.assertRaises(TypeError):
            buscador.recuperar(None, 2)

    def test_argumentos_invalidos(self):
        ruta = RAIZ / "normas/original"
        for opciones in ({"k_entorno": 0}, {"k_entorno": True}, {"k1": 0},
                         {"k1": float("nan")}, {"k1": "1.5"}, {"b": -1},
                         {"b": 1.1}, {"b": float("inf")}, {"fragmentacion": "otra"}):
            with self.subTest(opciones=opciones):
                with self.assertRaises((TypeError, ValueError)):
                    BuscadorBM25(ruta, **opciones)
        buscador = BuscadorBM25(ruta)
        for k in (-1, 1.5, True, "2"):
            with self.subTest(k=k):
                with self.assertRaises((TypeError, ValueError)):
                    buscador.recuperar("documento", k)

    def test_parrafos_preservan_texto_parametros_y_procedencia(self):
        for variante in ("original", "b", "c"):
            with self.subTest(variante=variante):
                ruta = RAIZ / "normas" / variante
                buscador = BuscadorBM25(ruta, fragmentacion="parrafo")
                for seccion in cargar_normas(ruta):
                    fragmentos = [f for f in buscador.fragmentos if f.seccion == seccion.id]
                    self.assertTrue(fragmentos)
                    for parrafo in seccion.cuerpo.split("\n\n")[1:]:
                        self.assertTrue(any(parrafo in f.texto for f in fragmentos))
                    for f in fragmentos:
                        self.assertIn(seccion.valores, f.texto)
                        self.assertIn(seccion.cuerpo.splitlines()[0], f.texto)
                largos = [len(f.texto) for f in buscador.fragmentos if f.seccion == "NOR-COB-02"]
                original = next(s for s in cargar_normas(ruta) if s.id == "NOR-COB-02")
                self.assertLess(max(largos), len(original.texto))

    def test_secciones_completas_son_el_modo_compatible_por_defecto(self):
        buscador = BuscadorBM25(RAIZ / "normas/original", k_entorno=3)
        self.assertEqual(buscador.k_entorno, 3)
        self.assertEqual([f.texto for f in buscador.fragmentos], [s.texto for s in buscador.secciones])
        self.assertEqual(len(buscador.recuperar("cobertura", 3)), 3)


if __name__ == "__main__":
    unittest.main()
