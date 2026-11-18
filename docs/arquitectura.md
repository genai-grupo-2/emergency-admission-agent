# Arquitectura: modelo, agente, herramientas y buscador

Cómo se conectan las piezas cuando se juega un caso. Lo que está en `admision/` es el kit de la cátedra y no se
modifica. El resto es del grupo.

```mermaid
flowchart LR
    subgraph kit["admision/ (kit de la cátedra)"]
        correr["admision.correr<br/>jugar → puntuar"]
        entorno["Entorno por caso<br/>admision/entorno.py"]
        comparar["admision/comparar.py<br/>8 campos + verificación = 9 controles"]
        subgraph herramientas["5 herramientas"]
            triage["leer_triage"]
            preguntar["preguntar"]
            verificar["verificar_afiliacion"]
            buscar["buscar_normativa"]
            registrar["registrar_decision"]
        end
    end

    subgraph grupo["Entrega del grupo"]
        entrega["entrega.py<br/>construir_buscador · construir_agente"]
        config["configuracion.json<br/>(+ variables ADMISION_*)"]
        agente["Agente<br/>agente/ciclo.py · jugar_lote"]
        prompt["Mensaje de sistema<br/>prompts/catedra.txt"]
        modelo["ModeloHF<br/>agente/modelo.py<br/>Gemma 4 E4B (base o SFT)"]
        bm25["BuscadorBM25<br/>buscador/bm25.py<br/>una sección por fragmento, k=2"]
        normas[("normas/original · b · c")]
    end

    correr --> entrega
    config --> entrega
    entrega --> agente
    entrega --> bm25
    prompt --> agente
    modelo <-->|"lote de conversaciones → una respuesta JSON por caso"| agente
    agente <-->|"{herramienta, argumentos} → «Resultado de …»"| entorno
    entorno --- herramientas
    buscar -->|"recuperar(consulta, k_entorno)"| bm25
    normas --> bm25
    registrar -->|"ficha"| correr
    correr --> comparar
```

## Un caso, paso a paso

1. `admision.correr` arma un `Entorno` por caso y le pasa a la entrega sólo el id del paciente y una función
   `paso(herramienta, argumentos)`. El agente nunca ve el caso ni las fichas esperadas.
2. `entrega.py` lee `configuracion.json`: modelo y revisión, prompt, parámetros del buscador y límites del agente.
   Cualquiera se puede pisar con variables `ADMISION_*` (`agente/config.py`). Así se evalúa cada condición de la
   matriz sin tocar el código.
3. En cada vuelta, el `Agente` llama una vez al modelo con todas las conversaciones activas. Cada respuesta es un
   objeto `{"herramienta": ..., "argumentos": {...}}`. El entorno la ejecuta y el resultado vuelve como mensaje del
   usuario.
4. `buscar_normativa` llama a `recuperar(consulta, k_entorno)` del buscador del grupo, que devuelve las dos secciones
   de las normas de esa corrida (`original`, `b` o `c`) que más se parecen a la consulta. Por eso los plazos que cambian
   entre versiones se buscan en vez de memorizarse.
5. `registrar_decision` cierra el caso con la ficha. Después, `puntuar` la compara con la esperada y da los 9
   controles: los 8 campos de la ficha y si se verificó la afiliación correcta.

## Límites del agente

Salen de `configuracion.json` (`agente`): como máximo 40 llamadas a herramientas, 3 respuestas seguidas sin JSON válido
y 60 turnos. Cuando quedan 5 llamadas, el agente avisa. Con una sola, sólo acepta `registrar_decision`. Si un caso
falla, se cierra ese caso y el resto del lote sigue.
