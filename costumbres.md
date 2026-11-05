# Costumbres inferidas del historial

Generado con `python -X utf8 -m datos.clasificar`. Evidencia completa y búsqueda del umbral en `datos/evidencia_costumbres.json`. Se consideran sólo las filas que no violan las normas escritas; una violación escrita siempre se clasifica como `error`, aunque también se aparte de una costumbre.

Estas son inferencias sobre lo que suelen hacer los operadores. No son normas de la cátedra ni mediciones de calidad de un modelo. Los contraejemplos se interpretan como ruido únicamente después de comprobar que no violan una norma. No se usaron respuestas de evaluación.

## 1. Avisar al voluntariado para pacientes mayores que llegan solos

El patrón con más coincidencias es avisar cuando la edad es al menos 75 años y el paciente no tiene acompañante. En los demás casos, no avisar. El umbral se obtiene buscando entre todas las edades observadas y la siguiente; no se copia de un parámetro normativo. La hipótesis explorada combina edad y ausencia de acompañante. Se exige un mínimo de 20 ejemplos y 80% de apoyo en cada grupo; si hay empate de umbrales, el proceso pide revisión.

El mejor umbral coincide en 1609 de 1760 filas, frente a 1461 si nunca se avisa. El segundo umbral candidato es 76, con 1599 coincidencias.

### Pacientes en los que el patrón indica avisar

Coinciden 167 de 186 filas.

Ejemplos de apoyo: H-0013, H-0016, H-0036, H-0044, H-0045, H-0063, H-0088, H-0094, H-0100, H-0114, H-0146, H-0171.

Ejemplos que se apartan: H-0077, H-0127, H-0182, H-0353, H-0449, H-0617, H-0644, H-0907, H-1088, H-1093, H-1116, H-1452.

Las listas completas están en `datos/evidencia_costumbres.json`.

### Resto de los pacientes

Coinciden 1442 de 1574 filas.

Ejemplos de apoyo: H-0001, H-0002, H-0003, H-0004, H-0007, H-0008, H-0011, H-0012, H-0015, H-0017, H-0018, H-0019.

Ejemplos que se apartan: H-0005, H-0006, H-0009, H-0053, H-0056, H-0067, H-0093, H-0108, H-0110, H-0140, H-0142, H-0150.

Las listas completas están en `datos/evidencia_costumbres.json`.

## 2. Preferir la prepaga si se presentan dos credenciales

Si se presentan una obra social y una prepaga, los operadores suelen verificar la prepaga. La selección se observa en la entidad verificada; no se deduce del campo final `cobertura`, que puede ser `sin_cobertura` por una afiliación inactiva o reservada. La regla no se aplica a accidentes laborales: ahí corresponde la ART por norma escrita. Las normas no establecen prioridad entre la obra social y la prepaga.

Coinciden 163 de 172 filas.

Ejemplos de apoyo: H-0011, H-0021, H-0056, H-0075, H-0086, H-0087, H-0088, H-0099, H-0114, H-0125, H-0153, H-0157.

Ejemplos que se apartan: H-0334, H-0404, H-0408, H-0480, H-0792, H-0881, H-1190, H-1467, H-1520.

Las listas completas están en `datos/evidencia_costumbres.json`.

## Límites y casos que requieren revisión

El umbral y la preferencia fueron elegidos explorando este historial completo; sus porcentajes no son una evaluación independiente ni prueban una política universal del hospital. La evidencia permite auditar la hipótesis y revisarla. No se inventan reglas para escenarios sin evidencia suficiente. Por ejemplo, box primero es obligatorio por edad o urgencia; en los demás casos, hacerlo primero no se considera por sí solo una violación. El CSV no registra minutos de atención ni eventos posteriores de retriage, llegada de documentos o indicaciones de internación; no se deducen incumplimientos de esos eventos ausentes.
