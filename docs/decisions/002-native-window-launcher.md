# ADR-002 — Ventana nativa de escritorio sin navegador

- **Fecha**: 2026-09
- **Estado**: Aceptado (mandato del usuario)
- **Decisores**: Usuario ("es un programa de PC, no debe abrir el navegador")

## Contexto

Streamlit es la tecnología de UI elegida, pero sirve su interfaz vía HTTP en un navegador. El usuario final (una persona no técnica) exigió explícitamente que el programa se abra en **su propia ventana de escritorio**, nunca en el navegador.

## Decisión

`launcher.py`:

1. Arranca Streamlit en **headless** (`--server.headless true`) sobre `127.0.0.1` en el primer puerto libre del rango 8501–8560.
2. Abre una **ventana nativa WebView2** vía pywebview (`webview.create_window("EliminaMuletillas", url, ...)`), sin barra de navegador.
3. **Fallback al navegador** solo si la ventana nativa no puede crearse (WebView2 Runtime ausente), con registro en `launcher.log` y aviso vía `MessageBoxW`.
4. Errores de arranque → `MessageBoxW` nativo + `launcher.log` (no hay consola: el exe se compila con `--noconsole`).

## Alternativas consideradas

- **Tauri/Electron**: sobrepeso enorme para empaquetar y mantener; el proyecto ya tiene el motor web en Streamlit.
- **pywebview (elegido)**: contenedor delgado sobre el WebView2 del sistema, empaquetable en el runtime portable.
- **Dejar el navegador**: rechazado por mandato explícito del usuario.

## Consecuencias

- `--server.headless true` es una invariante de empaquetado: el exe jamás debe abrir el navegador por sí mismo.
- El runtime portable debe incluir pywebview y sus dependencias (`bottle`, `cffi`, `pythonnet`, `proxy_tools`, `clr_loader`, etc.).
- En equipos sin WebView2 Runtime el programa usa el navegador como plan B y lo documenta en `LEEME.txt`; es un comportamiento aceptado, no un error.
