import unittest
from pathlib import Path

from datos.clasificar import clasificar_fila
from datos.normas import cargar_parametros


class ClasificacionTests(unittest.TestCase):
    def test_error_escrito_prevalece_sobre_ruido(self):
        fila = {
            "id": "PRUEBA", "edad": "30", "nivel": "4", "documento_tipo": "", "documento_numero": "",
            "motivo": "cefalea", "sospecha_sepsis": "no", "llegada": "por sus propios medios",
            "lesion_trabajo": "no", "credenciales": "", "cobertura_declarada": "ninguna",
            "entidad_verificada": "", "numero_verificado": "", "puede_responder": "no", "acompanante": "",
            "aviso_al_voluntariado": "sí",
        }
        ficha = {"registro": "definitivo", "numero_documento": None, "box_antes_del_registro": False,
                 "circuito": "ninguno", "plazo_circuito_min": None, "cobertura": "sin_cobertura",
                 "entidad_a_notificar": None, "aviso_al_voluntariado": True}
        traza = {"ficha": ficha, "pasos": []}
        parametros = cargar_parametros(Path(__file__).resolve().parents[1] / "normas/original")
        costumbres = {"voluntariado": {"edad_minima": 75}, "doble_credencial": {"preferencia": "prepaga"}}
        self.assertEqual(clasificar_fila(fila, traza, parametros, costumbres)["tipo"], "error")
        ficha["registro"] = "provisorio"
        self.assertEqual(clasificar_fila(fila, traza, parametros, costumbres)["tipo"], "ruido")
        ficha["aviso_al_voluntariado"] = False
        fila["aviso_al_voluntariado"] = "no"
        self.assertEqual(clasificar_fila(fila, traza, parametros, costumbres)["tipo"], "correcta")


if __name__ == "__main__":
    unittest.main()
