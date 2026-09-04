# ADR-003 — Distribución portable (exe + runtime embebido + ffmpeg)

- **Fecha**: 2026-09
- **Estado**: Aceptado
- **Decisores**: Arquitectura + perfil del cliente final (no técnico)

## Contexto

El destinatario es una persona normal que no instala Python ni dependencias. Se necesita entregar el programa listo para ejecutar (doble clic), sin instalador complejo, que funcione sin permisos de administrador y que no dependa de un navegador (ver ADR-002).

## Decisión

Distribución **portable** en carpeta `EliminaMuletillas_Portable/`, empaquetada como ZIP:

```
EliminaMuletillas_Portable/
├── EliminaMuletillas.exe   # launcher.py compilado (PyInstaller --onefile --noconsole)
├── app/                    # código fuente + filler_words.json + .streamlit/config.toml
├── runtime/                # Python 3.11 embebido + site-packages
├── bin/                    # ffmpeg / ffprobe
└── LEEME.txt               # instrucciones del usuario final
```

El exe es solo el lanzador; la app se sirve desde `app\app.py` con `runtime\python.exe`, y `bin\` se añade al `PATH` para pydub/ffmpeg.

## Alternativas consideradas

- **PyInstaller de la app Streamlit completa en un solo binario**: frágil con el runtime de Streamlit y sus estáticos; el enfoque exe-lanzador es más mantenible.
- **Instalador (Inno Setup / MSI)**: más complejo de mantener; el usuario pidió "versión portable".
- **Pedir al usuario instalar Python + `pip install`**: descartado por el perfil no técnico del cliente.

## Consecuencias

- **Invariantes de empaquetado**: no borrar/renombrar `runtime\` ni `bin\`; **no modificar `python311._pth`**; el exe no abre el navegador (`--server.headless true`).
- **Proceso de build manual** (ver `AGENTS.md`): copiar fuentes a `app\`, recompilar el exe con PyInstaller, verificar, regenerar el ZIP (≈470 MB, varios minutos).
- La primera transcripción requiere internet para descargar el modelo Whisper (~460 MB); el resto del funcionamiento es offline.
- `launcher.log` junto al exe es la fuente de diagnóstico principal; `LEEME.txt` documenta solución de problemas (WebView2, editor desconocido, etc.).
