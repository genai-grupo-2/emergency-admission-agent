"""Casos límite de las reglas escritas, sin respuestas de evaluación."""

import unittest
from pathlib import Path

from datos.normas import cargar_parametros, comprobar_normas


class NormasTests(unittest.TestCase):
    def setUp(self):
        self.parametros = cargar_parametros(Path(__file__).resolve().parents[1] / "normas/original")
        self.fila = {
            "id": "CASO-DE-PRUEBA", "edad": "30", "nivel": "4", "documento_tipo": "DNI",
            "documento_numero": "12.345.678", "motivo": "cefalea", "sospecha_sepsis": "no",
            "llegada": "por sus propios medios", "lesion_trabajo": "no", "credenciales": "",
            "cobertura_declarada": "ninguna", "art_declarada": "", "entidad_verificada": "",
            "numero_verificado": "", "respuesta_verificacion": "", "puede_responder": "sí", "acompanante": "",
        }
        self.traza = {
            "ficha": {"registro": "definitivo", "numero_documento": "12.345.678", "box_antes_del_registro": False,
                      "circuito": "ninguno", "plazo_circuito_min": None, "cobertura": "sin_cobertura",
                      "entidad_a_notificar": None, "aviso_al_voluntariado": False},
            "pasos": [{"orden": 2, "herramienta": "preguntar", "argumentos": {"tema": "cobertura", "a_quien": "paciente"}}],
        }

    def errores(self):
        return comprobar_normas(self.fila, self.traza, self.parametros)

    def campos(self):
        return {e["campo"] for e in self.errores()}

    def test_no_convierte_box_permitido_en_prohibido(self):
        self.assertEqual(self.errores(), [])
        self.traza["ficha"]["box_antes_del_registro"] = True
        self.assertEqual(self.errores(), [])

    def test_edad_en_umbral_prevalece_sobre_nivel_no_urgente(self):
        self.fila["edad"] = str(self.parametros["P-ADM-2"])
        self.assertIn("box_antes_del_registro", self.campos())
        self.fila["edad"] = str(self.parametros["P-ADM-2"] - 1)
        self.assertNotIn("box_antes_del_registro", self.campos())

    def test_pasaporte_urgente_conserva_numero_pero_es_provisorio(self):
        self.fila.update(documento_tipo="pasaporte", documento_numero="ABC123", nivel=str(self.parametros["P-ADM-3"]))
        self.traza["ficha"].update(numero_documento="ABC123", box_antes_del_registro=True)
        self.assertEqual(self.campos(), {"registro"})
        self.traza["ficha"]["registro"] = "provisorio"
        self.assertEqual(self.errores(), [])

    def test_sepsis_posible_ambulancia_aplica_ambas_reglas(self):
        self.fila.update(motivo="sospecha de sepsis", sospecha_sepsis="posible, sin signos de shock", llegada="en ambulancia")
        self.traza["ficha"].update(circuito="codigo_sepsis", plazo_circuito_min=self.parametros["P-TDE-4"] - self.parametros["P-TDE-5"])
        self.assertEqual(self.errores(), [])
        self.traza["ficha"]["plazo_circuito_min"] = self.parametros["P-TDE-4"]
        self.assertEqual(self.campos(), {"plazo_circuito_min"})

    def afiliacion(self, numero="123-7", respuesta="inactiva"):
        self.fila.update(credenciales=f"Entidad de prueba (obra social) {numero}", entidad_verificada="Entidad de prueba",
                         numero_verificado=numero, respuesta_verificacion=respuesta)
        self.traza["pasos"] = [{"orden": 3, "herramienta": "verificar_afiliacion", "argumentos": {"entidad": "Entidad de prueba", "numero_afiliado": numero}}]

    def test_terminacion_reservada_notifica_incluso_inactiva(self):
        self.afiliacion(numero="123-" + str(self.parametros["P-COB-2"]))
        self.assertEqual(self.campos(), {"entidad_a_notificar"})
        self.traza["ficha"]["entidad_a_notificar"] = "Entidad de prueba"
        self.assertEqual(self.errores(), [])

    def test_activa_no_reservada_conserva_cobertura(self):
        self.afiliacion(numero="123-0", respuesta="activa")
        self.traza["ficha"].update(cobertura="obra_social", entidad_a_notificar="Entidad de prueba")
        self.assertEqual(self.errores(), [])

    def test_art_prevalece_sobre_credencial_y_terminacion_reservada(self):
        self.afiliacion()
        self.fila.update(lesion_trabajo="trabajando", art_declarada="ART de prueba CUIL 20-123-7",
                         entidad_verificada="ART de prueba", numero_verificado="20-123-7", respuesta_verificacion="activa")
        self.traza["pasos"] = [
            {"orden": 2, "herramienta": "preguntar", "argumentos": {"tema": "art", "a_quien": "paciente"}},
            {"orden": 3, "herramienta": "verificar_afiliacion", "argumentos": {"entidad": "ART de prueba", "numero_afiliado": "20-123-7"}},
        ]
        self.traza["ficha"].update(cobertura="art", entidad_a_notificar="ART de prueba")
        self.assertEqual(self.errores(), [])
        self.traza["pasos"].append({"orden": 4, "herramienta": "verificar_afiliacion", "argumentos": {"entidad": "Entidad de prueba", "numero_afiliado": "123-7"}})
        self.assertIn("verificacion", self.campos())

    def test_paciente_sin_interlocutor_no_requiere_pregunta(self):
        self.fila["puede_responder"] = "no"
        self.traza["pasos"] = []
        self.assertEqual(self.errores(), [])

    def test_consulta_debe_preceder_verificacion(self):
        self.afiliacion(numero="123-0", respuesta="activa")
        self.fila.update(credenciales="", cobertura_declarada="Entidad de prueba (obra social) 123-0")
        self.traza["ficha"].update(cobertura="obra_social", entidad_a_notificar="Entidad de prueba")
        self.traza["pasos"].append({"orden": 4, "herramienta": "preguntar", "argumentos": {"tema": "cobertura", "a_quien": "paciente"}})
        self.assertEqual(self.campos(), {"preguntar"})

    def test_parametros_distintos_cambian_el_criterio(self):
        self.fila["edad"] = "65"
        self.assertNotIn("box_antes_del_registro", self.campos())
        self.parametros["P-ADM-2"] = 60
        self.assertIn("box_antes_del_registro", self.campos())

    def test_circuitos_simultaneos_se_revisan_sin_inventar_prioridad(self):
        self.fila.update(motivo="dolor torácico", sospecha_sepsis="probable")
        with self.assertRaisesRegex(ValueError, "simultáneos"):
            self.errores()


if __name__ == "__main__":
    unittest.main()
