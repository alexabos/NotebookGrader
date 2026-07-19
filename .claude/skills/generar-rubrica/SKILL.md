---
name: generar-rubrica
description: Genera un borrador de rúbrica de corrección (rubric.txt) a partir de un notebook con enunciados de una entrega. Úsala cuando el usuario pida crear, generar o preparar una rúbrica para una unidad o entrega nueva de NotebookGrader.
---

# Generar rúbrica de corrección

## Cuándo usar esta skill
Cuando el usuario proporcione un notebook con enunciados (sin resolver) y pida
generar una rúbrica de evaluación para esa entrega, para usar con `grader.py`.

## Input esperado
- Ruta al notebook con los enunciados de la unidad (p.ej.
  `courses/intro_python/unidad3/enunciados.ipynb`).
- (Opcional) Notebooks de entregas anteriores ya resueltos, como referencia de nivel de exigencia.
- (Opcional) Un `rubric.txt` de una unidad anterior del mismo curso, como referencia de formato/tono.
- (Opcional) Instrucciones del profesor sobre criterios especiales (ej. "penalizar código no vectorizado",
  "no exigir manejo de excepciones", "no penalizar fallos de `input()` en ejecución automática").

## Proceso
1. Lee el notebook de enunciados celda por celda.
2. Identifica cada ejercicio evaluable (ignora celdas de introducción/contexto sin tarea).
3. Para cada ejercicio, propone:
   - Un título breve y su valor en puntos.
   - Criterios de corrección desglosados en sub-puntos si el ejercicio tiene varias partes
     (ej. "función devuelve el tipo correcto", "maneja el caso borde de lista vacía").
   - Puntuación por criterio, de forma que la suma de todos los ejercicios dé exactamente 10.
4. Marca explícitamente cualquier ejercicio donde el enunciado sea ambiguo o
   permita varias interpretaciones válidas — no asumas una única solución correcta;
   propón cómo dar crédito a enfoques alternativos razonables.
5. Si detectas algo que fallará en corrección automática por diseño (p.ej. `input()`,
   dependencias externas, aleatoriedad) anótalo como nota para no penalizarlo.
6. NO resuelvas los ejercicios tú mismo salvo que sea necesario para entender qué se pide.
7. Si se te proporcionó un `rubric.txt` anterior, sigue su mismo estilo y estructura de encabezados.
8. Incluye siempre la sección "Reglas generales" (ver más abajo) en el `rubric.txt` generado.

## Reglas generales
Estas reglas aplican a todas las rúbricas generadas por esta skill; inclúyelas siempre
como parte de las Notes del `rubric.txt`, no solo en este documento:
- **Mensajes de `print`**: no penalizar mensajes genéricos o poco elaborados — basta con que
  transmitan la información pedida. Si el enunciado muestra un mensaje de ejemplo (p.ej.
  "56 es divisible por 2"), el texto exacto es solo ilustrativo, no hace falta reproducirlo
  palabra por palabra. Penalizar únicamente si el mensaje es claramente incorrecto, engañoso
  o no comunica la información pedida.
- **Uso de `input()`**: no penalizar el uso de `input()` en ningún ejercicio. `input()` falla
  en la ejecución automática del notebook, así que en esos casos evalúa la lógica del código
  tal como está escrito (sin poder ver su ejecución) para comprobar que es correcta, en lugar
  de basarte en la salida.
- **Nombres de función**: si el enunciado especifica el nombre de una función (p.ej.
  `elementos_pares`) y el alumno usa un nombre distinto pero la lógica/comportamiento es
  correcto, no penalizar — el nombre exacto no es un criterio de corrección salvo que el
  enunciado indique explícitamente que otro código depende de ese nombre concreto.
- **Manejo de errores**: si el manejo de errores/excepciones es incompleto o mejorable
  (p.ej. no cubre todos los casos, `except` demasiado genérico o demasiado específico),
  no bajar mucho la nota por ello — explicar en el comentario cómo se podría mejorar, pero
  aplicar solo una penalización pequeña. Esto no aplica a errores que impiden ejecutar el
  notebook o que rompen la lógica principal del ejercicio; aplica solo a la calidad del
  manejo de errores en sí.

## Formato de salida
Escribe directamente en el mismo formato de texto plano que ya usa `rubric.txt` en este
proyecto (revisa `courses/*/*/rubric.txt` si existe alguno como referencia de estilo). Estructura:

```
<Nombre del curso/unidad>
Grading rubric (0–10 scale, total 10 points)

---

### Ejercicio 1 — <título> (<puntos> points)
- a) <criterio> (<puntos> pts)
- b) <criterio> (<puntos> pts)

### Ejercicio 2 — <título> (<puntos> points)
<descripción y criterios>

---

### Overall grading scale
10    — ...
8–9   — ...
6–7   — ...
4–5   — ...
2–3   — ...
0–1   — ...

### Notes
- <notas sobre casos especiales, ambigüedades, qué no penalizar>
```

Este archivo es consumido literalmente por `evaluator.py`: se envía tal cual a Claude
junto al notebook del alumno, así que debe ser autocontenido y sin dependencias de este
documento de skill.

## Importante
- Esto es un BORRADOR. Al terminar, muestra un resumen legible del desglose por ejercicio
  (no solo el archivo final) y pide explícitamente confirmación del usuario antes de escribir
  o sobrescribir `rubric.txt`.
- Si ya existe un `rubric.txt` en la carpeta de destino, avisa antes de sobrescribirlo y
  confirma con el usuario.
- No actives corrección automática (`grader.py`) como parte de esta skill — solo generas la
  rúbrica; correr el grader es una acción separada que decide el usuario.
