---
name: ingerir-entregas
description: Ingiere una descarga masiva de entregas de Moodle (una carpeta por alumno) en courses/<curso>/<unidad>/submissions/, sustituyendo el nombre del alumno por un id anónimo estable y manteniendo el mapeo en courses/<curso>/roster.csv. Úsala cuando el usuario tenga una carpeta descargada de Moodle y quiera prepararla para NotebookGrader.
---

# Ingerir entregas de Moodle

## Cuándo usar esta skill

Cuando el usuario tenga una carpeta de descarga masiva de Moodle (contiene una
subcarpeta por alumno, con el patrón `<Nombre>_<id_moodle>_assignsubmission_*`)
y quiera dejar los `.ipynb` listos en `courses/<curso>/<unidad>/submissions/`
para poder corregirlos con `grader.py`, sin que el nombre real del alumno
quede en el nombre del archivo.

## Input esperado

- Ruta a la carpeta de descarga de Moodle (p.ej. `temp/MUDAB_..._Unidad 2-349496`).
- Curso destino (p.ej. `intro_python`).
- Unidad destino (p.ej. `unidad2`).

## Proceso

1. Ejecuta el script determinista:
   ```
   uv run ingest.py --source "<carpeta_moodle>" --course <curso> --unit <unidad>
   ```
   Toda la lógica de emparejar nombre↔id, copiar y renombrar los notebooks la
   hace el script, no el modelo — es un paso mecánico que debe ser
   reproducible, no una decisión de la LLM.

2. Lee el resumen que imprime el script y repórtaselo al usuario de forma
   legible:
   - **Nuevas entradas en el roster** (`id  <-  nombre`): muéstraselas todas
     y pide confirmación explícita de que el mapeo nombre→id es correcto
     antes de dar el paso por terminado.
   - **Posibles duplicados** (nombres parecidos a uno ya existente en el
     roster, p.ej. con/sin tilde): el script NUNCA los fusiona
     automáticamente. Muéstraselos al usuario y pregúntale si son la misma
     persona (y en ese caso cómo prefiere resolverlo manualmente editando
     `roster.csv`) o son personas distintas.
   - **Carpetas omitidas** (sin `.ipynb` o con varios): muéstraselas con el
     motivo y pregunta al usuario cómo proceder — normalmente eligiendo a
     mano el archivo correcto y copiándolo, o descartando la entrega.
   - **Advertencias** (p.ej. falta `rubric.txt` en la unidad destino):
     coméntaselas, pero no es necesario bloquear el proceso por esto.

3. Confirma con el usuario que `courses/<curso>/<unidad>/submissions/` está
   lista para usarse con `grader.py`.

## Importante

- `roster.csv` y la carpeta de origen de Moodle contienen nombres reales de
  alumnos. Ambos están en `.gitignore`: nunca los añadas al control de
  versiones ni los pegues en un prompt de evaluación — el nombre del alumno
  no debe llegar nunca a la LLM.
- No ejecutes `grader.py` como parte de esta skill: ingerir entregas y
  corregirlas son pasos separados que decide el usuario.
- No fusiones manualmente entradas del roster que la skill marque como
  "posible duplicado" sin que el usuario lo confirme explícitamente.
- Si `courses/<curso>/<unidad>/rubric.txt` no existe todavía, el script
  avisa pero ingiere igualmente; recuérdale al usuario que tendrá que
  crearlo (p.ej. con la skill `generar-rubrica`) antes de poder corregir.
