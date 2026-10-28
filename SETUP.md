# Preparación del entorno

Esta guía explica cómo preparar el entorno local y los accesos del grupo. Los requisitos de la entrega están en [mission.md](mission.md).

## Instalar y sincronizar

En Windows, instalar `uv` si todavía no está disponible:

```powershell
winget install --id=astral-sh.uv -e
```

Cerrar y abrir la terminal después de instalarlo. Desde la carpeta del repositorio:

```powershell
$env:PYTHONUTF8 = '1'
uv --version
uv sync --locked
uv run --locked python --version
uv run --locked python -c "import admision, yaml; print('Kit de admision: OK')"
```

`.python-version` selecciona Python 3.12.16. `uv` puede descargar esa versión si falta; el entorno del proyecto se crea en `.venv`. `uv.lock` fija las versiones de los paquetes. La instalación de Python 3.11 del equipo se conserva.

En Windows, repetir `$env:PYTHONUTF8 = '1'` al abrir una terminal para trabajar en el proyecto. Esto permite imprimir los caracteres Unicode que usa el evaluador del kit. También se puede activar para un comando puntual con `python -X utf8`.

El grupo `dev`, instalado por defecto por `uv sync`, incluye los clientes de Modal, Hugging Face y W&B. Las librerías de entrenamiento e inferencia se agregarán cuando se defina la estrategia.

Referencias oficiales: [instalación de uv](https://docs.astral.sh/uv/getting-started/installation/), [gestión de Python](https://docs.astral.sh/uv/guides/install-python/).

## Accesos a los servicios

Los clientes están instalados; iniciar sesión y comprobar los permisos es un paso separado. Tener una sesión abierta en el navegador no autentica automáticamente los comandos.

### Modal

Crear o usar una cuenta en [Modal](https://modal.com) y ejecutar:

```powershell
uv run --locked modal setup
uv run --locked modal profile list
```

`setup` abre el proceso de autenticación en el navegador. Para las próximas etapas, comprobar en la cuenta el acceso a una GPU A100 de 40 GB y las condiciones de créditos y facturación. Esta preparación local no ejecuta trabajos en GPU.

Referencia: [guía de inicio de Modal](https://modal.com/docs/guide).

### Hugging Face

Crear o usar una cuenta en [Hugging Face](https://huggingface.co/join). Generar un token en [Access Tokens](https://huggingface.co/settings/tokens) e ingresarlo directamente cuando lo solicite el comando:

```powershell
uv run --locked hf auth login
uv run --locked hf auth whoami
```

Usar permisos de lectura para descargar modelos. Cuando publiquemos los puntos de control, configurar permisos de escritura limitados al repositorio del grupo. Después de elegir el modelo base, verificar también que la cuenta pueda acceder a sus archivos y completar cualquier solicitud de acceso o aceptación de licencia que corresponda.

Referencias: [CLI de Hugging Face](https://huggingface.co/docs/huggingface_hub/guides/cli), [permisos de tokens](https://huggingface.co/docs/hub/security-tokens).

### Weights & Biases (W&B)

Crear o usar una cuenta en [W&B](https://wandb.ai), obtener su clave en la configuración de la cuenta y ejecutar:

```powershell
uv run --locked wandb login
```

Ingresar la clave directamente en la terminal cuando se solicite. Falta acordar el usuario o equipo y el proyecto que guardarán las corridas del grupo; luego comprobaremos que todos tengan acceso.

Referencia: [inicio rápido del SDK oficial de W&B](https://github.com/wandb/wandb#quickstart).

### Loom y organización del grupo

Comprobar que se puede ingresar a [Loom](https://www.loom.com) para ver los videos del enunciado y grabar la presentación final. Acordar los responsables de las tareas y cómo repartir los commits entre los integrantes.

## Variables y credenciales

[.env.example](.env.example) enumera variables para los futuros scripts del grupo y contiene valores vacíos para los secretos. El kit actual no carga `.env` automáticamente; los comandos de autenticación anteriores funcionan sin crear ese archivo. `.env` ya está excluido por `.gitignore`.

Las contraseñas y claves se ingresan en el servicio o en su comando de autenticación, sin pegarlas en el chat ni guardarlas en archivos versionados.

## Comprobación local realizada

El 28 de octubre de 2026 se instaló `uv` 0.13.6 y Python 3.12.16, se ejecutó `uv sync` y se comprobó la ejecución con `uv run --locked`. Se importaron correctamente los diez módulos de `admision`, PyYAML y los clientes de Modal, Hugging Face y W&B. También se comprobó la ayuda de `admision.correr` y, activando UTF-8, la de `admision.evaluar_rag`.

Los inicios de sesión y permisos de las cuentas siguen pendientes de verificación.
