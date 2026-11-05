import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from datos.clasificar import sha256, sha256_lf
from datos.verificar import verificar


class HuellasTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)

    def test_windows_linux_conservan_huella_de_fuente_pero_no_ocultan_cambios(self):
        ruta = self.raiz / "fuente.txt"
        ruta.write_bytes(b"primera\nsegunda\n")
        original = sha256(ruta)
        ruta.write_bytes(b"primera\r\nsegunda\r\n")
        self.assertNotEqual(original, sha256(ruta))
        self.assertEqual(original, sha256_lf(ruta))
        ruta.write_bytes(b"primera\r\notra segunda\r\n")
        self.assertNotEqual(original, sha256_lf(ruta))

    def test_verificador_rechaza_rutas_fuera_del_repositorio(self):
        (self.raiz / "datos").mkdir()
        documento = {"fuentes_sha256_lf": {"../fuera.txt": "no-leer"}, "codigo_sha256_lf": {}}
        for nombre in ("manifiesto.json", "resumen_clasificacion.json"):
            (self.raiz / "datos" / nombre).write_text(json.dumps(documento), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fuera del repositorio"):
            verificar(self.raiz)

    def test_verificador_se_detiene_si_cambia_una_fuente(self):
        (self.raiz / "datos").mkdir()
        (self.raiz / "fuente.txt").write_bytes(b"contenido alterado\n")
        documento = {"fuentes_sha256_lf": {"fuente.txt": hashlib.sha256(b"original\n").hexdigest()}, "codigo_sha256_lf": {}}
        for nombre in ("manifiesto.json", "resumen_clasificacion.json"):
            (self.raiz / "datos" / nombre).write_text(json.dumps(documento), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fuente o el código"):
            verificar(self.raiz)


if __name__ == "__main__":
    unittest.main()
