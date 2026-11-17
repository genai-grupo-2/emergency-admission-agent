"""Pruebas de la carga, validación y máscara de pérdida del entrenamiento (sin GPU, con un tokenizador de juguete)."""

import json
import tempfile
import unittest
from pathlib import Path

from agente.prompts import cargar_prompt
from entrenar import datos
from entrenar.config import RAIZ


class TokenizadorDeJuguete:
    """Plantilla parecida a la de Gemma (`<turn>rol\\ncontenido<end>\\n`) y un token por carácter."""

    def __init__(self, estable=True):
        self.estable = estable

    def apply_chat_template(self, mensajes, tokenize=False, add_generation_prompt=False):
        assert not tokenize
        texto = "<bos>"
        for m in mensajes:
            rol = "model" if m["role"] == "assistant" else m["role"]
            contenido = m["content"]
            if not self.estable and m["role"] == "assistant" and m is mensajes[-1] and not add_generation_prompt:
                contenido = contenido.upper()  # una plantilla que cambia el último turno rompe el prefijo
            texto += f"<{rol}>\n{contenido}<end>\n"
        if add_generation_prompt:
            texto += "<model>\n"
        return texto

    def __call__(self, texto, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in texto]}

    def decodificar(self, ids):
        return "".join(chr(i) for i in ids)


def fila(id_, sistema="SISTEMA", grupo=None, paciente="P-1", ultimo=None):
    ultimo = ultimo or json.dumps({"herramienta": "registrar_decision", "argumentos": {"registro": "normal"}})
    return {"id": id_, "grupo": grupo or f"g-{id_}", "huella_conversacion": f"h-{id_}", "paciente_id": paciente,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": "Ingresó el paciente."},
                {"role": "assistant", "content": '{"herramienta": "leer_triage"}'},
                {"role": "user", "content": "Resultado de leer_triage:\nPaciente: X, 70 años. Motivo: dolor torácico"},
                {"role": "assistant", "content": ultimo},
            ]}


class TestValidar(unittest.TestCase):
    def test_datos_correctos(self):
        resumen = datos.validar([fila("a"), fila("b")], [fila("c")], "SISTEMA")
        self.assertEqual((resumen["train"], resumen["validacion"]), (2, 1))

    def test_prompt_distinto_se_rechaza(self):
        with self.assertRaisesRegex(datos.DatosInvalidos, "no es el prompt"):
            datos.validar([fila("a", sistema="OTRO")], [fila("c")], "SISTEMA")

    def test_ultima_respuesta_tiene_que_ser_registrar_decision(self):
        malo = fila("a", ultimo='{"herramienta": "preguntar"}')
        with self.assertRaisesRegex(datos.DatosInvalidos, "registrar_decision"):
            datos.validar([malo], [fila("c")], "SISTEMA")

    def test_filtracion_entre_particiones(self):
        with self.assertRaisesRegex(datos.DatosInvalidos, "grupo"):
            datos.validar([fila("a", grupo="g")], [fila("c", grupo="g")], "SISTEMA")

    def test_reproducir_un_caso_de_practica_se_rechaza_pero_un_id_igual_no(self):
        caso = {"id": "pev-1", "paciente_id": "P-1", "edad": 70, "motivo": "dolor torácico"}
        with self.assertRaisesRegex(datos.DatosInvalidos, "pev-1"):
            datos.validar([fila("a")], [fila("c", paciente="P-9")], "SISTEMA", [caso])
        otro = dict(caso, edad=31)  # mismo id de paciente, otro paciente: casualidad, no filtración
        resumen = datos.validar([fila("a")], [fila("c", paciente="P-9")], "SISTEMA", [otro])
        self.assertEqual(resumen["ids_de_paciente_que_coinciden_con_practica_sin_ser_el_mismo_caso"], 1)


class TestTokenizar(unittest.TestCase):
    def test_la_mascara_cubre_solo_las_respuestas_del_asistente(self):
        tok = TokenizadorDeJuguete()
        f = fila("a")
        e = datos.tokenizar(tok, f)
        supervisado = tok.decodificar([i for i, m in zip(e.ids, e.mascara) if m])
        esperado = "".join(f"{m['content']}<end>\n" for m in f["messages"] if m["role"] == "assistant")
        self.assertEqual(supervisado, esperado)

    def test_plantilla_inestable_corta_en_vez_de_correr_la_mascara(self):
        with self.assertRaisesRegex(datos.DatosInvalidos, "prefijo-estable"):
            datos.tokenizar(TokenizadorDeJuguete(estable=False), fila("a"))

    def test_largos_se_descartan_y_se_cuentan(self):
        tok = TokenizadorDeJuguete()
        ejemplos, est = datos.construir_ejemplos(tok, [fila("a"), fila("b", sistema="S" * 5000)], max_tokens=1000)
        self.assertEqual([e.id for e in ejemplos], ["a"])
        self.assertEqual(est["descartadas_por_largo"], ["b"])
        self.assertEqual(est["usadas"], 1)


class TestDatosDelRepositorio(unittest.TestCase):
    """Los archivos reales que se van a usar para entrenar."""

    @classmethod
    def setUpClass(cls):
        cls.prompt = cargar_prompt("catedra")
        cls.train = datos.leer_conversaciones(RAIZ / "datos/conversaciones/train.jsonl")
        cls.val = datos.leer_conversaciones(RAIZ / "datos/conversaciones/validacion.jsonl")
        cls.casos = [json.loads(linea) for linea in (RAIZ / "practica/casos.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_validan_contra_el_prompt_de_la_catedra_y_sin_filtraciones(self):
        resumen = datos.validar(self.train, self.val, self.prompt, self.casos)
        self.assertEqual((resumen["train"], resumen["validacion"]), (2176, 224))

    def test_con_el_prompt_optimizado_no_validan(self):
        with self.assertRaises(datos.DatosInvalidos):
            datos.validar(self.train, self.val, cargar_prompt("optimizado"), self.casos)

    def test_la_mascara_de_las_conversaciones_reales(self):
        tok = TokenizadorDeJuguete()
        for f in self.train[:20]:
            e = datos.tokenizar(tok, f)
            supervisado = tok.decodificar([i for i, m in zip(e.ids, e.mascara) if m])
            esperado = "".join(f"{m['content']}<end>\n" for m in f["messages"] if m["role"] == "assistant")
            self.assertEqual(supervisado, esperado)


class TestLectura(unittest.TestCase):
    def test_json_roto_dice_archivo_y_linea(self):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "x.jsonl"
            ruta.write_text('{"a": 1}\n{roto\n', encoding="utf-8")
            with self.assertRaisesRegex(datos.DatosInvalidos, ":2:"):
                datos.leer_conversaciones(ruta)


if __name__ == "__main__":
    unittest.main()
