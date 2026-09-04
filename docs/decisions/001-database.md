# ADR-001 — Persistencia con SQLite + `filler_words.json`

- **Fecha**: 2026 (fase inicial del proyecto)
- **Estado**: Aceptado
- **Decisores**: Arquitectura + requisitos del usuario ("Regla del DM")

## Contexto

La app necesita dos tipos de persistencia local, sin red:

1. **Historial de proyectos**: metadatos de cada audio procesado (ruta original, duración, `sample_rate`, canales, bits, ruta de exportación, fecha) para auditoría y reapertura de sesiones.
2. **Lista de muletillas**: editable por un usuario no técnico, con cambios que deben reflejarse al instante y sin re-transcribir.

## Decisión

- **SQLite** (`projects.db`, esquema idempotente `_SCHEMA` en `database.py`) para los metadatos estructurados de proyectos y sus rutas de exportación.
- **JSON** (`filler_words.json`, `{"fillers": [...]}`) para la lista de muletillas, gestionado por el singleton thread-safe `FillerConfig` (`models.py`).
- `models.DEFAULT_FILLERS` es solo el seed del primer arranque; nunca es la fuente de verdad en ejecución.

## Alternativas consideradas

- **Un solo JSON para todo**: pierde las consultas estructuradas y la integridad del historial.
- **CSV**: sin tipos, sin concurrencia segura, feo de editar a mano.
- **Sin persistencia**: el usuario final no podría reabrir proyectos ni conservar su lista personalizada.

## Consecuencias

- El esquema SQLite es idempotente (`executescript` con `CREATE TABLE IF NOT EXISTS`); las bases existentes deben seguir siendo compatibles al evolucionar el esquema.
- El JSON es legible y editable a mano, cumpliendo la "Regla del DM": cambiar la lista solo re-ejecuta `mark_fillers`, nunca Whisper.
- `FillerConfig` usa un singleton con `threading.Lock` porque la UI de Streamlit puede acceder a la configuración desde varios contextos.
