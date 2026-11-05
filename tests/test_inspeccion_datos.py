"""Pruebas de corrupción y correspondencia de las fuentes, sin modelos ni red."""

import contextlib
import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from datos.inspeccionar import COLUMNAS, CSV, HISTORIAL, REFERENCIA, inspeccionar, main


class InspeccionTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        ficha = {
            "registro": "provisorio", "numero_documento": None,
            "box_antes_del_registro": False, "circuito": "ninguno",
            "plazo_circuito_min": None, "cobertura": "sin_cobertura",
            "entidad_a_notificar": None, "aviso_al_voluntariado": False,
        }
        self.filas, self.trazas = [], []
        for i in (1, 2):
            fila = dict.fromkeys(COLUMNAS, "")
            fila.update({
                "id": f"H-{i:04d}", "fecha": f"2026-03-01 0{i}:00", "operador": "OP-01",
                "edad": "30", "nivel": "4", "motivo": "cefalea", "nota_enfermeria": f"Dolor desde hace {i} horas.",
                "sospecha_sepsis": "no", "llegada": "por sus propios medios",
                "puede_responder": "sí", "lesion_trabajo": "no", "registro": "provisorio",
                "box_antes_del_registro": "no", "circuito": "ninguno", "cobertura": "sin_cobertura",
                "aviso_al_voluntariado": "no",
            })
            self.filas.append(fila)
            self.trazas.append({
                "id": fila["id"], "fecha": fila["fecha"], "operador": fila["operador"],
                "paciente_id": "P-1000", "ficha": copy.deepcopy(ficha),
                "pasos": [
                    {"orden": 1, "herramienta": "leer_triage", "argumentos": {"paciente_id": "P-1000"}, "resultado": fila["nota_enfermeria"]},
                    {"orden": 2, "herramienta": "registrar_decision", "argumentos": copy.deepcopy(ficha), "resultado": "Ficha registrada."},
                ],
            })
        self.referencia = copy.deepcopy(self.trazas[:1])
        self.referencia[0] = {k: v for k, v in self.referencia[0].items() if k not in {"fecha", "operador"}}
        self.referencia[0]["id"] = "E-001"
        self.guardar()

    def guardar(self):
        for nombre in (CSV, HISTORIAL, REFERENCIA):
            (self.raiz / nombre).parent.mkdir(parents=True, exist_ok=True)
        with (self.raiz / CSV).open("w", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
            escritor.writeheader()
            escritor.writerows(self.filas)
        for nombre, trazas in ((HISTORIAL, self.trazas), (REFERENCIA, self.referencia)):
            (self.raiz / nombre).write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in trazas), encoding="utf-8")

    def informe(self):
        return inspeccionar(self.raiz, n_historial=2, n_referencia=1)

    def codigos(self):
        return {e["codigo"] for e in self.informe()["errores"]}

    def test_nulos_y_pacientes_repetidos_no_son_corrupcion(self):
        informe = self.informe()
        self.assertEqual(informe["errores"], [])
        self.assertTrue(informe["correspondencia"]["ids_en_el_mismo_orden"])
        self.assertEqual(informe["correspondencia"]["fichas_comparadas"], 2)
        self.assertEqual(informe["archivos"][CSV]["vacios_por_columna"]["documento_numero"], 2)
        self.assertEqual(informe["advertencias"][0]["codigo"], "paciente_id_repetido")

    def test_detecta_reordenamiento_sin_confundir_fichas(self):
        self.trazas.reverse()
        self.guardar()
        self.assertIn("orden_historial", self.codigos())
        self.assertNotIn("metadatos_no_coinciden", self.codigos())

    def test_detecta_id_duplicado_y_id_faltante_aun_con_cantidad_correcta(self):
        self.trazas[1]["id"] = self.trazas[0]["id"]
        self.guardar()
        self.assertTrue({"ids_duplicados", "cobertura_ids"} <= self.codigos())

    def test_detecta_divergencia_entre_csv_y_traza(self):
        self.filas[0]["box_antes_del_registro"] = "sí"
        self.guardar()
        self.assertIn("csv_difiere_ficha", self.codigos())

    def test_detecta_decision_final_distinta_de_la_ficha(self):
        self.trazas[0]["pasos"][-1]["argumentos"]["numero_documento"] = "12345678"
        self.guardar()
        self.assertIn("registro_difiere_ficha", self.codigos())

    def test_no_acepta_uno_como_booleano_json(self):
        self.trazas[0]["ficha"]["aviso_al_voluntariado"] = 1
        self.guardar()
        self.assertTrue({"tipo_ficha", "registro_difiere_ficha", "csv_difiere_ficha"} <= self.codigos())

    def test_detecta_orden_y_llamadas_posteriores_al_cierre(self):
        self.trazas[0]["pasos"].append(copy.deepcopy(self.trazas[0]["pasos"][0]))
        self.guardar()
        self.assertTrue({"orden_pasos", "inicio_fin_traza"} <= self.codigos())

    def test_reporta_json_roto_en_vez_de_omitirlo_silenciosamente(self):
        with (self.raiz / REFERENCIA).open("a", encoding="utf-8") as f:
            f.write('{"id":\n')
        self.assertIn("json_invalido", self.codigos())

    def test_rechaza_claves_json_repetidas(self):
        ruta = self.raiz / REFERENCIA
        ruta.write_text(ruta.read_text(encoding="utf-8").replace('"id": "E-001"', '"id": "E-001", "id": "E-002"'), encoding="utf-8")
        self.assertIn("json_invalido", self.codigos())

    def test_reporta_columna_faltante_y_archivo_faltante(self):
        with (self.raiz / CSV).open("a", encoding="utf-8") as f:
            f.write("H-0003\n")
        (self.raiz / REFERENCIA).unlink()
        self.assertTrue({"ancho_csv", "archivo_inaccesible"} <= self.codigos())

    def test_reporta_argumentos_malformados_sin_caerse(self):
        self.trazas[0]["pasos"].insert(1, {
            "orden": 2, "herramienta": "preguntar",
            "argumentos": {"paciente_id": "P-OTRO", "a_quien": [], "tema": "invalido"},
            "resultado": "Error.",
        })
        self.guardar()
        self.assertTrue({"tipo_argumento", "dominio_preguntar", "paciente_distinto"} <= self.codigos())

    def test_diagnostico_reproducible_y_fuentes_sin_cambios(self):
        antes = {n: (self.raiz / n).read_bytes() for n in (CSV, HISTORIAL, REFERENCIA)}
        self.assertEqual(self.informe(), self.informe())
        self.assertEqual(antes, {n: (self.raiz / n).read_bytes() for n in antes})

    def test_cli_no_puede_sobrescribir_una_fuente(self):
        antes = (self.raiz / CSV).read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["--raiz", str(self.raiz), "--salida", CSV])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(antes, (self.raiz / CSV).read_bytes())


if __name__ == "__main__":
    unittest.main()
