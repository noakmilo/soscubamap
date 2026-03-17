# Guia de contribucion a traducciones

## Arquitectura

Las traducciones estan centralizadas en `translations/`:

```
translations/
  messages.pot                        # fuente maestra backend (generada, no editar a mano)
  es/LC_MESSAGES/messages.po          # backend español
  en/LC_MESSAGES/messages.po          # backend ingles
  frontend/
    es.json                           # fuente maestra frontend (editar aqui)
    en.json                           # frontend ingles
    *.json                            # otros idiomas (gestionados por Crowdin)
```

El selector de idioma en la UI detecta automaticamente los archivos `translations/frontend/*.json` disponibles.
Agregar un nuevo idioma en Crowdin hace que aparezca en la UI sin cambios de codigo.

---

## Para traductores (sin codigo)

Traduce directamente en **Crowdin**. No edites los archivos `.po` ni `.json` del repo a mano.

Crowdin gestiona:
- `translations/frontend/*.json` para la UI del navegador.
- `translations/*/LC_MESSAGES/messages.po` para textos del servidor (Flask).

---

## Para desarrolladores

### Anadir texto nuevo en Python o Jinja (backend)

1. Envuelve el texto con `_("...")`:

   ```python
   flash(_("Texto nuevo."), "success")
   ```

   En Jinja:

   ```html
   {{ _("Texto nuevo.") }}
   ```

2. Regenera la plantilla maestra:

   ```bash
   pybabel extract -F babel.cfg -o translations/messages.pot .
   ```

3. Actualiza los catalogos existentes:

   ```bash
   pybabel update -i translations/messages.pot -d translations
   ```

4. Haz commit de `translations/messages.pot` y los `.po` actualizados.

   > Los archivos `.mo` **no se versionan**; se compilan durante el build de Docker.

### Anadir texto nuevo en JavaScript (frontend)

1. Agrega la clave y el texto en espanol en `translations/frontend/es.json`:

   ```json
   "mi_clave_nueva": "Texto en espanol."
   ```

2. Usa la clave en el JS con `t("mi_clave_nueva")`.

3. Haz commit solo de `translations/frontend/es.json`. No toques los otros `.json`; Crowdin los actualiza.

### Verificacion local antes de abrir PR

```bash
# Verificar que messages.pot esta al dia
python scripts/check_i18n.py pot

# Verificar coherencia de archivos JSON de frontend
python scripts/check_i18n.py frontend
```

Estos mismos checks corren automaticamente en CI para cada PR a `main`.

---

## Automatizacion Crowdin <-> GitHub

| Workflow | Cuando corre | Que hace |
|---|---|---|
| `l10n-upload-sources` | Push a `main` con cambios en fuentes | Sube `messages.pot` y `es.json` a Crowdin |
| `l10n-download-translations` | Cada 6 horas o manual | Descarga traducciones y abre PR automatica |
| `check-i18n` | Cada PR a `main` | Bloquea si las fuentes estan desactualizadas |

### Secrets requeridos en GitHub Actions

- `CROWDIN_PROJECT_ID`
- `CROWDIN_PERSONAL_TOKEN`

### Configuracion del proyecto en Crowdin

- Idioma fuente: `es`
- Idiomas destino: `en` y los que se agreguen
- Archivo de configuracion: `crowdin.yml`
