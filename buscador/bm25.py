"""Buscador del grupo, basado en el BM25 inicial de Juan.

Lee texto y valores desde ruta_normas. Permite comparar secciones completas
con párrafos sin cambiar la interfaz que usa entrega.py.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from numbers import Real
from pathlib import Path

from admision.normas import cargar_normas


@dataclass(frozen=True)
class Fragmento:
    id: str
    seccion: str
    texto: str


def _entero(nombre: str, valor: int, minimo: int) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"{nombre} debe ser un entero")
    if valor < minimo:
        raise ValueError(f"{nombre} debe ser mayor o igual a {minimo}")


def _tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


class BuscadorBM25:
    def __init__(self, ruta_normas: Path, k_entorno: int = 2, k1: float = 1.5, b: float = 0.75,
                 fragmentacion: str = "seccion"):
        _entero("k_entorno", k_entorno, 1)
        for nombre, valor in (("k1", k1), ("b", b)):
            if isinstance(valor, bool) or not isinstance(valor, Real):
                raise TypeError(f"{nombre} debe ser un numero real")
            if not math.isfinite(valor):
                raise ValueError(f"{nombre} debe ser finito")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("se requiere k1 > 0 y 0 <= b <= 1")
        if fragmentacion not in ("seccion", "parrafo"):
            raise ValueError("fragmentacion debe ser seccion o parrafo")
        self.secciones = cargar_normas(Path(ruta_normas))
        if not self.secciones:
            raise FileNotFoundError(f"no hay secciones NOR-*.md en {ruta_normas}")
        self.k_entorno, self.k1, self.b = k_entorno, k1, b
        self.fragmentacion = fragmentacion
        self.fragmentos = []
        for seccion in self.secciones:
            if fragmentacion == "seccion":
                self.fragmentos.append(Fragmento(seccion.id, seccion.id, seccion.texto))
            else:
                # Conservar cada párrafo completo: el evaluador exige evidencia textual.
                encabezado, *parrafos = re.split(r"\n\s*\n", seccion.cuerpo)
                for numero, parrafo in enumerate(parrafos or [""], 1):
                    texto = "\n\n".join(t for t in (encabezado, parrafo, seccion.valores) if t)
                    self.fragmentos.append(Fragmento(f"{seccion.id}#{numero}", seccion.id, texto))
        self._docs = [Counter(_tokens(s.texto)) for s in self.fragmentos]
        self._largos = [sum(d.values()) for d in self._docs]
        self._medio = sum(self._largos) / len(self._largos)
        df = Counter(t for d in self._docs for t in d)
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _puntaje(self, consulta: list[str], i: int) -> float:
        d, largo, total = self._docs[i], self._largos[i], 0.0
        for t in consulta:
            f = d.get(t, 0)
            if f:
                total += self._idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * largo / self._medio))
        return total

    def recuperar(self, consulta: str, k: int):
        if not isinstance(consulta, str):
            raise TypeError("consulta debe ser texto")
        _entero("k", k, 0)
        q = _tokens(consulta)
        if not q or k == 0:
            return []
        puntajes = [(self._puntaje(q, i), i) for i in range(len(self.fragmentos))]
        orden = sorted((p for p in puntajes if p[0] > 0), key=lambda p: (-p[0], p[1]))
        return [self.fragmentos[i] for _, i in orden[:k]]
