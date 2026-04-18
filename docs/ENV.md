# Variables de entorno

Referencia completa de las variables de entorno de SOSCuba Map. Copiar `.env.example` a `.env` y ajustar los valores.

## Obligatorias

| Variable       | Descripción                                  | Ejemplo                                                            |
|----------------|----------------------------------------------|--------------------------------------------------------------------|
| `SECRET_KEY`   | Clave secreta de Flask para firmar sesiones. Cambiar siempre en producción. | `openssl rand -hex 32`                                    |
| `DATABASE_URL` | URI de conexión a PostgreSQL.                | `postgresql+psycopg://user:pass@localhost:5432/soscubamap`         |

## Administrador

| Variable         | Descripción                                  | Default                |
|------------------|----------------------------------------------|------------------------|
| `ADMIN_EMAIL`    | Email del administrador. Se auto-crea al hacer login por primera vez. | `admin@soscuba.local` |
| `ADMIN_PASSWORD` | Contraseña del admin. Si está vacía, el login admin no funciona. | (vacío)               |

## Imágenes (Cloudinary)

| Variable                | Descripción                          | Default  |
|-------------------------|--------------------------------------|----------|
| `CLOUDINARY_CLOUD_NAME` | Nombre del cloud en Cloudinary.      | (vacío)  |
| `CLOUDINARY_API_KEY`    | API key de Cloudinary.               | (vacío)  |
| `CLOUDINARY_API_SECRET` | API secret de Cloudinary.            | (vacío)  |
| `IMAGE_MAX_MB`          | Tamaño máximo por imagen en MB.      | `2`      |
| `IMAGE_MAX_PER_SUBMIT`  | Máximo de imágenes por envío.        | `3`      |
| `IMAGE_ALLOWED_EXTENSIONS` | Extensiones permitidas (CSV).     | `jpg,jpeg,png,webp,heic` |

## Mapas (Google Maps)

Estos valores se usan opcionalmente para geocodificación y mapas avanzados. La app funciona sin ellos usando Leaflet/OSM.

| Variable              | Descripción                   | Default  |
|-----------------------|-------------------------------|----------|
| `GOOGLE_MAPS_API_KEY` | API key de Google Maps.       | (vacío)  |
| `GOOGLE_MAPS_MAP_ID`  | Map ID para estilos custom.   | (vacío)  |

## IA (OpenAI)

Optimización opcional de título y descripción en la edición de reportes (solo admin).

| Variable                 | Descripción                                              | Default       |
|--------------------------|----------------------------------------------------------|---------------|
| `OPENAI_API_KEY`         | API key de OpenAI para usar la optimización de texto.    | (vacío)       |
| `OPENAI_TEXT_MODEL`      | Modelo usado para corregir texto de título/descripcion.  | `gpt-4o-mini` |
| `OPENAI_TIMEOUT_SECONDS` | Timeout en segundos para la petición a OpenAI.           | `30`          |

## GeoJSON (datos geográficos de Cuba)

Rutas a archivos GeoJSON para la resolución automática de provincia/municipio a partir de coordenadas.

| Variable                         | Descripción                                              | Default  |
|----------------------------------|----------------------------------------------------------|----------|
| `GEOJSON_PROVINCES_PATH`         | Ruta al archivo GeoJSON de provincias.                   | (vacío)  |
| `GEOJSON_MUNICIPALITIES_PATH`    | Ruta al archivo GeoJSON de municipios.                   | (vacío)  |
| `GEOJSON_PROVINCE_KEYS`         | Nombres de propiedades en el GeoJSON para buscar provincia. | (vacío) |
| `GEOJSON_MUNICIPALITY_KEYS`     | Nombres de propiedades para buscar municipio.            | (vacío)  |
| `GEOJSON_MUNICIPALITY_PROVINCE_KEYS` | Propiedades que vinculan municipio con provincia.   | (vacío)  |
| `GEOJSON_PROVINCE_KEYS`          | Nombres de propiedades en el GeoJSON para buscar provincia. | (vacío) |
| `GEOJSON_MUNICIPALITY_KEYS`      | Nombres de propiedades para buscar municipio.            | (vacío)  |
| `GEOJSON_MUNICIPALITY_PROVINCE_KEYS` | Propiedades que vinculan municipio con provincia.   | (vacío)  |
| `GEOJSON_LOCALITY_KEYS`          | Nombres de propiedades para buscar localidad.            | (vacío)  |
| `GEOJSON_LOCALITY_MUNICIPALITY_KEYS` | Propiedades que vinculan localidad con municipio.   | (vacío)  |
| `GEOJSON_LOCALITY_PROVINCE_KEYS` | Propiedades que vinculan localidad con provincia.        | (vacío)  |

## Push Notifications (VAPID)

Para habilitar notificaciones push a los navegadores suscritos cuando se crean reportes urgentes o alertas de pánico.

| Variable            | Descripción                                     | Default                           |
|---------------------|-------------------------------------------------|-----------------------------------|
| `VAPID_PUBLIC_KEY`  | Clave pública VAPID (base64url).                | (vacío — push deshabilitado)      |
| `VAPID_PRIVATE_KEY` | Clave privada VAPID (base64url).                | (vacío — push deshabilitado)      |
| `VAPID_SUBJECT`     | Email de contacto para VAPID.                   | `mailto:soscubamap@proton.me`     |

Generar par de claves VAPID:

```bash
pip install pywebpush
python -c "from pywebpush import webpush; from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('PUBLIC:', v.public_key); print('PRIVATE:', v.private_key)"
```

## reCAPTCHA

| Variable                  | Descripción                        | Default  |
|---------------------------|------------------------------------|----------|
| `RECAPTCHA_V2_SITE_KEY`   | Site key de reCAPTCHA v2.          | (vacío — reCAPTCHA deshabilitado) |
| `RECAPTCHA_V2_SECRET_KEY` | Secret key de reCAPTCHA v2.        | (vacío)  |

## Rate Limiting

| Variable                | Descripción                                        | Default    |
|-------------------------|----------------------------------------------------|------------|
| `RATELIMIT_STORAGE_URI` | Backend de almacenamiento para rate limits.         | `memory://` |

En producción con múltiples workers, usar Redis: `redis://localhost:6379/0`.
Compatibilidad: también se acepta `RATELIMIT_STORAGE_URL` como alias legado.

## Conectividad (Cloudflare Radar)

Layer de datos de conectividad a internet por provincias, alimentado por Cloudflare Radar.

| Variable                                   | Descripción                                               | Default  |
|--------------------------------------------|-----------------------------------------------------------|----------|
| `CF_API_TOKEN`                             | Token de API de Cloudflare con permiso `Radar:Read`.      | (vacío — layer deshabilitado) |
| `CLOUDFLARE_RADAR_HTTP_TIMESERIES_URL`     | URL del endpoint de series temporales de Radar.           | (URL pública de Cuba) |
| `CLOUDFLARE_RADAR_API_BASE_URL`            | Base URL de API de Radar para alertas/speed/audiencia.    | `https://api.cloudflare.com/client/v4/radar` |
| `CF_RADAR_PROVINCE_GEOIDS_JSON`            | JSON mapeando nombre de provincia → GeoID de Cloudflare.  | (vacío)  |
| `CONNECTIVITY_FETCH_DELAY_SECONDS`         | Segundos entre peticiones al fetcher en background.       | `120`    |
| `CONNECTIVITY_FETCH_TIMEOUT_SECONDS`       | Timeout HTTP para peticiones a Radar.                     | `30`     |
| `CONNECTIVITY_ALERT_ACTIVE_MAX_AGE_HOURS` | Edad máxima (sin `end_date`) para considerar alerta activa.| `24`     |
| `CONNECTIVITY_STALE_AFTER_HOURS`           | Horas tras las que un snapshot se considera obsoleto.     | `8`      |
| `CONNECTIVITY_FRONTEND_REFRESH_SECONDS`    | Frecuencia de refresco del layer en el navegador.         | `300`    |
| `CONNECTIVITY_RADAR_ENRICHMENT_COOLDOWN_SECONDS` | Reutiliza el último enrichment (audiencia/speed/alertas) durante este cooldown para reducir 429. | `21600` |

## AIS buques rumbo a Cuba (AISStream)

Layer administrativo (beta) para visualizar buques con destino a puertos de Cuba detectados por AIS.

| Variable                                   | Descripción                                                               | Default |
|--------------------------------------------|---------------------------------------------------------------------------|---------|
| `AISSTREAM_ENABLED`                        | `1` habilita ingesta AISStream y capa admin; `0` la desactiva.           | `0` |
| `AISSTREAM_API_KEY`                        | API key de AISStream (websocket).                                         | (vacío) |
| `AISSTREAM_WS_URL`                         | URL websocket de AISStream.                                               | `wss://stream.aisstream.io/v0/stream` |
| `AISSTREAM_SUBSCRIPTION_BBOXES_JSON`       | Bounding boxes JSON para suscripción AIS.                                 | `[[[17.5,-88.5],[25.8,-73.0]]]` |
| `AISSTREAM_CAPTURE_MINUTES`                | Duración de cada corrida de captura en minutos.                           | `30` |
| `AISSTREAM_MAX_MESSAGES_PER_RUN`           | Límite de mensajes procesados por corrida para evitar sobrecarga.         | `120000` |
| `AISSTREAM_INGESTION_INTERVAL_SECONDS`     | Intervalo de ingesta automática en Celery Beat.                           | `86400` |
| `AISSTREAM_FRONTEND_REFRESH_SECONDS`       | Refresco del layer AIS en frontend (admin).                               | `1800` |
| `AISSTREAM_STALE_AFTER_HOURS`              | Marca como stale cuando la última corrida supera este umbral.             | `48` |
| `AISSTREAM_VESSEL_STALE_HOURS`             | Elimina buques no vistos después de N horas.                              | `168` |
| `AISSTREAM_MAX_TARGET_VESSELS`             | Máximo de puntos retornados por `/api/v1/ais/cuba-targets`.               | `1500` |
| `AISSTREAM_MIN_SOG_FOR_DIRECTION_KNOTS`    | Velocidad mínima para inferencia direccional de destinos genéricos.       | `1.0` |
| `AISSTREAM_MAX_DIRECTION_DELTA_DEG`        | Diferencia angular máxima COG→puerto para aceptar destino genérico.       | `70` |
| `AISSTREAM_MAX_DIRECTION_DISTANCE_NM`      | Distancia máxima al puerto (millas náuticas) para destino genérico.       | `1200` |

## Vuelos hacia Cuba (FlightRadar API Explorer)

Layer administrativo para visualizar vuelos con destino a aeropuertos cubanos con snapshots `24h/6h/2h`.

| Variable | Descripción | Default |
|----------|-------------|---------|
| `FLIGHTS_ENABLED` | `1` habilita ingesta/capa de vuelos; `0` la desactiva. | `0` |
| `FLIGHTS_API_KEY` | API key de FlightRadar Explorer. | (vacío) |
| `FLIGHTS_API_BASE_URL` | Base URL del API Explorer. | `https://fr24api.flightradar24.com/api` |
| `FLIGHTS_API_AUTH_HEADER` | Header de autenticación. | `Authorization` |
| `FLIGHTS_API_AUTH_PREFIX` | Prefijo del header (ej. `Bearer`). | `Bearer` |
| `FLIGHTS_API_ACCEPT_VERSION` | Valor de `Accept-Version` requerido por proveedor. | `v1` |
| `FLIGHTS_API_TIMEOUT_SECONDS` | Timeout HTTP por request. | `20` |
| `FLIGHTS_API_RESPONSE_LIMIT` | Límite por página/request (plan: `20`). | `20` |
| `FLIGHTS_API_REQUEST_RATE_LIMIT` | Máximo de requests por segundo (plan: `10`). | `10` |
| `FLIGHTS_API_MAX_RETRIES` | Reintentos automáticos por request en `429`. | `2` |
| `FLIGHTS_API_RETRY_BACKOFF_SECONDS` | Backoff base en segundos para reintentos (`429`). | `1.5` |
| `FLIGHTS_INGESTION_INTERVAL_SECONDS` | Intervalo de ingesta periódica por Celery Beat. | `900` |
| `FLIGHTS_FRONTEND_REFRESH_SECONDS` | Refresco frontend de la capa admin. | `300` |
| `FLIGHTS_STALE_AFTER_SECONDS` | Umbral de stale del snapshot. | `1800` |
| `FLIGHTS_REQUEST_CAP_PER_RUN` | Cap de requests por corrida en modo normal. | `120` |
| `FLIGHTS_SAFE_REQUEST_CAP_PER_RUN` | Cap de requests por corrida al entrar en modo seguro. | `40` |
| `FLIGHTS_MONTHLY_CREDIT_BUDGET` | Presupuesto mensual estimado de créditos. | `60000` |
| `FLIGHTS_GUARDRAIL_PERCENT` | Umbral de guardia de cuota (modo seguro). | `85` |
| `FLIGHTS_ESTIMATED_CREDIT_PER_REQUEST` | Crédito estimado por request para budgeting interno. | `1` |
| `FLIGHTS_BACKFILL_DAYS` | Backfill inicial en días (forzado o bootstrap inicial). | `7` |
| `FLIGHTS_BACKFILL_CHUNK_HOURS` | Tamaño de chunk para backfill histórico. | `24` |
| `FLIGHTS_POLLING_HISTORIC_HOURS` | Ventana histórica (horas) aplicada en cada polling periódico de Celery. | `24` |
| `FLIGHTS_BACKFILL_ON_EMPTY_DB` | `1` activa backfill inicial cuando BD está vacía. | `0` |
| `FLIGHTS_BACKFILL_HISTORIC_ENABLED` | `1` intenta backfill vía endpoint histórico (solo si tu plan/queries lo soportan). | `0` |
| `FLIGHTS_SAFE_MODE_SKIP_BACKFILL` | `1` evita backfill en modo seguro (ahorro de cuota). | `1` |
| `FLIGHTS_AIRPORTS_SYNC_ENABLED` | `1` habilita sync de catálogo de aeropuertos en API. | `0` |
| `FLIGHTS_AIRPORTS_SYNC_INTERVAL_SECONDS` | Frecuencia de sync del catálogo de aeropuertos cubanos. | `86400` |
| `FLIGHTS_AIRPORTS_MAX_PAGES` | Máximo de páginas de aeropuertos por corrida. | `10` |
| `FLIGHTS_EVENTS_MAX_PAGES` | Máximo de páginas de eventos/live por corrida (normal). | `5` |
| `FLIGHTS_SAFE_EVENTS_MAX_PAGES` | Máximo de páginas de eventos/live por corrida (safe mode). | `2` |
| `FLIGHTS_LAYER_MAX_POINTS` | Máximo de puntos retornados para la capa por ventana. | `2000` |
| `FLIGHTS_TRACK_POINT_LIMIT` | Máximo de puntos por track al seleccionar vuelo. | `2000` |
| `FLIGHTS_API_AIRPORTS_LIGHT_PATH` | Path endpoint “Airports light” (acepta `{code}` para lookup por aeropuerto). | `/static/airports/{code}/light` |
| `FLIGHTS_API_LIVE_POSITIONS_LIGHT_PATH` | Path endpoint “Live flight positions light”. | `/live/flight-positions/light` |
| `FLIGHTS_API_HISTORIC_EVENTS_LIGHT_PATH` | Path endpoint “Historic flight events light”. | `/historic/flight-events/light` |
| `FLIGHTS_API_HISTORIC_POSITIONS_LIGHT_PATH` | Path endpoint “Historic flight positions light” (usado para backfill por timestamp). | `/historic/flight-positions/light` |
| `FLIGHTS_API_FLIGHT_SUMMARY_LIGHT_PATH` | Path endpoint “Flight summary light” (enriquecimiento bajo demanda al abrir detalle). | `/flight-summary/light` |
| `FLIGHTS_API_TRACKS_PATH` | Path endpoint de tracks por vuelo seleccionado. | `/flights/tracks` |
| `FLIGHTS_LIVE_FILTER_BOUNDS` | Bounding box opcional para query `live` (formato `minLat,minLon,maxLat,maxLon`). | (vacío) |
| `FLIGHTS_LIVE_FILTER_AIRPORTS` | Filtro `airports` para query `live`; recomendado para Cuba: `inbound:CU`. | `inbound:CU` |
| `FLIGHTS_SUMMARY_ON_DEMAND_ENABLED` | `1` habilita enriquecimiento por `Flight summary light` al abrir detalle del avión. | `1` |
| `FLIGHTS_SUMMARY_ON_DEMAND_HOURS` | Rango de búsqueda alrededor del evento clicado para query de summary. | `48` |
| `FLIGHTS_SUMMARY_ON_DEMAND_LIMIT` | Límite de resultados solicitados en query summary on-demand. | `20` |
| `FLIGHTS_CUBA_AIRPORT_CODES` | Lista CSV base de códigos (IATA/ICAO) para detección de destino Cuba. | `MUHA,HAV,MUCU,SCU,MUVR,VRA,MUCC,CCC,MUCM,CMW,MUSC,SNU,MUBY,BCA,MUGT,BWW,MUMZ,MZG,MUCL,CYO,MUBA` |

## Protestas (RSS / NLP)

Layer de eventos de protesta inferidos automáticamente desde fuentes RSS.

| Variable                          | Descripción                                                          | Default |
|-----------------------------------|----------------------------------------------------------------------|---------|
| `PROTEST_RSS_FEEDS_JSON_PATH`     | Ruta al JSON de feeds RSS para la capa de protestas.                 | `app/static/data/protest_feeds.json` |
| `PROTEST_FETCH_TIMEOUT_SECONDS`   | Timeout HTTP al descargar cada feed.                                 | `30`    |
| `PROTEST_FETCH_INTERVAL_SECONDS`  | Intervalo en segundos para ingesta periódica (Celery Beat).          | `300`   |
| `PROTEST_FRONTEND_REFRESH_SECONDS`| Frecuencia de refresco del layer en el navegador.                    | `300`   |
| `PROTEST_MIN_CONFIDENCE_TO_SHOW`  | Puntuación mínima de confianza (0–100) para mostrar un evento.       | `35`    |
| `PROTEST_REQUIRE_SOURCE_URL`      | `1` = solo mostrar eventos con URL de fuente verificada.             | `1`     |
| `PROTEST_ALLOW_UNRESOLVED_TO_MAP` | `1` = mostrar eventos sin coordenadas resueltas.                     | `0`     |
| `PROTEST_MAX_ITEMS_PER_FEED`      | Máximo de ítems a procesar por feed en cada ciclo.                   | `120`   |
| `PROTEST_MAX_POST_AGE_DAYS`       | Ignorar ítems del feed con más de N días de antigüedad.              | `30`    |
| `PROTEST_KEYWORDS_STRONG`         | Palabras clave de alta confianza (CSV). Aumentan score fuertemente.  | (vacío) |
| `PROTEST_KEYWORDS_CONTEXT`        | Palabras de contexto (CSV). Requieren keyword fuerte para sumar.     | (vacío) |
| `PROTEST_KEYWORDS_WEAK`           | Palabras clave débiles (CSV). Suman poco score individualmente.      | (vacío) |
| `PROTEST_PLACE_ALIASES_JSON`      | JSON de alias de lugares cubanos para mejorar geocodificación.       | (vacío) |
| `PROTEST_SOURCE_NAME_OVERRIDES_JSON` | JSON de overrides para nombres de fuentes en la UI.              | (vacío) |

## Represores (catálogo externo + backup local)

| Variable                               | Descripción                                                                 | Default |
|----------------------------------------|-----------------------------------------------------------------------------|---------|
| `REPRESSOR_API_BASE_URL`               | Base URL de API externa de represores.                                      | `https://data.represorescubanos.com` |
| `REPRESSOR_PUBLIC_BASE_URL`            | Base URL pública de fichas (`/repressor-detail/<id>`).                      | `https://represorescubanos.com/repressor-detail` |
| `REPRESSOR_FETCH_TIMEOUT_SECONDS`      | Timeout HTTP por request de ingesta.                                        | `20` |
| `REPRESSOR_FETCH_RETRIES`              | Reintentos HTTP por request de ingesta.                                     | `3` |
| `REPRESSOR_FETCH_PAUSE_SECONDS`        | Pausa entre IDs durante ingesta para no saturar la fuente.                  | `0` |
| `REPRESSOR_SCAN_START_ID`              | ID inicial de escaneo.                                                      | `1` |
| `REPRESSOR_INGESTION_INTERVAL_SECONDS` | Intervalo de ingesta automática (Celery Beat).                              | `86400` |
| `REPRESSOR_BACKUP_JSON_PATH`           | Ruta del backup JSON local del catálogo sincronizado.                       | `data/repressors_backup_latest.json` |
| `REPRESSOR_RESIDENCE_AUTO_APPROVE`     | `1` publica automático reportes de vivienda; `0` los deja en moderación.    | `0` |

Notas de rango de ingesta:
- Primera ingesta: escanea desde `REPRESSOR_SCAN_START_ID` y avanza automáticamente hasta una racha larga de IDs inexistentes.
- Ingestas automáticas siguientes: comienzan en `último external_id local + 1` y se detienen al alcanzar una racha corta de IDs inexistentes.
- Si necesitas un rango fijo, usa argumentos explícitos `--start-id/--end-id` en `python -m scripts.fetch_repressors`.

## Celery (ingesta periódica)

| Variable                           | Descripción                                                          | Default |
|------------------------------------|----------------------------------------------------------------------|---------|
| `CELERY_BROKER_URL`                | URL del broker de Celery (recomendado Redis).                        | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND`            | Backend de resultados de Celery.                                     | `redis://localhost:6379/1` |
| `CELERY_TIMEZONE`                  | Zona horaria del scheduler Celery Beat.                              | `UTC`   |
| `CELERY_PROTEST_INGESTION_ENABLED` | `1` habilita el job periódico de ingesta de protestas.              | `1`     |
| `CELERY_PROTEST_QUEUE`             | Cola de Celery usada por la ingesta de protestas.                    | `ingestion` |
| `CELERY_CONNECTIVITY_POLLING_ENABLED` | `1` habilita el polling automático de conectividad.               | `1` |
| `CELERY_CONNECTIVITY_POLLING_INTERVAL_SECONDS` | Intervalo del polling de conectividad.                     | `7200` |
| `CELERY_CONNECTIVITY_SINGLE_CALL` | `1` usa una sola ronda por ciclo (menos llamadas a Radar); `0` usa dos rondas con delay. | `1` |
| `CELERY_CONNECTIVITY_QUEUE`        | Cola usada por el polling de conectividad.                           | `ingestion` |
| `CELERY_AIS_INGESTION_ENABLED`     | `1` habilita la ingesta periódica AIS (si `AISSTREAM_ENABLED=1`).    | `1` |
| `CELERY_AIS_QUEUE`                 | Cola usada por la ingesta AIS.                                        | `ingestion` |
| `CELERY_FLIGHTS_INGESTION_ENABLED` | `1` habilita la ingesta periódica de vuelos (si `FLIGHTS_ENABLED=1`). | `1` |
| `CELERY_FLIGHTS_QUEUE`             | Cola usada por la ingesta de vuelos.                                  | `ingestion` |
| `CELERY_REPRESSOR_INGESTION_ENABLED` | `1` habilita la ingesta periódica de represores.                   | `1` |
| `CELERY_REPRESSOR_QUEUE`           | Cola usada por la ingesta de represores.                             | `ingestion` |


## GitHub Actions / Crowdin

Secretos necesarios en **Settings → Secrets and variables → Actions** del repositorio para el workflow de i18n.

| Secret                   | Descripción                                                      |
|--------------------------|------------------------------------------------------------------|
| `CROWDIN_PROJECT_ID`     | ID numérico del proyecto en Crowdin.                             |
| `CROWDIN_PERSONAL_TOKEN` | Token personal de Crowdin con permiso de lectura/escritura.      |

## Aplicación

| Variable              | Descripción                                      | Default  |
|-----------------------|--------------------------------------------------|----------|
| `CHAT_DISABLED`       | Deshabilitar el chat en vivo. `1` = deshabilitado. | `0`     |
| `ASSET_VERSION`       | Versión para cache-busting de assets estáticos.  | `1`      |
| `TRUST_PROXY_HEADERS` | Confiar en cabeceras de proxy (X-Forwarded-For). `1` = sí. | `1` |
