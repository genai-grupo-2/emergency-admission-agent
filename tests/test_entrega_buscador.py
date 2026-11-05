"""Integración real del RAG con entrega/agente/entorno, sin inferencia GPU."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from admision.casos import cargar_casos
from admision.contrato import cargar_entrega
from admision.correr import jugar
from agente.modelo import construir_modelo


RAIZ = Path(__file__).resolve().parents[1]


class EntregaBuscadorTests(unittest.TestCase):
    def test_cinco_herramientas_y_conversaciones_completas_con_las_tres_normas(self):
        casos = [c for c in cargar_casos(RAIZ / "practica/casos.jsonl")
                 if c.puede_responder and c.declarada is not None][:2]
        self.assertEqual(len(casos), 2)
        with patch.dict(os.environ, {"ADMISION_BACKEND": "falso", "ADMISION_CONFIG": "",
                                     "ADMISION_PROMPT": "catedra"}):
            entrega = cargar_entrega(RAIZ / "entrega.py")
            for variante in ("original", "b", "c"):
                with self.subTest(variante=variante), tempfile.TemporaryDirectory() as temporal:
                    with patch("entrega_entrega.construir_modelo", wraps=construir_modelo) as carga:
                        trazas = jugar(entrega, casos, RAIZ / "normas" / variante, Path(temporal))
                        carga.assert_called_once()
                    guardadas = [json.loads(l) for l in (Path(temporal) / "trazas.jsonl").read_text(
                        encoding="utf-8").splitlines()]
                    self.assertEqual(guardadas, trazas)
                    for caso, traza in zip(casos, trazas, strict=True):
                        self.assertEqual(traza["caso"], caso.id)
                        log, mensajes = traza["log"], traza["mensajes"]
                        self.assertEqual([p["herramienta"] for p in log], [
                            "leer_triage", "preguntar", "verificar_afiliacion",
                            "buscar_normativa", "registrar_decision"])
                        self.assertTrue(all(p["valida"] for p in log))
                        self.assertIsNotNone(traza["decision"])
                        self.assertEqual(len(mensajes), 2 + 2 * len(log) - 1)
                        for i, paso in enumerate(log):
                            self.assertEqual(json.loads(mensajes[2 + 2 * i]["content"]),
                                             {"herramienta": paso["herramienta"],
                                              "argumentos": paso["argumentos"]})
                            if i < len(log) - 1:
                                self.assertEqual(mensajes[3 + 2 * i]["content"],
                                                 f"Resultado de {paso['herramienta']}:\n{paso['observacion']}")
                        self.assertIn("NOR-ADM", log[3]["observacion"])

    def test_configuracion_del_rag_llega_al_constructor(self):
        with tempfile.TemporaryDirectory() as temporal:
            config = json.loads((RAIZ / "configuracion.json").read_text(encoding="utf-8"))
            config["buscador"] = {"fragmentacion": "parrafo", "k_entorno": 4, "k1": 1.2, "b": 0.5}
            ruta = Path(temporal) / "config.json"
            ruta.write_text(json.dumps(config), encoding="utf-8")
            with patch.dict(os.environ, {"ADMISION_CONFIG": str(ruta)}):
                entrega = cargar_entrega(RAIZ / "entrega.py")
                buscador = entrega.construir_buscador(RAIZ / "normas/b")
            self.assertEqual((buscador.fragmentacion, buscador.k_entorno, buscador.k1, buscador.b),
                             ("parrafo", 4, 1.2, 0.5))
            self.assertIn("#", buscador.recuperar("documento", 1)[0].id)


if __name__ == "__main__":
    unittest.main()
