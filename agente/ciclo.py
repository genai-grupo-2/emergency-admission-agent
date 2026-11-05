"""El ciclo del agente: juega un lote de casos con el protocolo JSON del ejemplo de la cátedra.

En cada vuelta hay una sola llamada al modelo con todas las partidas activas. El modelo responde
`{"herramienta": ..., "argumentos": {...}}` y el resultado vuelve como `Resultado de <herramienta>:\\n<observación>`.

Qué agrega sobre `admision.ejemplo.AgenteJSON`:
- valida el nombre de la herramienta y que los argumentos sean un objeto antes de gastar una llamada del caso;
- avisa cuántas llamadas quedan cuando faltan pocas y, con una sola, sólo acepta `registrar_decision`;
- un error del modelo o del entorno en un caso cierra ese caso, no el lote (queda en `informe`);
- devuelve siempre las conversaciones completas, en el orden de `entornos`.

No importa torch ni transformers: el modelo es cualquier función `modelo_lote(conversaciones) -> respuestas`."""

from admision.ejemplo import extraer_json, primer_mensaje

HERRAMIENTAS = ("leer_triage", "preguntar", "verificar_afiliacion", "buscar_normativa", "registrar_decision")
CIERRE = "registrar_decision"
NO_ENTENDI = ('No entendí tu respuesta. Respondé solo con un objeto JSON: '
              '{"herramienta": "<nombre>", "argumentos": {...}}')


class _Partida:
    def __init__(self, entorno, sistema: str, agente: "Agente"):
        self.entorno, self.agente = entorno, agente
        self.mensajes = [{"role": "system", "content": sistema},
                         {"role": "user", "content": primer_mensaje(entorno.paciente_id)}]
        self.llamadas = self.turnos = self.sin_json = 0
        self.activa, self.fin, self.error = True, None, None

    def terminar(self, fin: str, error: str | None = None) -> None:
        self.activa, self.fin, self.error = False, fin, error

    def _resultado(self, herramienta: str, observacion: str) -> None:
        self.mensajes.append({"role": "user", "content": f"Resultado de {herramienta}:\n{observacion}"})

    def recibir(self, respuesta) -> None:
        self.turnos += 1
        respuesta = respuesta if isinstance(respuesta, str) else str(respuesta)
        self.mensajes.append({"role": "assistant", "content": respuesta})
        self._procesar(respuesta)
        if self.activa and self.turnos >= self.agente.max_turnos:
            self.terminar("max_turnos")

    def _procesar(self, respuesta: str) -> None:
        a = self.agente
        obj = extraer_json(respuesta)
        if obj is None:
            self.sin_json += 1
            if self.sin_json >= a.max_sin_json:
                self.terminar("sin_json")
            else:
                self.mensajes.append({"role": "user", "content": NO_ENTENDI})
            return
        self.sin_json = 0
        herramienta, argumentos = str(obj.get("herramienta", "")), obj.get("argumentos", {})
        restantes = a.max_llamadas - self.llamadas
        if herramienta not in HERRAMIENTAS:
            return self._resultado(herramienta, f"Error: no existe la herramienta {herramienta!r}. "
                                                f"Las herramientas son: {', '.join(HERRAMIENTAS)}.")
        if not isinstance(argumentos, dict):
            return self._resultado(herramienta, 'Error: "argumentos" tiene que ser un objeto JSON {...}.')
        if restantes <= 1 and herramienta != CIERRE:
            return self._resultado(herramienta, "Error: te queda una sola llamada y tiene que ser registrar_decision.")
        try:
            observacion, termino = self.entorno.paso(herramienta, argumentos)
        except Exception as e:  # un entorno roto cierra este caso y no el lote
            return self.terminar("error_entorno", f"{type(e).__name__}: {e}")
        self.llamadas += 1
        if termino:
            registrada = herramienta == CIERRE and observacion == "Ficha registrada."
            return self.terminar("registrada" if registrada else "terminado")
        restantes = a.max_llamadas - self.llamadas
        if restantes <= a.aviso_restantes:
            observacion += (f"\n\nTe quedan {restantes} llamadas a herramientas. Registrá la ficha con "
                            "registrar_decision antes de quedarte sin llamadas.")
        self._resultado(herramienta, observacion)


class Agente:
    def __init__(self, modelo_lote, sistema: str, max_llamadas: int = 40, max_sin_json: int = 3,
                 aviso_restantes: int = 5, max_turnos: int = 60):
        if not sistema.strip():
            raise ValueError("el mensaje de sistema está vacío")
        self.modelo_lote, self.sistema = modelo_lote, sistema
        self.max_llamadas, self.max_sin_json = max_llamadas, max_sin_json
        self.aviso_restantes, self.max_turnos = aviso_restantes, max_turnos
        self.informe: list[dict] = []

    def _responder(self, activas: list[_Partida]) -> None:
        try:
            respuestas = self.modelo_lote([p.mensajes for p in activas])
            if len(respuestas) != len(activas):
                raise ValueError(f"el modelo devolvió {len(respuestas)} respuestas para {len(activas)} conversaciones")
        except Exception:  # el lote falló: se reintenta caso por caso para aislar el que lo rompe
            for p in activas:
                try:
                    (respuesta,) = self.modelo_lote([p.mensajes])
                except Exception as e:
                    p.terminar("error_modelo", f"{type(e).__name__}: {e}")
                else:
                    p.recibir(respuesta)
            return
        for p, respuesta in zip(activas, respuestas, strict=True):
            p.recibir(respuesta)

    def jugar_lote(self, entornos: list) -> list[list[dict]]:
        partidas = [_Partida(e, self.sistema, self) for e in entornos]
        while activas := [p for p in partidas if p.activa]:
            self._responder(activas)
        self.informe = [{"paciente_id": p.entorno.paciente_id, "fin": p.fin, "llamadas": p.llamadas,
                         "turnos": p.turnos, "error": p.error} for p in partidas]
        return [p.mensajes for p in partidas]
