import copy
import json
import unittest

from datos.conversaciones import convertir_traza, preparar_registro


class ConversacionesTests(unittest.TestCase):
    def setUp(self):
        self.ficha = {"registro": "provisorio", "numero_documento": None, "box_antes_del_registro": True,
                      "circuito": "ecg", "plazo_circuito_min": 99, "cobertura": "sin_cobertura",
                      "entidad_a_notificar": None, "aviso_al_voluntariado": False}
        self.traza = {"id": "E-001", "paciente_id": "P-1234", "ficha": copy.deepcopy(self.ficha), "pasos": [
            {"orden": 1, "herramienta": "leer_triage", "argumentos": {"paciente_id": "P-1234"}, "resultado": "Paciente: Ana Pérez, 30 años.\nDolor torácico."},
            {"orden": 2, "herramienta": "buscar_normativa", "argumentos": {"consulta": "ECG"}, "resultado": "P-TDE-1 = 99 min.\nTexto de esta traza."},
            {"orden": 3, "herramienta": "registrar_decision", "argumentos": copy.deepcopy(self.ficha), "resultado": "Ficha registrada."},
        ]}

    def test_preserva_llamadas_resultados_y_valores_de_esa_traza(self):
        antes = copy.deepcopy(self.traza)
        mensajes = convertir_traza(self.traza, "Sistema de prueba")
        self.assertEqual([m["role"] for m in mensajes], ["system", "user", "assistant", "user", "assistant", "user", "assistant"])
        for paso, mensaje in zip(self.traza["pasos"], mensajes[2::2], strict=True):
            self.assertEqual(json.loads(mensaje["content"]), {"herramienta": paso["herramienta"], "argumentos": paso["argumentos"]})
        self.assertEqual(mensajes[5]["content"], "Resultado de buscar_normativa:\nP-TDE-1 = 99 min.\nTexto de esta traza.")
        self.assertEqual(self.traza, antes)
        self.assertNotIn("Ficha registrada.", [m["content"] for m in mensajes])

    def test_rechaza_pasos_despues_de_registrar(self):
        self.traza["pasos"].append(copy.deepcopy(self.traza["pasos"][0]))
        with self.assertRaises(ValueError):
            convertir_traza(self.traza, "Sistema")

    def test_rechaza_una_ficha_inventada(self):
        self.traza["ficha"]["plazo_circuito_min"] = 10
        with self.assertRaisesRegex(ValueError, "no coincide"):
            convertir_traza(self.traza, "Sistema")

    def test_prompt_nuevo_no_cambia_las_llamadas(self):
        inicial = convertir_traza(self.traza, "Original")
        final = convertir_traza(self.traza, "Prompt de Juan")
        self.assertNotEqual(inicial[0], final[0])
        self.assertEqual(inicial[1:], final[1:])

    def test_agrupa_copias_con_otro_nombre_e_id_de_paciente(self):
        copia = copy.deepcopy(self.traza)
        copia.update(id="E-002", paciente_id="P-9999")
        copia["pasos"][0]["argumentos"]["paciente_id"] = "P-9999"
        copia["pasos"][0]["resultado"] = copia["pasos"][0]["resultado"].replace("Ana Pérez", "Luis Gómez")
        a = preparar_registro(self.traza, "entrenamiento", "Sistema")
        b = preparar_registro(copia, "entrenamiento", "Sistema")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(a["huella_conversacion"], b["huella_conversacion"])
        copia["pasos"][1]["resultado"] = "P-TDE-1 = 20 min."
        self.assertNotEqual(a["huella_conversacion"], preparar_registro(copia, "entrenamiento", "Sistema")["huella_conversacion"])


if __name__ == "__main__":
    unittest.main()
