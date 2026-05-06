from flask import current_app

from app.services.input_safety import has_malicious_input

FIELD_TITLE = "title"
FIELD_DESCRIPTION = "description"
VALID_FIELDS = {FIELD_TITLE, FIELD_DESCRIPTION}
MAX_INPUT_LENGTH = {
    FIELD_TITLE: 200,
    FIELD_DESCRIPTION: 6000,
}
MAX_NEWS_BODY_LENGTH = 12000


def _build_system_prompt(field: str) -> str:
    if field == FIELD_TITLE:
        return (
            "Eres un editor profesional en espanol para reportes ciudadanos. "
            "Corrige ortografia, gramatica y concordancia del TITULO sin inventar hechos. "
            "Mantiene nombres propios, lugares, fechas y sentido original. "
            "No agregues informacion nueva ni cambies el tono del reporte. "
            "Devuelve solo el titulo final, sin comillas ni explicaciones."
        )
    return (
        "Eres un editor profesional en espanol para reportes ciudadanos. "
        "Corrige ortografia, gramatica, concordancia y fluidez de la DESCRIPCION "
        "sin inventar hechos. Mantiene nombres propios, lugares, fechas y sentido original. "
        "Mantiene una longitud similar al original y nunca menos de 50 caracteres. "
        "No agregues informacion nueva ni conclusiones. "
        "Devuelve solo la descripcion final, sin comillas ni explicaciones."
    )


def _build_user_prompt(
    field: str,
    text: str,
    title_context: str = "",
    description_context: str = "",
) -> str:
    field_name = "titulo" if field == FIELD_TITLE else "descripcion"
    return (
        f"Campo a mejorar: {field_name}\n"
        f"Titulo de contexto: {title_context.strip()[:260]}\n"
        f"Descripcion de contexto: {description_context.strip()[:2500]}\n"
        f"Texto original:\n{text.strip()}\n\n"
        "Devuelve solo el texto corregido final."
    )


def _load_openai_client():
    api_key = (current_app.config.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY no esta configurada. Define la variable de entorno para usar IA."
        )
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(
            "La dependencia openai no esta instalada. Ejecuta: pip install -r requirements.txt"
        ) from exc

    timeout_seconds = int(current_app.config.get("OPENAI_TIMEOUT_SECONDS", 30) or 30)
    try:
        return OpenAI(api_key=api_key, timeout=timeout_seconds)
    except TypeError as exc:
        # Compatibilidad para entornos con openai viejo + httpx nuevo
        # donde el cliente interno falla por el argumento "proxies".
        if "proxies" not in str(exc).lower():
            raise
        try:
            import httpx
        except Exception as import_exc:
            raise RuntimeError(
                "Incompatibilidad de dependencias OpenAI/httpx. "
                "Actualiza openai o instala httpx compatible."
            ) from import_exc
        http_client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        return OpenAI(api_key=api_key, http_client=http_client)


def optimize_report_text(
    field: str,
    text: str,
    title_context: str = "",
    description_context: str = "",
) -> str:
    normalized_field = (field or "").strip().lower()
    if normalized_field not in VALID_FIELDS:
        raise ValueError("Campo invalido. Usa 'title' o 'description'.")

    value = (text or "").strip()
    if not value:
        raise ValueError("No hay texto para optimizar.")

    max_len = MAX_INPUT_LENGTH.get(normalized_field, 2000)
    if len(value) > max_len:
        raise ValueError(f"El texto supera el maximo permitido ({max_len} caracteres).")

    if has_malicious_input([value, title_context, description_context]):
        raise ValueError("Se detecto contenido sospechoso.")

    model = (current_app.config.get("OPENAI_TEXT_MODEL") or "gpt-4o-mini").strip()
    if not model:
        model = "gpt-4o-mini"

    client = _load_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=220 if normalized_field == FIELD_TITLE else 700,
        messages=[
            {"role": "system", "content": _build_system_prompt(normalized_field)},
            {
                "role": "user",
                "content": _build_user_prompt(
                    normalized_field,
                    value,
                    title_context=title_context,
                    description_context=description_context,
                ),
            },
        ],
    )

    message = ""
    if response and getattr(response, "choices", None):
        first = response.choices[0]
        if first and getattr(first, "message", None):
            message = (first.message.content or "").strip()

    if not message:
        raise RuntimeError("OpenAI no devolvio texto optimizado.")

    if normalized_field == FIELD_TITLE:
        return message[:200].strip()
    return message.strip()


def generate_news_summary(title: str, body: str) -> str:
    title_value = (title or "").strip()[:220]
    body_value = (body or "").strip()
    if not body_value:
        raise ValueError("No hay cuerpo de noticia para resumir.")
    if len(body_value) > MAX_NEWS_BODY_LENGTH:
        raise ValueError(f"El cuerpo supera el maximo permitido ({MAX_NEWS_BODY_LENGTH} caracteres).")
    if has_malicious_input([title_value, body_value]):
        raise ValueError("Se detecto contenido sospechoso.")

    model = (current_app.config.get("OPENAI_TEXT_MODEL") or "gpt-4o-mini").strip()
    if not model:
        model = "gpt-4o-mini"

    client = _load_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=130,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un editor de noticias en espanol. Resume una noticia para una "
                    "tarjeta de blog en 1 o 2 frases, maximo 320 caracteres. No inventes "
                    "hechos, no agregues opinion y devuelve solo el resumen."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Titulo: {title_value}\n\n"
                    f"Cuerpo en markdown:\n{body_value[:MAX_NEWS_BODY_LENGTH]}\n\n"
                    "Devuelve solo el resumen final."
                ),
            },
        ],
    )

    message = ""
    if response and getattr(response, "choices", None):
        first = response.choices[0]
        if first and getattr(first, "message", None):
            message = (first.message.content or "").strip()
    if not message:
        raise RuntimeError("OpenAI no devolvio resumen.")
    return message[:500].strip()
