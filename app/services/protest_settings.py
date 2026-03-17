from app.extensions import db
from app.models.site_setting import SiteSetting


PROTEST_SETTINGS_SCHEMA = [
    {
        "key": "PROTEST_FETCH_INTERVAL_SECONDS",
        "label": "Intervalo de ingesta (segundos)",
        "kind": "int",
        "default": "300",
        "min": 60,
        "max": 86400,
        "help": "Cada cuanto corre la ingesta automatica de feeds.",
    },
    {
        "key": "PROTEST_FETCH_TIMEOUT_SECONDS",
        "label": "Timeout por feed (segundos)",
        "kind": "int",
        "default": "20",
        "min": 5,
        "max": 300,
        "help": "Tiempo maximo de espera por request al feed.",
    },
    {
        "key": "PROTEST_FRONTEND_REFRESH_SECONDS",
        "label": "Refresh del mapa (segundos)",
        "kind": "int",
        "default": "300",
        "min": 30,
        "max": 86400,
        "help": "Cada cuanto el frontend actualiza la capa de protestas.",
    },
    {
        "key": "PROTEST_MAX_POST_AGE_DAYS",
        "label": "Antiguedad maxima de posts (dias)",
        "kind": "int",
        "default": "7",
        "min": 1,
        "max": 90,
        "help": "Descarta posts mas antiguos que este limite.",
    },
    {
        "key": "PROTEST_MAX_ITEMS_PER_FEED",
        "label": "Maximo items por feed",
        "kind": "int",
        "default": "120",
        "min": 1,
        "max": 1000,
        "help": "Limite de items procesados por cada feed.",
    },
    {
        "key": "PROTEST_REQUIRE_SOURCE_URL",
        "label": "Requerir URL de fuente para mostrar en mapa",
        "kind": "bool01",
        "default": "1",
        "help": "1 = exige enlace de fuente. 0 = permite sin fuente.",
    },
    {
        "key": "PROTEST_ALLOW_UNRESOLVED_TO_MAP",
        "label": "Permitir eventos sin coordenadas en mapa",
        "kind": "bool01",
        "default": "0",
        "help": "1 = permite sin coordenadas. 0 = solo con lat/lon.",
    },
    {
        "key": "PROTEST_MIN_CONFIDENCE_TO_SHOW",
        "label": "Confianza minima para mostrar (0-100)",
        "kind": "float_range",
        "default": "10",
        "min": 0.0,
        "max": 100.0,
        "help": "Escala 0-100.",
    },
    {
        "key": "PROTEST_KEYWORDS_STRONG",
        "label": "Keywords fuertes (CSV)",
        "kind": "csv",
        "default": (
            "protesta,protestas,protestantes,manifestantes,cacerolazo,"
            "a la calle,cacerolas,calderos,trancar calles,gritar libertad"
        ),
        "help": "Separadas por coma.",
    },
    {
        "key": "PROTEST_KEYWORDS_CONTEXT",
        "label": "Keywords de contexto (CSV)",
        "kind": "csv",
        "default": (
            "detenidos,fuente,represion,descontento social,"
            "indignacion popular,enfrentamiento,sin orden judicial"
        ),
        "help": "Separadas por coma.",
    },
    {
        "key": "PROTEST_KEYWORDS_WEAK",
        "label": "Keywords debiles (CSV)",
        "kind": "csv",
        "default": "situacion,tension,incidente",
        "help": "Separadas por coma.",
    },
]

PROTEST_SETTINGS_DEFAULTS = {
    field["key"]: str(field.get("default", ""))
    for field in PROTEST_SETTINGS_SCHEMA
}


def get_protest_settings_schema():
    return [dict(field) for field in PROTEST_SETTINGS_SCHEMA]


def _normalize_csv(value):
    parts = [part.strip() for part in str(value or "").split(",")]
    return ",".join(part for part in parts if part)


def _format_float(value):
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.4f}".rstrip("0").rstrip(".")


def get_protest_settings_values():
    keys = [field["key"] for field in PROTEST_SETTINGS_SCHEMA]
    existing = SiteSetting.query.filter(SiteSetting.key.in_(keys)).all()
    settings_map = {item.key: item.value for item in existing}

    values = {}
    for field in PROTEST_SETTINGS_SCHEMA:
        values[field["key"]] = str(settings_map.get(field["key"], field["default"]))
    return values


def get_protest_setting_value(key, fallback=None):
    default_value = fallback
    if default_value is None:
        default_value = PROTEST_SETTINGS_DEFAULTS.get(str(key or "").strip(), "")

    try:
        setting = SiteSetting.query.filter_by(key=str(key or "").strip()).first()
    except Exception:
        return str(default_value)
    if not setting:
        return str(default_value)

    value = str(setting.value or "").strip()
    return value if value else str(default_value)


def validate_protest_settings_payload(payload):
    cleaned = {}
    errors = {}

    for field in PROTEST_SETTINGS_SCHEMA:
        key = field["key"]
        raw_value = str((payload or {}).get(key, "")).strip()
        if not raw_value:
            raw_value = str(field["default"])

        kind = field["kind"]
        if kind == "int":
            try:
                parsed = int(raw_value)
            except Exception:
                errors[key] = "Debe ser un entero."
                continue
            min_value = int(field.get("min", parsed))
            max_value = int(field.get("max", parsed))
            if parsed < min_value or parsed > max_value:
                errors[key] = f"Debe estar entre {min_value} y {max_value}."
                continue
            cleaned[key] = str(parsed)
            continue

        if kind == "bool01":
            if raw_value not in {"0", "1"}:
                errors[key] = "Usa 1 o 0."
                continue
            cleaned[key] = raw_value
            continue

        if kind == "float_range":
            try:
                parsed = float(raw_value)
            except Exception:
                errors[key] = "Debe ser numerico."
                continue
            min_value = float(field.get("min", parsed))
            max_value = float(field.get("max", parsed))
            if parsed < min_value or parsed > max_value:
                errors[key] = f"Debe estar entre {min_value:g} y {max_value:g}."
                continue
            cleaned[key] = _format_float(parsed)
            continue

        if kind == "csv":
            normalized = _normalize_csv(raw_value)
            if not normalized:
                errors[key] = "No puede quedar vacio."
                continue
            cleaned[key] = normalized
            continue

        cleaned[key] = raw_value

    return cleaned, errors


def save_protest_settings(values):
    if not values:
        return

    keys = list(values.keys())
    existing = SiteSetting.query.filter(SiteSetting.key.in_(keys)).all()
    settings_map = {item.key: item for item in existing}

    for key, value in values.items():
        setting = settings_map.get(key)
        if setting:
            setting.value = str(value)
        else:
            db.session.add(SiteSetting(key=key, value=str(value)))

    db.session.commit()
