"""Pruebas del optimizador de prompt con evaluadores falsos y deterministas (sin GPU)."""

import tempfile
import unittest
from pathlib import Path

from agente.config import cargar_config
from agente.falso import ModeloFalso
from agente.prompts import cargar_prompt, tokens_aproximados
from optimizacion.bloques import SEMILLAS, armar, vecinos
from optimizacion.optimizar import Evaluador, buscar, frontera, puntaje
from optimizacion.particion import cargar_particion, particionar


def evaluador_por_texto(pesos):
    """Resueltos = suma de los pesos de los fragmentos presentes en el prompt; registra lo que evaluó."""
    llamados = []

    def evaluar(texto, sha):
        llamados.append(sha)
        return {"episodios": 90, "resueltos": sum(p for frag, p in pesos.items() if frag in texto),
                "parcial_medio": 0.5}
    return evaluar, llamados


class BloquesTest(unittest.TestCase):
    def test_la_semilla_catedra_es_el_prompt_de_la_catedra(self):
        self.assertEqual(armar(SEMILLAS["catedra"]), cargar_prompt("catedra"))

    def test_vecinos_cambian_un_bloque_y_nunca_omiten_el_protocolo(self):
        for mutacion, cand in vecinos(SEMILLAS["catedra"]):
            self.assertEqual(sum(cand[b] != SEMILLAS["catedra"][b] for b in cand), 1, mutacion)
            armar(cand)  # no levanta

    def test_ningun_bloque_trae_numeros_de_las_normas(self):
        from optimizacion.bloques import BLOQUES
        for bloque, variantes in BLOQUES.items():
            for nombre, texto in variantes.items():
                numeros = {n for n in __import__("re").findall(r"\d+", texto)} - {"1", "2", "3", "4", "01", "03",
                                                                                   "04", "1234", "75"}
                self.assertEqual(numeros, set(), f"{bloque}={nombre}")


class BusquedaTest(unittest.TestCase):
    def test_elige_la_mejora_y_es_determinista(self):
        pesos = {"Costumbres del hospital": 20, "Cómo trabajar": 5}
        r1 = buscar(evaluador_por_texto(pesos)[0], tokens_aproximados, 0.05, 40)
        r2 = buscar(evaluador_por_texto(pesos)[0], tokens_aproximados, 0.05, 40)
        self.assertIn("Costumbres del hospital", armar(r1["mejor"]["bloques"]))
        self.assertEqual([f["sha256"] for f in r1["historia"]], [f["sha256"] for f in r2["historia"]])
        self.assertEqual(r1["motivo_fin"], "sin mejora")

    def test_a_igual_acierto_gana_el_prompt_mas_corto(self):
        r = buscar(evaluador_por_texto({})[0], tokens_aproximados, 0.05, 60)
        self.assertEqual(r["mejor"]["tokens"], min(f["tokens"] for f in r["historia"]))

    def test_no_reevalua_y_respeta_el_presupuesto(self):
        evaluar, llamados = evaluador_por_texto({"Costumbres": 1})
        r = buscar(evaluar, tokens_aproximados, 0.05, 5)
        self.assertEqual(len(llamados), 5)
        self.assertEqual(len(set(llamados)), 5)
        self.assertEqual(r["motivo_fin"], "presupuesto agotado")

    def test_una_evaluacion_que_falla_queda_registrada_y_no_compite(self):
        filas = []

        def evaluar(texto, sha):
            if "Costumbres" in texto:
                raise RuntimeError("CUDA out of memory")
            return {"episodios": 90, "resueltos": 10, "parcial_medio": 0.5}
        r = buscar(evaluar, tokens_aproximados, 0.05, 10, filas.append)
        fallidas = [f for f in filas if f["error"]]
        self.assertTrue(fallidas)
        self.assertTrue(all(f["puntaje"] is None for f in fallidas))
        self.assertNotIn("Costumbres", armar(r["mejor"]["bloques"]))

    def test_puntaje_y_frontera(self):
        self.assertEqual(puntaje({"episodios": 100, "resueltos": 50}, 1000, 0.05), 0.45)
        filas = [{"sha256": "a", "resueltos": 10, "tokens": 500, "puntaje": 1},
                 {"sha256": "b", "resueltos": 12, "tokens": 600, "puntaje": 1},
                 {"sha256": "c", "resueltos": 9, "tokens": 700, "puntaje": 1}]
        self.assertEqual([f["sha256"] for f in frontera(filas)], ["a", "b"])


class ParticionTest(unittest.TestCase):
    def test_particion_reproducible_y_sin_cruce(self):
        p = cargar_particion()
        ids = p["optimizacion"] + p["validacion"]
        self.assertEqual(len(set(ids)), 50)
        self.assertEqual(particionar(ids, p["semilla"], len(p["validacion"])),
                         {"optimizacion": p["optimizacion"], "validacion": p["validacion"]})


class EvaluadorTest(unittest.TestCase):
    def test_juega_y_puntua_solo_los_casos_pedidos(self):
        ids = cargar_particion()["optimizacion"][:2]
        with tempfile.TemporaryDirectory() as carpeta:
            evaluar = Evaluador(ModeloFalso(), cargar_config(), ids, ["original", "b"], Path(carpeta))
            r = evaluar(cargar_prompt("catedra"), "0" * 64)
            self.assertEqual(r["episodios"], 4)
            self.assertIsNone(r["error"])
            for norma in ("original", "b"):
                trazas = (Path(carpeta) / ("0" * 12) / norma / "trazas.jsonl").read_text(encoding="utf-8")
                self.assertEqual(len(trazas.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
