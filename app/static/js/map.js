let map;
let markers = [];
let markerIndex = new Map();
let markerClusterGroup = null;
let markerClustersByCategory = {}; // Map to store cluster groups by category
let shapeLayers = [];
let connectivityGeoLayer;
let connectivityRefreshTimer;
let connectivityLastSnapshotId = null;
let connectivityLastRenderKey = null;
let connectivityRefreshSeconds = 300;
let connectivityWindowHours = 24;
let connectivityLastPayload = null;
let selectedConnectivityProvince = "";
let selectedConnectivityProvinceState = null;
let activeBaseMode = "map";
let mapHintElement;
let reportLegendSection;
let connectivityLegendOverlay;
let connectivityUpdatedLabel;
let connectivityTrafficPanel;
let connectivityTrafficValue;
let connectivityTrafficDelta;
let connectivityTrafficDrop;
let connectivityTrafficNote;
let connectivitySparkMain;
let connectivitySparkPrev;
let connectivityWindowButtons = [];
let connectivityProvincePanel;
let connectivityProvinceTitle;
let connectivityProvinceStatus;
let connectivityProvinceRange;
let connectivityProvinceChartMain;
let connectivityProvinceChartPrev;
let connectivityProvinceLog;
let connectivityRegionPanel;
let connectivityRegionChart;
let connectivityRegionLegend;
let connectivityRegionNote;
let connectivityRegionFocused = "";
let connectivityAlertPanel;
let connectivityAlertBadge;
let connectivityAlertCopy;
let connectivityAlertList;
let connectivityQualityPanel;
let connectivityQualityDownloadValue;
let connectivityQualityDownloadMeta;
let connectivityQualityLatencyValue;
let connectivityQualityLatencyMeta;
let connectivityQualityNote;
let connectivityAudiencePanel;
let connectivityAudienceMobileBar;
let connectivityAudienceDesktopBar;
let connectivityAudienceHumanBar;
let connectivityAudienceBotBar;
let connectivityAudienceMobileValue;
let connectivityAudienceDesktopValue;
let connectivityAudienceHumanValue;
let connectivityAudienceBotValue;
let connectivityAudienceNote;
let repressorLayerGroup;
let repressorLastPayload = null;
let repressorOverlay;
let repressorSummary;
let repressorStatsPanel;
let repressorDetailRequestSeq = 0;
let repressorStatsPayload = null;
let prisonerLayerGroup;
let prisonerLastPayload = null;
let prisonerOverlay;
let prisonerSummary;
let prisonerStatsPanel;
let prisonerDetailRequestSeq = 0;
let prisonerStatsPayload = null;
let prisonerProvinceFilter;
let prisonerMunicipalityFilter;
let prisonerPrisonFilter;
let protestLayerGroup;
let protestRefreshTimer;
let protestRefreshPromise;
let protestRefreshSeconds = 300;
let protestLastPayload = null;
let protestTimelineStartDay = "";
let protestTimelineEndDay = "";
let protestSelectedDay = "";
let protestSelectedStartDay = "";
let protestSelectedEndDay = "";
let protestSelectedMode = "day";
let protestSelectedFeatureId = null;
let protestOverlay;
let protestTimelineSlider;
let protestTimelineLabel;
let protestDayInput;
let protestStartInput;
let protestEndInput;
let protestApplyDayBtn;
let protestApplyRangeBtn;
let protestResetRangeBtn;
let protestSummary;
let protestDetailPanel;
let aisLayerGroup;
let aisRefreshTimer;
let aisRefreshSeconds = 1800;
let aisLastPayload = null;
let aisOverlay;
let aisSummary;
let aisPortList;
let flightsLayerGroup;
let flightsTrackLayer;
let flightsRefreshTimer;
let flightsRefreshSeconds = 300;
let flightsLastPayload = null;
let flightsOverlay;
let flightsSummary;
let flightsMeta;
let flightsAirportsList;
let flightsWindowButtons = [];
let flightsWindowHours = 24;
let flightsDetailRequestSeq = 0;
let flightsPhotoModalNode = null;
let reportDetailPanel;
let activePopup;
let alertTimer;
let alertConsolePanel;
let alertConsoleToggle;
let alertConsoleToggleLabel;
let alertConsoleUnreadBadge;
let alertConsoleUnreadCount = 0;
let knownAlertIds = new Set();
let alertsSnapshotReady = false;
let searchMarker;
let isAdmin = false;
let allPosts = [];
let mapImageModal;
let mapImageModalImg;
let mapImageModalCaption;
let pendingMarkers = [];
let mainBaseLayers = {};
let mapLayerRouteTemplate = "/map=__layer__";
let mapAppShell;
let mapSidePanel;
let mapSideScroll;
let mapPanelToggle;
let mapSheetHandle;
let selectedReportId = null;
let selectedLegendCategory = "all";
let mobileSheetState = "peek";
let mobileSheetPointerStartY = null;
let mobileSheetPointerId = null;
let mobileSheetDragStartOffsetPct = null;
let panelResizeInvalidateInterval = null;
let panelResizeInvalidateTimeout = null;

const CUBA_BOUNDS = {
  north: 24.2,
  south: 19.0,
  west: -86.2,
  east: -73.0,
};
const CARIBBEAN_BOUNDS = {
  north: 27.5,
  south: 14.0,
  west: -90.0,
  east: -58.0,
};
const CONNECTIVITY_PAN_BOUNDS = {
  north: 28.3,
  south: 10.8,
  west: -90.0,
  east: -58.0,
};
const FLIGHTS_WINDOW_OPTIONS = [2, 6, 24, 168];
const MOBILE_VIEWPORT_QUERY = "(max-width: 900px)";
const ALERT_PANEL_HIDDEN_COOKIE = "soscuba_alert_panel_hidden";
const ALERT_PANEL_HIDDEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const HAVANA_CENTER = [23.1136, -82.3666];
const MOBILE_HAVANA_ZOOM = 9;
const MAP_PROVIDER_LEAFLET = "leaflet";
const MAP_PROVIDER_GOOGLE = "google";
const MOBILE_SHEET_OFFSETS = {
  peek: 92,
  mid: 42,
  full: 6,
};
const MAP_MODE_TO_ROUTE_SLUG = {
  map: "mapa",
  satellite: "satelite",
  connectivity: "conectividad",
  repressors: "represores",
  prisoners: "prisioneros",
  protests: "protestas",
  ais: "buques-cuba",
  flights: "vuelos-cuba",
};
const ROUTE_SLUG_TO_MAP_MODE = {
  map: "map",
  mapa: "map",
  satellite: "satellite",
  satelite: "satellite",
  connectivity: "connectivity",
  conectividad: "connectivity",
  repressors: "repressors",
  represores: "repressors",
  prisoners: "prisoners",
  prisioneros: "prisoners",
  protests: "protests",
  protestas: "protests",
  ais: "ais",
  buques: "ais",
  "buques-cuba": "ais",
  ships: "ais",
  vessels: "ais",
  flights: "flights",
  vuelos: "flights",
  "vuelos-cuba": "flights",
  "flights-cuba": "flights",
};
const CONNECTIVITY_STATUS_COLORS = {
  normal: "#2E7D32",
  degraded: "#F9A825",
  severe: "#EF6C00",
  critical: "#C62828",
  unknown: "#667085",
};
const CONNECTIVITY_STATUS_LABELS = {
  normal: "Normal",
  degraded: "Degradacion leve",
  severe: "Problemas severos",
  critical: "Apagon o conectividad critica",
  unknown: "Sin datos",
};
const CONNECTIVITY_REGION_COLORS = [
  "#6ee7b7",
  "#f59e0b",
  "#38bdf8",
  "#fb7185",
  "#f97316",
  "#22d3ee",
  "#a3e635",
  "#facc15",
  "#2dd4bf",
  "#93c5fd",
  "#f472b6",
  "#34d399",
  "#eab308",
  "#60a5fa",
  "#4ade80",
  "#fda4af",
];
const PROTEST_EVENT_LABELS = {
  confirmed_protest: "Protesta confirmada",
  probable_protest: "Protesta probable",
  related_unrest: "Hecho relacionado",
  unresolved_location: "Ubicacion aproximada",
  context_only: "Contexto",
};
const PROTEST_EVENT_COLORS = {
  confirmed_protest: "#c62828",
  probable_protest: "#ef6c00",
  related_unrest: "#f9a825",
  unresolved_location: "#d97706",
  context_only: "#64748b",
};
const REPRESSOR_CONFIRMED_COLOR = "#16a34a";
const REPRESSOR_UNRESOLVED_COLOR = "#dc2626";
const repressorUnresolvedDetailCache = new Map();
const PRISONER_COUNT_COLOR = "#22c55e";
const prisonerTerritoryDetailCache = new Map();
const flightsDetailCacheByEvent = new Map();
const flightsDetailCacheByAircraft = new Map();
const AIS_MARKER_COLOR = "#0ea5e9";
const FLIGHTS_MARKER_COLOR = "#ef4444";
const MAP_POPUP_OPTIONS = {
  maxWidth: 320,
  maxHeight: 320,
  autoPan: true,
  keepInView: true,
  autoPanPaddingTopLeft: [24, 120],
  autoPanPaddingBottomRight: [24, 24],
};

function canUseGoogleMutant(provider) {
  if (provider !== MAP_PROVIDER_GOOGLE) return false;
  return (
    typeof L !== "undefined" &&
    L.gridLayer &&
    typeof L.gridLayer.googleMutant === "function" &&
    typeof window.google !== "undefined" &&
    window.google &&
    window.google.maps
  );
}

function buildMainBaseLayers(provider) {
  const useGoogle = canUseGoogleMutant(provider);

  if (useGoogle) {
    const mapLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const satelliteLayer = L.gridLayer.googleMutant({
      type: "hybrid",
      maxZoom: 20,
    });
    const connectivityLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const repressorLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const prisonerLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const protestLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const aisLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    const flightsLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    return {
      useGoogle,
      streetsLayer: mapLayer,
      satelliteLayer,
      satelliteLabelsLayer: null,
      connectivityBaseLayer: connectivityLayer,
      repressorBaseLayer: repressorLayer,
      prisonerBaseLayer: prisonerLayer,
      protestBaseLayer: protestLayer,
      aisBaseLayer: aisLayer,
      flightsBaseLayer: flightsLayer,
    };
  }

  const streetsLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });

  const satelliteLayer = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      attribution:
        'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
      maxZoom: 19,
    }
  );
  const satelliteLabelsLayer = L.tileLayer(
    "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    {
      attribution: "Labels &copy; Esri",
      maxZoom: 19,
    }
  );
  const connectivityBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  const repressorBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  const prisonerBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  const protestBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  const aisBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  const flightsBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  return {
    useGoogle,
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  };
}

function cubaLatLngBounds() {
  return L.latLngBounds(
    [CUBA_BOUNDS.south, CUBA_BOUNDS.west],
    [CUBA_BOUNDS.north, CUBA_BOUNDS.east]
  );
}

function caribbeanLatLngBounds() {
  return L.latLngBounds(
    [CARIBBEAN_BOUNDS.south, CARIBBEAN_BOUNDS.west],
    [CARIBBEAN_BOUNDS.north, CARIBBEAN_BOUNDS.east]
  );
}

function connectivityLatLngBounds() {
  return L.latLngBounds(
    [CONNECTIVITY_PAN_BOUNDS.south, CONNECTIVITY_PAN_BOUNDS.west],
    [CONNECTIVITY_PAN_BOUNDS.north, CONNECTIVITY_PAN_BOUNDS.east]
  );
}

function applyMapPanBoundsForMode(mode = "map") {
  if (!map) return;
  if (mode === "connectivity") {
    map.setMaxBounds(connectivityLatLngBounds());
    map.options.maxBoundsViscosity = 0.55;
    return;
  }
  if (mode === "flights") {
    map.setMaxBounds(null);
    map.options.maxBoundsViscosity = 0.0;
    return;
  }

  map.setMaxBounds(caribbeanLatLngBounds());
  map.options.maxBoundsViscosity = 1.0;
}

function enableMiddleClickPan(leafletMap) {
  const container = leafletMap?.getContainer?.();
  if (!container) return;

  let middleDown = false;
  let lastX = 0;
  let lastY = 0;

  const onMouseMove = (event) => {
    if (!middleDown) return;
    event.preventDefault();
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    if (!dx && !dy) return;
    leafletMap.panBy([-dx, -dy], { animate: false, noMoveStart: true });
    lastX = event.clientX;
    lastY = event.clientY;
  };

  const stopMiddlePan = () => {
    if (!middleDown) return;
    middleDown = false;
    container.style.cursor = "";
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  };

  const onMouseUp = (event) => {
    if (event.button !== 1 && !middleDown) return;
    stopMiddlePan();
  };

  container.addEventListener(
    "mousedown",
    (event) => {
      if (event.button !== 1) return;
      event.preventDefault();
      middleDown = true;
      lastX = event.clientX;
      lastY = event.clientY;
      container.style.cursor = "grabbing";
      window.addEventListener("mousemove", onMouseMove, { passive: false });
      window.addEventListener("mouseup", onMouseUp);
    },
    { passive: false }
  );

  container.addEventListener("auxclick", (event) => {
    if (event.button === 1) event.preventDefault();
  });
}

function disableMapNativeDragDrop(leafletMap) {
  const container = leafletMap?.getContainer?.();
  if (!container) return;

  const applyNoDragToNodes = () => {
    const nodes = container.querySelectorAll(
      "img, canvas, a, .leaflet-tile, .leaflet-layer, .leaflet-marker-icon, .leaflet-pane"
    );
    nodes.forEach((node) => {
      if (node instanceof HTMLElement) {
        node.draggable = false;
      }
    });
  };

  container.setAttribute("draggable", "false");
  container.addEventListener("dragstart", (event) => {
    event.preventDefault();
  });

  applyNoDragToNodes();
  leafletMap.on("layeradd", applyNoDragToNodes);
  leafletMap.on("popupopen", applyNoDragToNodes);
}

function setupSidePanelScrollIsolation(leafletMap) {
  if (!leafletMap || typeof L === "undefined") return;

  const targets = [mapSidePanel, mapSideScroll].filter(Boolean);
  if (!targets.length) return;

  const stopPropagation = (event) => {
    if (!event) return;
    L.DomEvent.stopPropagation(event);
  };

  targets.forEach((target) => {
    L.DomEvent.disableScrollPropagation(target);
    target.addEventListener("wheel", stopPropagation, { passive: false });
    target.addEventListener("touchmove", stopPropagation, { passive: true });
  });
}

function decorateMapLayersControl(layersControl) {
  const controlContainer = layersControl?.getContainer?.();
  if (!controlContainer) return;

  controlContainer.classList.add("map-layer-control");
  const toggle = controlContainer.querySelector(".leaflet-control-layers-toggle");
  if (!toggle) return;
  toggle.setAttribute("aria-label", "Capas");
  toggle.setAttribute("title", "Capas");
  toggle.classList.add("map-layer-toggle-btn");
  toggle.innerHTML = `
    <i class="fa-solid fa-layer-group" aria-hidden="true"></i>
    <span class="map-layer-toggle-label"><strong>Capas</strong></span>
  `;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeUrl(value) {
  const url = String(value || "").trim();
  if (!/^https?:\/\//i.test(url)) return "";
  return url.replaceAll('"', "%22").replaceAll("'", "%27");
}

function normalizeNameList(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (!item || typeof item !== "object") return "";
      const name = typeof item.name === "string" ? item.name.trim() : "";
      return name;
    })
    .filter(Boolean);
}

function normalizeLinkList(value) {
  const links = [];
  const append = (rawHref, rawLabel) => {
    const href = String(rawHref || "").trim();
    if (!href) return;
    const label = String(rawLabel || href).trim() || href;
    links.push({ href, label });
  };

  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (typeof item === "string") {
        append(item, item);
        return;
      }
      if (!item || typeof item !== "object") return;
      append(item.url || item.href || item.link || item.value, item.label || item.title || item.text);
    });
    return links;
  }

  if (typeof value === "string") {
    append(value, value);
    return links;
  }

  if (value && typeof value === "object") {
    append(value.url || value.href || value.link || value.value, value.label || value.title || value.text);
  }

  return links;
}

function normalizeBaseMode(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "map";
  return ROUTE_SLUG_TO_MAP_MODE[raw] || "map";
}

function mapModeRouteSlug(mode) {
  const normalized = normalizeBaseMode(mode);
  return MAP_MODE_TO_ROUTE_SLUG[normalized] || "mapa";
}

function parseBaseModeFromPath(pathname) {
  const path = String(pathname || "").trim();
  if (!path) return "map";

  const mapEqualMatch = path.match(/\/map=([^/?#]+)/i);
  if (mapEqualMatch && mapEqualMatch[1]) {
    try {
      return normalizeBaseMode(decodeURIComponent(mapEqualMatch[1]));
    } catch (_error) {
      return normalizeBaseMode(mapEqualMatch[1]);
    }
  }

  const mapSlashMatch = path.match(/\/map\/([^/?#]+)/i);
  if (mapSlashMatch && mapSlashMatch[1]) {
    try {
      return normalizeBaseMode(decodeURIComponent(mapSlashMatch[1]));
    } catch (_error) {
      return normalizeBaseMode(mapSlashMatch[1]);
    }
  }

  return "map";
}

function buildBaseModeRoutePath(mode) {
  const slug = mapModeRouteSlug(mode);
  const template = String(mapLayerRouteTemplate || "").trim();
  if (template.includes("__layer__")) {
    return template.replace("__layer__", slug);
  }
  return `/map=${slug}`;
}

function syncBaseModeRoute(mode, options = {}) {
  if (typeof window === "undefined" || !window.history || !window.location) return;
  const targetPath = buildBaseModeRoutePath(mode);
  if (!targetPath) return;

  const search = window.location.search || "";
  const hash = window.location.hash || "";
  const target = `${targetPath}${search}${hash}`;
  const current = `${window.location.pathname}${search}${hash}`;
  if (target === current) return;

  const method = options.replace ? "replaceState" : "pushState";
  const state = {
    ...(window.history.state || {}),
    map_base_mode: normalizeBaseMode(mode),
  };
  window.history[method](state, "", target);
}

function baseLayerForMode(mode) {
  const normalized = normalizeBaseMode(mode);
  const {
    streetsLayer,
    satelliteLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  } = mainBaseLayers || {};
  if (normalized === "satellite") return satelliteLayer;
  if (normalized === "connectivity") return connectivityBaseLayer;
  if (normalized === "repressors") return repressorBaseLayer;
  if (normalized === "prisoners") return prisonerBaseLayer;
  if (normalized === "protests") return protestBaseLayer;
  if (normalized === "ais") return aisBaseLayer;
  if (normalized === "flights") return flightsBaseLayer;
  return streetsLayer;
}

function modeForBaseLayer(layer) {
  if (!layer) return "map";
  const {
    streetsLayer,
    satelliteLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  } = mainBaseLayers || {};
  if (layer === satelliteLayer) return "satellite";
  if (layer === connectivityBaseLayer) return "connectivity";
  if (layer === repressorBaseLayer) return "repressors";
  if (layer === prisonerBaseLayer) return "prisoners";
  if (layer === protestBaseLayer) return "protests";
  if (layer === aisBaseLayer) return "ais";
  if (layer === flightsBaseLayer) return "flights";
  if (layer === streetsLayer) return "map";
  return "map";
}

function isWithinCubaBounds(location) {
  if (!location) return false;
  const lat = Number(location.lat);
  const lng = Number(location.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return false;
  return lat <= CUBA_BOUNDS.north && lat >= CUBA_BOUNDS.south && lng >= CUBA_BOUNDS.west && lng <= CUBA_BOUNDS.east;
}

function isMobileViewport() {
  return typeof window.matchMedia === "function" && window.matchMedia(MOBILE_VIEWPORT_QUERY).matches;
}

function readCookie(name) {
  if (!name || typeof document === "undefined") return "";
  const cookieName = `${name}=`;
  const parts = String(document.cookie || "").split(";");
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed.startsWith(cookieName)) continue;
    return decodeURIComponent(trimmed.slice(cookieName.length));
  }
  return "";
}

function writeCookie(name, value, maxAgeSeconds = ALERT_PANEL_HIDDEN_COOKIE_MAX_AGE) {
  if (!name || typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(String(value || ""))}; Max-Age=${Math.max(
    0,
    Number(maxAgeSeconds) || 0
  )}; Path=/; SameSite=Lax${secure}`;
}

function clearCookie(name) {
  writeCookie(name, "", 0);
}

function isAlertPanelHiddenByCookie() {
  return readCookie(ALERT_PANEL_HIDDEN_COOKIE) === "1";
}

function persistAlertPanelCollapsed(collapsed) {
  if (collapsed) {
    writeCookie(ALERT_PANEL_HIDDEN_COOKIE, "1");
    return;
  }
  clearCookie(ALERT_PANEL_HIDDEN_COOKIE);
}

function parseDurationToMs(value, fallbackMs = 760) {
  const raw = String(value || "").trim();
  if (!raw) return fallbackMs;
  if (raw.endsWith("ms")) {
    const parsed = parseFloat(raw.slice(0, -2));
    return Number.isFinite(parsed) ? parsed : fallbackMs;
  }
  if (raw.endsWith("s")) {
    const parsed = parseFloat(raw.slice(0, -1));
    return Number.isFinite(parsed) ? parsed * 1000 : fallbackMs;
  }
  const parsed = parseFloat(raw);
  return Number.isFinite(parsed) ? parsed : fallbackMs;
}

function getPanelShellDurationMs() {
  if (!mapAppShell) return 760;
  const styles = window.getComputedStyle(mapAppShell);
  return parseDurationToMs(styles.getPropertyValue("--panel-shell-duration"), 760);
}

function clearPanelResizeInvalidateTimers() {
  if (panelResizeInvalidateInterval) {
    window.clearInterval(panelResizeInvalidateInterval);
    panelResizeInvalidateInterval = null;
  }
  if (panelResizeInvalidateTimeout) {
    window.clearTimeout(panelResizeInvalidateTimeout);
    panelResizeInvalidateTimeout = null;
  }
}

function scheduleMapResizeInvalidate() {
  if (!map || isMobileViewport()) return;
  clearPanelResizeInvalidateTimers();

  const durationMs = getPanelShellDurationMs();
  const tickMs = 90;

  map.invalidateSize({ pan: false, animate: false });

  panelResizeInvalidateInterval = window.setInterval(() => {
    if (!map) return;
    map.invalidateSize({ pan: false, animate: false });
  }, tickMs);

  panelResizeInvalidateTimeout = window.setTimeout(() => {
    clearPanelResizeInvalidateTimers();
    if (!map) return;
    map.invalidateSize({ pan: false, animate: false });
  }, durationMs + 140);
}

function syncMapShellHeight() {
  if (!mapAppShell) return;
  const content = document.querySelector("main.content");
  const header = document.querySelector(".site-header");
  const footer = document.querySelector(".site-footer");
  const flashGroup = content ? content.querySelector(".flash-group") : null;
  const contentStyle = content ? window.getComputedStyle(content) : null;
  const padTop = contentStyle ? parseFloat(contentStyle.paddingTop) || 0 : 0;
  const padBottom = contentStyle ? parseFloat(contentStyle.paddingBottom) || 0 : 0;
  const reserved =
    (header ? header.offsetHeight : 0) +
    (footer ? footer.offsetHeight : 0) +
    (flashGroup ? flashGroup.offsetHeight : 0) +
    padTop +
    padBottom +
    14;
  const height = Math.max(420, Math.floor(window.innerHeight - reserved));
  mapAppShell.style.setProperty("--map-shell-height", `${height}px`);
  if (map) {
    requestAnimationFrame(() => {
      map.invalidateSize();
    });
  }
}

function setDesktopPanelCollapsed(collapsed) {
  if (!mapAppShell || !mapPanelToggle) return;
  mapAppShell.classList.toggle("is-panel-collapsed", collapsed);
  const label = collapsed ? "Mostrar panel" : "Ocultar panel";
  mapPanelToggle.setAttribute("aria-label", label);
  mapPanelToggle.setAttribute("title", label);
  mapPanelToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  mapPanelToggle.classList.toggle("is-collapsed", collapsed);
  scheduleMapResizeInvalidate();
}

function setMobileSheetState(nextState, options = {}) {
  if (!mapSidePanel) return;
  const state = MOBILE_SHEET_OFFSETS[nextState] !== undefined ? nextState : "mid";
  const animate = options.animate !== false;
  mobileSheetState = state;
  mapSidePanel.dataset.mobileState = state;
  mapSidePanel.style.setProperty("--mobile-sheet-offset", `${MOBILE_SHEET_OFFSETS[state]}%`);
  mapSidePanel.classList.toggle("is-dragging", !animate);
}

function getClosestMobileSheetState(offsetPercent) {
  const entries = Object.entries(MOBILE_SHEET_OFFSETS);
  if (!entries.length) return "mid";
  let bestState = entries[0][0];
  let bestDiff = Math.abs(offsetPercent - Number(entries[0][1]));
  for (let index = 1; index < entries.length; index += 1) {
    const [state, value] = entries[index];
    const diff = Math.abs(offsetPercent - Number(value));
    if (diff < bestDiff) {
      bestState = state;
      bestDiff = diff;
    }
  }
  return bestState;
}

function moveMobileSheetState(direction) {
  const order = ["peek", "mid", "full"];
  const currentIndex = Math.max(0, order.indexOf(mobileSheetState));
  const nextIndex = Math.min(order.length - 1, Math.max(0, currentIndex + direction));
  setMobileSheetState(order[nextIndex]);
}

function ensureContextPanelVisible(options = {}) {
  const mobileState = options.mobileState || "mid";
  if (isMobileViewport()) {
    setMobileSheetState(mobileState);
    return;
  }
  setDesktopPanelCollapsed(false);
}

function syncReportDetailPanelLayout() {
  if (!mapSidePanel) return;
  const prioritizeReportDetail = activeBaseMode === "map" || activeBaseMode === "satellite";
  mapSidePanel.classList.toggle("is-report-priority", prioritizeReportDetail);
  mapSidePanel.classList.remove("is-report-after-legend");
}

function setupContextPanelLayout() {
  mapAppShell = document.getElementById("mapAppShell");
  mapSidePanel = document.getElementById("mapSidePanel");
  mapSideScroll = mapSidePanel ? mapSidePanel.querySelector(".map-side-scroll") : null;
  mapPanelToggle = document.getElementById("mapPanelToggle");
  mapSheetHandle = document.getElementById("mapSheetHandle");
  if (!mapAppShell || !mapSidePanel) return;

  document.body.classList.add("map-dashboard-page");
  const content = document.querySelector("main.content");
  if (content) {
    content.classList.add("map-dashboard-content");
  }
  syncReportDetailPanelLayout();

  const syncViewportLayout = () => {
    syncMapShellHeight();
    if (isMobileViewport()) {
      mapAppShell.classList.remove("is-panel-collapsed");
      setMobileSheetState(mobileSheetState || "peek");
    } else {
      mapSidePanel.classList.remove("is-dragging");
      mapSidePanel.style.removeProperty("--mobile-sheet-offset");
      if (!mapAppShell.classList.contains("is-panel-collapsed")) {
        setDesktopPanelCollapsed(false);
      } else {
        setDesktopPanelCollapsed(true);
      }
    }
  };

  if (mapPanelToggle) {
    mapPanelToggle.addEventListener("click", () => {
      if (isMobileViewport()) {
        setMobileSheetState("full");
        return;
      }
      const collapsed = !mapAppShell.classList.contains("is-panel-collapsed");
      setDesktopPanelCollapsed(collapsed);
      syncMapShellHeight();
    });
  }

  if (mapSheetHandle) {
    mapSheetHandle.addEventListener("pointerdown", (event) => {
      if (!isMobileViewport()) return;
      mobileSheetPointerStartY = event.clientY;
      mobileSheetPointerId = event.pointerId;
      mobileSheetDragStartOffsetPct = Number(MOBILE_SHEET_OFFSETS[mobileSheetState] ?? MOBILE_SHEET_OFFSETS.mid);
      mapSidePanel.classList.add("is-dragging");
      if (mapSheetHandle.setPointerCapture) {
        try {
          mapSheetHandle.setPointerCapture(event.pointerId);
        } catch (_error) {
          // ignore capture failures
        }
      }
    });

    const releasePointer = () => {
      mobileSheetPointerStartY = null;
      mobileSheetPointerId = null;
      mobileSheetDragStartOffsetPct = null;
      mapSidePanel.classList.remove("is-dragging");
    };

    mapSheetHandle.addEventListener("pointermove", (event) => {
      if (!isMobileViewport()) return;
      if (!Number.isFinite(mobileSheetPointerStartY)) return;
      if (mobileSheetPointerId !== null && event.pointerId !== mobileSheetPointerId) return;

      const panelHeight = mapSidePanel.getBoundingClientRect().height || 0;
      if (!panelHeight) return;

      const startOffsetPct = Number.isFinite(mobileSheetDragStartOffsetPct)
        ? mobileSheetDragStartOffsetPct
        : Number(MOBILE_SHEET_OFFSETS[mobileSheetState] ?? MOBILE_SHEET_OFFSETS.mid);
      const deltaPx = event.clientY - mobileSheetPointerStartY;
      const minOffsetPx = (MOBILE_SHEET_OFFSETS.full / 100) * panelHeight;
      const maxOffsetPx = (MOBILE_SHEET_OFFSETS.peek / 100) * panelHeight;
      const startOffsetPx = (startOffsetPct / 100) * panelHeight;
      const nextOffsetPx = Math.max(minOffsetPx, Math.min(maxOffsetPx, startOffsetPx + deltaPx));
      const nextOffsetPct = (nextOffsetPx / panelHeight) * 100;
      mapSidePanel.style.setProperty("--mobile-sheet-offset", `${nextOffsetPct}%`);
    });

    mapSheetHandle.addEventListener("pointerup", (event) => {
      if (!isMobileViewport()) return;
      const startY = mobileSheetPointerStartY;
      if (!Number.isFinite(startY)) {
        releasePointer();
        setMobileSheetState("full");
        return;
      }
      const deltaY = event.clientY - startY;
      const rawOffset = parseFloat(mapSidePanel.style.getPropertyValue("--mobile-sheet-offset") || "");
      const hasDragged = Math.abs(deltaY) >= 10;
      releasePointer();
      if (!hasDragged) {
        moveMobileSheetState(1);
        return;
      }
      const targetState = Number.isFinite(rawOffset)
        ? getClosestMobileSheetState(rawOffset)
        : mobileSheetState;
      setMobileSheetState(targetState);
    });

    mapSheetHandle.addEventListener("pointercancel", releasePointer);
  }

  window.addEventListener("resize", syncViewportLayout, { passive: true });
  syncViewportLayout();
}

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("mapSearch");
  if (searchInput) {
    const placeholders = [
      "Ej: Sector PNR",
      "Ej: Prision",
      "Ej: Unidad Militar",
      "Ej: Tropas",
      "Ej: Estacion de policia",
      "Ej: Centro de detencion",
      "Ej: Brigada Especial",
    ];
    const pick = placeholders[Math.floor(Math.random() * placeholders.length)];
    searchInput.setAttribute("placeholder", pick);
  }

  setupContextPanelLayout();
  initMap();
});

function setupMapImageModal() {
  mapImageModal = document.getElementById("mapImageModal");
  mapImageModalImg = document.getElementById("mapImageModalImg");
  mapImageModalCaption = document.getElementById("mapImageModalCaption");
  if (!mapImageModal || !mapImageModalImg) return;

  const close = () => {
    mapImageModal.setAttribute("aria-hidden", "true");
    mapImageModal.classList.remove("open");
    mapImageModalImg.src = "";
    if (mapImageModalCaption) mapImageModalCaption.textContent = "";
  };

  document.querySelectorAll("[data-close-map-image]").forEach((btn) => {
    btn.addEventListener("click", close);
  });
}

const CATEGORY_ICONS = {
  "accion-represiva": "fa-hand-fist",
  "movimiento-tropas": "fa-bolt",
  "desconexion-internet": "fa-wifi",
  "residencia-represor": "fa-house-chimney-user",
  "centro-penitenciario": "fa-landmark-dome",
  "estacion-policia": "fa-building-shield",
  "escuela-pcc": "fa-graduation-cap",
  "sede-pcc": "fa-people-group",
  "sede-gobierno": "fa-building-columns",
  "sede-ujc": "fa-flag",
  "sede-seguridad-estado": "fa-user-secret",
  "unidad-militar": "fa-person-military-pointing",
  "base-espionaje": "fa-satellite-dish",
  "otros": "fa-circle-question",
};

const CATEGORY_IMAGES = {
  "sede-pcc": "/static/img/Communist_Party_of_Cuba_logo.svg.png",
  "sede-ujc": "/static/img/ujc.png",
};

const ALERT_SLUGS = new Set(["accion-represiva", "movimiento-tropas", "desconexion-internet"]);

function isAlertCategory(slug) {
  return ALERT_SLUGS.has(slug);
}

function createMarkerIcon(iconClass, imageUrl, slug, pending) {
  const classes = ["pin-icon"];
  if (isAlertCategory(slug)) classes.push("alert");
  if (pending) classes.push("pending");
  const iconHtml = imageUrl
    ? `<img src="${imageUrl}" alt="" class="pin-image" />`
    : `<i class="fa-solid ${iconClass}"></i>`;

  return L.divIcon({
    className: "pin-icon-wrap",
    html: `<div class="${classes.join(" ")}">${iconHtml}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function createClusterIcon(cluster, slug) {
  const childCount = cluster.getChildCount();
  const iconClass = CATEGORY_ICONS[slug] || "fa-location-dot";
  const imageUrl = CATEGORY_IMAGES[slug];
  
  // Create a div that will contain both the category icon and the count
  let html;
  if (imageUrl) {
    html = `<div class="cluster-icon-content">
      <img src="${imageUrl}" alt="" class="cluster-image" />
      <span class="cluster-count">${childCount}</span>
    </div>`;
  } else {
    html = `<div class="cluster-icon-content">
      <i class="fa-solid ${iconClass}"></i>
      <span class="cluster-count">${childCount}</span>
    </div>`;
  }

  const size = childCount < 10 ? 33 : childCount < 100 ? 40 : 48;
  
  return L.divIcon({
    html: html,
    className: "cluster-icon-wrap",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function syncLegend() {
  const items = document.querySelectorAll(".legend-item[data-slug]");
  items.forEach((item) => {
    const slug = item.dataset.slug;
    const iconClass = slug === "__all__" ? "fa-layer-group" : CATEGORY_ICONS[slug] || "fa-location-dot";
    const icon = item.querySelector("i");
    if (icon) {
      icon.className = `fa-solid ${iconClass}`;
    }
  });
}

function setLegendCategoryFilter(value, options = {}) {
  const normalized = String(value || "all").trim() || "all";
  selectedLegendCategory = normalized;
  const buttons = document.querySelectorAll(".legend-item[data-category-filter]");
  buttons.forEach((button) => {
    const key = String(button.dataset.categoryFilter || "all");
    const isActive = key === selectedLegendCategory;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
  if (options.apply !== false) {
    applyFilters();
  }
}

function setupLegendCategoryFilter() {
  const buttons = document.querySelectorAll(".legend-item[data-category-filter]");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = String(button.dataset.categoryFilter || "all");
      if (key === selectedLegendCategory) return;
      setLegendCategoryFilter(key);
    });
  });
  setLegendCategoryFilter(selectedLegendCategory, { apply: false });
}

function clearMarkers() {
  // Clear all category-based cluster groups
  Object.keys(markerClustersByCategory).forEach((slug) => {
    const cluster = markerClustersByCategory[slug];
    if (cluster) {
      cluster.clearLayers();
    }
  });
  
  markers = [];
  pendingMarkers.forEach((marker) => marker.remove());
  pendingMarkers = [];
  shapeLayers.forEach((layer) => layer.remove());
  shapeLayers = [];
  markerIndex = new Map();
}

function closeActivePopup() {
  if (!map || !activePopup) return;
  map.closePopup(activePopup);
  activePopup = null;
}

async function switchBaseMode(nextMode, options = {}) {
  if (!map || !mainBaseLayers) return;

  let mode = normalizeBaseMode(nextMode);
  if ((mode === "ais" || mode === "flights") && !isAdmin) {
    mode = "map";
  }
  applyMapPanBoundsForMode(mode);
  const {
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  } = mainBaseLayers;
  const targetLayer = baseLayerForMode(mode);

  [
    streetsLayer,
    satelliteLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  ]
    .filter(Boolean)
    .forEach((layer) => {
      if (layer !== targetLayer && map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    });

  if (targetLayer && !map.hasLayer(targetLayer)) {
    targetLayer.addTo(map);
  }

  if (mode === "connectivity") {
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }
    if (activeBaseMode === "repressors") {
      disableRepressorMode();
    }
    if (activeBaseMode === "prisoners") {
      disablePrisonerMode();
    }
    if (activeBaseMode === "ais") {
      disableAISMode();
    }
    if (activeBaseMode === "flights") {
      disableFlightsMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enableConnectivityMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("connectivity", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (mode === "repressors") {
    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }
    if (activeBaseMode === "prisoners") {
      disablePrisonerMode();
    }
    if (activeBaseMode === "ais") {
      disableAISMode();
    }
    if (activeBaseMode === "flights") {
      disableFlightsMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enableRepressorMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("repressors", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (mode === "protests") {
    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "repressors") {
      disableRepressorMode();
    }
    if (activeBaseMode === "prisoners") {
      disablePrisonerMode();
    }
    if (activeBaseMode === "ais") {
      disableAISMode();
    }
    if (activeBaseMode === "flights") {
      disableFlightsMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enableProtestMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("protests", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (mode === "prisoners") {
    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "repressors") {
      disableRepressorMode();
    }
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }
    if (activeBaseMode === "ais") {
      disableAISMode();
    }
    if (activeBaseMode === "flights") {
      disableFlightsMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enablePrisonerMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("prisoners", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (mode === "ais") {
    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "repressors") {
      disableRepressorMode();
    }
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }
    if (activeBaseMode === "prisoners") {
      disablePrisonerMode();
    }
    if (activeBaseMode === "flights") {
      disableFlightsMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enableAISMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("ais", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (mode === "flights") {
    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "repressors") {
      disableRepressorMode();
    }
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }
    if (activeBaseMode === "prisoners") {
      disablePrisonerMode();
    }
    if (activeBaseMode === "ais") {
      disableAISMode();
    }
    if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }
    await enableFlightsMode();
    syncReportDetailPanelLayout();
    if (options.syncRoute !== false) {
      syncBaseModeRoute("flights", { replace: options.replaceRoute === true });
    }
    return;
  }

  if (activeBaseMode === "connectivity") {
    disableConnectivityMode();
  }
  if (activeBaseMode === "protests") {
    disableProtestMode();
  }
  if (activeBaseMode === "repressors") {
    disableRepressorMode();
  }
  if (activeBaseMode === "prisoners") {
    disablePrisonerMode();
  }
  if (activeBaseMode === "ais") {
    disableAISMode();
  }
  if (activeBaseMode === "flights") {
    disableFlightsMode();
  }

  activeBaseMode = mode === "satellite" ? "satellite" : "map";
  syncReportDetailPanelLayout();
  if (satelliteLabelsLayer && activeBaseMode === "satellite") {
    if (!map.hasLayer(satelliteLabelsLayer)) satelliteLabelsLayer.addTo(map);
  } else if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
    map.removeLayer(satelliteLabelsLayer);
  }

  setMapHintVisible(true);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  renderReportDetail(null);
  await applyFilters();

  if (options.syncRoute !== false) {
    syncBaseModeRoute(activeBaseMode, { replace: options.replaceRoute === true });
  }
}

async function ensureMapModeForReportFocus() {
  if (!map || !mainBaseLayers?.streetsLayer) return;
  await switchBaseMode("map", { syncRoute: true });
}

function setMapHintVisible(visible) {
  if (!mapHintElement) return;
  mapHintElement.hidden = !visible;
}

function setReportLegendVisible(visible) {
  if (!reportLegendSection) return;
  reportLegendSection.hidden = !visible;
}

function setReportDetailVisible(visible) {
  if (!reportDetailPanel) return;
  reportDetailPanel.hidden = !visible;
}

function setConnectivityLegendVisible(visible) {
  if (!connectivityLegendOverlay) return;
  connectivityLegendOverlay.hidden = !visible;
}

function setProtestOverlayVisible(visible) {
  if (!protestOverlay) return;
  protestOverlay.hidden = !visible;
}

function setRepressorOverlayVisible(visible) {
  if (!repressorOverlay) return;
  repressorOverlay.hidden = !visible;
}

function setPrisonerOverlayVisible(visible) {
  if (!prisonerOverlay) return;
  prisonerOverlay.hidden = !visible;
}

function setAISOverlayVisible(visible) {
  if (!aisOverlay) return;
  aisOverlay.hidden = !visible;
}

function setFlightsOverlayVisible(visible) {
  if (!flightsOverlay) return;
  flightsOverlay.hidden = !visible;
}

function setActiveConnectivityWindow(hours) {
  const numeric = Number(hours);
  if (![2, 6, 24].includes(numeric)) return;
  connectivityWindowHours = numeric;
  connectivityWindowButtons.forEach((button) => {
    const buttonHours = Number(button?.dataset?.connectivityWindowHours);
    const isActive = buttonHours === connectivityWindowHours;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function setActiveFlightsWindow(hours) {
  const numeric = Number(hours);
  if (!FLIGHTS_WINDOW_OPTIONS.includes(numeric)) return;
  flightsWindowHours = numeric;
  flightsWindowButtons.forEach((button) => {
    const buttonHours = Number(button?.dataset?.flightsWindowHours);
    const isActive = buttonHours === flightsWindowHours;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function formatUtcLabel(timestamp) {
  if (!timestamp) return "";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("es-ES", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  });
}

function formatLabelInZone(timestamp, timeZone) {
  if (!timestamp) return "";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return "";
  const parts = new Intl.DateTimeFormat("es-ES", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
  }).formatToParts(parsed);
  const getPart = (type) => parts.find((item) => item.type === type)?.value || "";
  const year = getPart("year");
  const month = getPart("month");
  const day = getPart("day");
  const hour = getPart("hour");
  const minute = getPart("minute");
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function formatUtcAndCuba(timestamp) {
  const utc = formatLabelInZone(timestamp, "UTC");
  const cuba = formatLabelInZone(timestamp, "America/Havana");
  if (!utc && !cuba) return "N/D";
  if (!utc) return `${cuba} (Cuba)`;
  if (!cuba) return `${utc} UTC`;
  return `${utc} UTC (${cuba} Cuba)`;
}

function formatMetricValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  if (Math.abs(numeric) >= 1000) {
    return numeric.toLocaleString("es-ES", { maximumFractionDigits: 0 });
  }
  if (Math.abs(numeric) >= 10) {
    return numeric.toLocaleString("es-ES", { maximumFractionDigits: 2 });
  }
  return numeric.toLocaleString("es-ES", { maximumFractionDigits: 6 });
}

function formatPercentValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(1)}%`;
}

function formatPercentCompact(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  return `${numeric.toFixed(1)}%`;
}

function formatSignedPercentDelta(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(1)}%`;
}

function formatMbps(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  return `${numeric.toFixed(2)} Mbps`;
}

function formatMilliseconds(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  return `${numeric.toFixed(1)} ms`;
}

function clampPercentWidth(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(100, Math.max(0, numeric));
}

function formatConnectivityMiniUtcLabel(tsMs) {
  const numeric = Number(tsMs);
  if (!Number.isFinite(numeric)) return "";
  const parsed = new Date(numeric);
  if (Number.isNaN(parsed.getTime())) return "";
  const day = String(parsed.getUTCDate()).padStart(2, "0");
  const month = String(parsed.getUTCMonth() + 1).padStart(2, "0");
  const hour = String(parsed.getUTCHours()).padStart(2, "0");
  const minute = String(parsed.getUTCMinutes()).padStart(2, "0");
  return `${day}/${month} ${hour}:${minute}`;
}

function getConnectivityRegionTrendMeta(changePct) {
  const numeric = Number(changePct);
  if (!Number.isFinite(numeric)) {
    return { label: "Sin cambio", cssClass: "is-stable" };
  }
  if (numeric <= -5) {
    return { label: "Bajando", cssClass: "is-down" };
  }
  if (numeric >= 5) {
    return { label: "Subiendo", cssClass: "is-up" };
  }
  return { label: "Estable", cssClass: "is-stable" };
}

function buildSparklinePath(values, minValue, maxValue, width = 280, height = 56, pad = 4) {
  if (!Array.isArray(values) || values.length < 2) return "";
  const valid = values.filter((value) => Number.isFinite(Number(value))).map((value) => Number(value));
  if (valid.length < 2) return "";

  const min = Number.isFinite(minValue) ? Number(minValue) : Math.min(...valid);
  const max = Number.isFinite(maxValue) ? Number(maxValue) : Math.max(...valid);
  const span = Math.max(max - min, 1e-9);
  const innerWidth = Math.max(width - pad * 2, 1);
  const innerHeight = Math.max(height - pad * 2, 1);

  let path = "";
  values.forEach((value, idx) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return;
    const x = pad + (values.length === 1 ? 0 : (idx / (values.length - 1)) * innerWidth);
    const y = height - pad - ((numeric - min) / span) * innerHeight;
    path += `${path ? " L" : "M"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return path;
}

function buildTimeseriesPath(
  points,
  minTsMs,
  maxTsMs,
  minValue,
  maxValue,
  width = 280,
  height = 160,
  pad = 8
) {
  if (!Array.isArray(points) || points.length < 2) return "";
  const valid = points.filter(
    (point) => Number.isFinite(Number(point?.ts_ms)) && Number.isFinite(Number(point?.value))
  );
  if (valid.length < 2) return "";

  const tsMin = Number.isFinite(minTsMs) ? Number(minTsMs) : valid[0].ts_ms;
  const tsMax = Number.isFinite(maxTsMs) ? Number(maxTsMs) : valid[valid.length - 1].ts_ms;
  const valueMin = Number.isFinite(minValue)
    ? Number(minValue)
    : Math.min(...valid.map((point) => Number(point.value)));
  const valueMax = Number.isFinite(maxValue)
    ? Number(maxValue)
    : Math.max(...valid.map((point) => Number(point.value)));

  const tsSpan = Math.max(tsMax - tsMin, 1);
  const valueSpan = Math.max(valueMax - valueMin, 1e-9);
  const innerWidth = Math.max(width - pad * 2, 1);
  const innerHeight = Math.max(height - pad * 2, 1);

  let path = "";
  valid.forEach((point) => {
    const x = pad + ((point.ts_ms - tsMin) / tsSpan) * innerWidth;
    const y = height - pad - ((Number(point.value) - valueMin) / valueSpan) * innerHeight;
    path += `${path ? " L" : "M"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return path;
}

function getConnectivityRegionSeries(payload) {
  const byProvince = payload?.http_requests_window_by_province;
  if (!byProvince || typeof byProvince !== "object") return [];

  return Object.entries(byProvince)
    .map(([provinceName, summary]) => {
      const regionName = String(provinceName || "").trim();
      const baseSeries = Array.isArray(summary?.series_main) ? summary.series_main : [];
      const dedupedByTs = new Map();
      baseSeries.forEach((point) => {
        const timestampText = String(point?.timestamp_utc || "").trim();
        const tsMs = Date.parse(timestampText);
        const value = Number(point?.value);
        if (!Number.isFinite(tsMs) || !Number.isFinite(value)) return;
        dedupedByTs.set(tsMs, {
          timestamp_utc: timestampText,
          ts_ms: tsMs,
          value,
        });
      });
      const series = Array.from(dedupedByTs.values()).sort((a, b) => a.ts_ms - b.ts_ms);
      if (!regionName || !series.length) return null;

      const first = series[0];
      const latest = series[series.length - 1];
      const changePct =
        Number.isFinite(first?.value) && first.value > 0
          ? ((latest.value - first.value) / first.value) * 100
          : null;

      return {
        name: regionName,
        series,
        latest_value: latest.value,
        change_pct: changePct,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name, "es", { sensitivity: "base" }));
}

function getConnectivityRegionColor(regionName) {
  const text = String(regionName || "");
  let hash = 0;
  for (let idx = 0; idx < text.length; idx += 1) {
    hash = (hash * 31 + text.charCodeAt(idx)) >>> 0;
  }
  return CONNECTIVITY_REGION_COLORS[hash % CONNECTIVITY_REGION_COLORS.length];
}

function renderConnectivityRegionChart(payload) {
  if (
    !connectivityRegionPanel ||
    !connectivityRegionChart ||
    !connectivityRegionLegend ||
    !connectivityRegionNote
  ) {
    return;
  }

  const regionSeries = getConnectivityRegionSeries(payload).map((item) => ({
    ...item,
    key: normalizeProvinceName(item.name),
  }));
  if (!payload || !regionSeries.length) {
    connectivityRegionFocused = "";
    connectivityRegionChart.innerHTML = "";
    connectivityRegionNote.textContent = "Sin serie regional disponible para la ventana activa.";
    connectivityRegionLegend.innerHTML =
      '<div class="connectivity-region-legend-empty">Sin regiones con datos.</div>';
    return;
  }

  const allPoints = regionSeries.flatMap((item) => item.series || []);
  const allTimestamps = allPoints.map((point) => Number(point.ts_ms)).filter(Number.isFinite);
  const allValues = allPoints.map((point) => Number(point.value)).filter(Number.isFinite);
  if (!allTimestamps.length || !allValues.length) {
    connectivityRegionFocused = "";
    connectivityRegionChart.innerHTML = "";
    connectivityRegionNote.textContent = "No hay puntos validos para dibujar la serie regional.";
    connectivityRegionLegend.innerHTML =
      '<div class="connectivity-region-legend-empty">Sin regiones con datos.</div>';
    return;
  }

  if (
    connectivityRegionFocused &&
    !regionSeries.some((item) => item.key === connectivityRegionFocused)
  ) {
    connectivityRegionFocused = "";
  }

  const chartWidth = 280;
  const chartHeight = 176;
  const marginLeft = 40;
  const marginRight = 8;
  const marginTop = 14;
  const marginBottom = 28;
  const plotWidth = Math.max(chartWidth - marginLeft - marginRight, 1);
  const plotHeight = Math.max(chartHeight - marginTop - marginBottom, 1);
  const minTsMs = Math.min(...allTimestamps);
  const maxTsMs = Math.max(...allTimestamps);
  let minValue = Math.min(...allValues);
  let maxValue = Math.max(...allValues);
  if (minValue === maxValue) {
    minValue -= 0.5;
    maxValue += 0.5;
  }
  const valueSpan = Math.max(maxValue - minValue, 1e-9);
  const tsSpan = Math.max(maxTsMs - minTsMs, 1);

  const yTickRatios = [0, 0.33, 0.66, 1];
  const yGuides = yTickRatios
    .map((ratio) => {
      const y = ratio * plotHeight;
      return `<line class="grid-line" x1="0" y1="${y.toFixed(2)}" x2="${plotWidth.toFixed(
        2
      )}" y2="${y.toFixed(2)}"></line>`;
    })
    .join("");

  const xTicks = [
    { ts: minTsMs, label: formatConnectivityMiniUtcLabel(minTsMs), anchor: "start" },
    {
      ts: minTsMs + tsSpan / 2,
      label: formatConnectivityMiniUtcLabel(minTsMs + tsSpan / 2),
      anchor: "middle",
    },
    { ts: maxTsMs, label: formatConnectivityMiniUtcLabel(maxTsMs), anchor: "end" },
  ];

  const xGuides = xTicks
    .map((tick) => {
      const x = ((tick.ts - minTsMs) / tsSpan) * plotWidth;
      return `<line class="grid-line x-grid-line" x1="${x.toFixed(2)}" y1="0" x2="${x.toFixed(
        2
      )}" y2="${plotHeight.toFixed(2)}"></line>`;
    })
    .join("");

  const hasFocus = !!connectivityRegionFocused;
  const seriesMarkup = regionSeries
    .map((item) => {
      const isFocused = hasFocus && item.key === connectivityRegionFocused;
      const isDimmed = hasFocus && item.key !== connectivityRegionFocused;
      const stateClass = isFocused ? " is-highlight" : isDimmed ? " is-dim" : "";
      const color = getConnectivityRegionColor(item.name);
      const path = buildTimeseriesPath(
        item.series,
        minTsMs,
        maxTsMs,
        minValue,
        maxValue,
        plotWidth,
        plotHeight,
        0
      );
      if (!path) return "";
      return `<path class="region-series${stateClass}" d="${path}" style="stroke:${color};"></path>`;
    })
    .join("");

  const yLabels = yTickRatios
    .map((ratio) => {
      const y = marginTop + ratio * plotHeight;
      const value = maxValue - ratio * valueSpan;
      return `<text class="axis-label y-label" x="${marginLeft - 4}" y="${y.toFixed(
        2
      )}" text-anchor="end" dominant-baseline="middle">${escapeHtml(
        formatMetricValue(value)
      )}</text>`;
    })
    .join("");

  const xLabels = xTicks
    .map((tick) => {
      const x = marginLeft + ((tick.ts - minTsMs) / tsSpan) * plotWidth;
      return `<text class="axis-label x-label" x="${x.toFixed(2)}" y="${(
        chartHeight - 6
      ).toFixed(2)}" text-anchor="${tick.anchor}" dominant-baseline="middle">${escapeHtml(
        tick.label
      )}</text>`;
    })
    .join("");

  connectivityRegionChart.innerHTML = `
    <text class="axis-title" x="${marginLeft}" y="10" text-anchor="start">Volumen HTTP</text>
    <text class="axis-title" x="${chartWidth - 2}" y="${chartHeight - 20}" text-anchor="end">Hora UTC</text>
    <g transform="translate(${marginLeft}, ${marginTop})">
      <rect class="plot-bg" x="0" y="0" width="${plotWidth}" height="${plotHeight}" rx="4" ry="4"></rect>
      ${yGuides}
      ${xGuides}
      ${seriesMarkup}
      <line class="axis-line" x1="0" y1="0" x2="0" y2="${plotHeight}"></line>
      <line class="axis-line" x1="0" y1="${plotHeight}" x2="${plotWidth}" y2="${plotHeight}"></line>
    </g>
    ${yLabels}
    ${xLabels}
  `;

  const startLabel = formatConnectivityMiniUtcLabel(minTsMs);
  const endLabel = formatConnectivityMiniUtcLabel(maxTsMs);
  const windowHours = Number(payload?.window?.hours);
  const windowLabel = [2, 6, 24].includes(windowHours) ? `${windowHours}h` : "ventana";
  const improvingCount = regionSeries.filter(
    (item) => Number.isFinite(Number(item.change_pct)) && Number(item.change_pct) >= 5
  ).length;
  const worseningCount = regionSeries.filter(
    (item) => Number.isFinite(Number(item.change_pct)) && Number(item.change_pct) <= -5
  ).length;
  const stableCount = Math.max(regionSeries.length - improvingCount - worseningCount, 0);
  const focusedRegion = regionSeries.find((item) => item.key === connectivityRegionFocused);
  if (focusedRegion) {
    const trendMeta = getConnectivityRegionTrendMeta(focusedRegion.change_pct);
    connectivityRegionNote.textContent = `${focusedRegion.name}: ${
      trendMeta.label
    } (${formatPercentValue(focusedRegion.change_pct)}) · Ultimo volumen ${formatMetricValue(
      focusedRegion.latest_value
    )} · UTC ${startLabel} -> ${endLabel}.`;
  } else {
    connectivityRegionNote.textContent = `${regionSeries.length} regiones · Ventana ${windowLabel} · UTC ${startLabel} -> ${endLabel} · Suben ${improvingCount}, bajan ${worseningCount}, estables ${stableCount}.`;
  }

  const legendItems = [...regionSeries].sort((a, b) => {
    const aChange = Number.isFinite(Number(a.change_pct)) ? Number(a.change_pct) : 0;
    const bChange = Number.isFinite(Number(b.change_pct)) ? Number(b.change_pct) : 0;
    return aChange - bChange;
  });

  connectivityRegionLegend.innerHTML = legendItems
    .map((item) => {
      const isActive = connectivityRegionFocused === item.key;
      const color = getConnectivityRegionColor(item.name);
      const latestValueText = formatMetricValue(item.latest_value);
      const changeText = Number.isFinite(Number(item.change_pct))
        ? formatPercentValue(item.change_pct)
        : "N/D";
      const trendMeta = getConnectivityRegionTrendMeta(item.change_pct);
      return `
        <button
          type="button"
          class="connectivity-region-legend-item${isActive ? " is-active" : ""}"
          data-region-key="${escapeHtml(item.key)}"
          aria-pressed="${isActive ? "true" : "false"}"
        >
          <span class="connectivity-region-swatch" style="background:${color};"></span>
          <span class="connectivity-region-name">${escapeHtml(item.name)}</span>
          <span class="connectivity-region-value">${escapeHtml(latestValueText)}</span>
          <span class="connectivity-region-change">${escapeHtml(changeText)}</span>
          <span class="connectivity-region-trend ${trendMeta.cssClass}">${trendMeta.label}</span>
        </button>
      `;
    })
    .join("");

  const legendButtons = Array.from(
    connectivityRegionLegend.querySelectorAll(".connectivity-region-legend-item[data-region-key]")
  );
  legendButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = String(button.getAttribute("data-region-key") || "").trim();
      connectivityRegionFocused = connectivityRegionFocused === key ? "" : key;
      renderConnectivityRegionChart(connectivityLastPayload);
    });
  });
}

function getSelectedLocationFilters() {
  const province = document.getElementById("provinceFilter")?.value || "";
  const municipality = document.getElementById("municipalityFilter")?.value || "";
  return { province, municipality };
}

async function loadPosts() {
  const res = await fetch(`/api/posts`);
  return await res.json();
}

function attachMediaThumbHandlers(container) {
  if (!container) return;
  const thumbs = container.querySelectorAll(".info-media-thumb");
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const url = thumb.getAttribute("data-image");
      const caption = thumb.getAttribute("data-caption") || "";
      if (!url || !mapImageModal || !mapImageModalImg) return;
      mapImageModalImg.src = url;
      if (mapImageModalCaption) mapImageModalCaption.textContent = caption;
      mapImageModal.setAttribute("aria-hidden", "false");
      mapImageModal.classList.add("open");
    });
  });
}

function renderGeometry(post) {
  if (!post?.polygon_geojson || !map) return;
  try {
    const geo = JSON.parse(post.polygon_geojson);
    if (geo && geo.type === "Polygon" && geo.coordinates?.length) {
      const latLngs = geo.coordinates[0].map(([lng, lat]) => [lat, lng]);
      const polygon = L.polygon(latLngs, {
        color: "#6ee7b7",
        weight: 2,
        opacity: 0.7,
        fillColor: "#6ee7b7",
        fillOpacity: 0.18,
      }).addTo(map);
      shapeLayers.push(polygon);
    } else if (geo && geo.type === "Point" && geo.coordinates?.length && geo.radius_m) {
      const circle = L.circle([geo.coordinates[1], geo.coordinates[0]], {
        radius: geo.radius_m,
        color: "#6ee7b7",
        weight: 2,
        opacity: 0.7,
        fillColor: "#6ee7b7",
        fillOpacity: 0.18,
      }).addTo(map);
      shapeLayers.push(circle);
    }
  } catch (err) {
    // ignore invalid geometry
  }
}

function attachPopupActions(post, popupElement, popupRef) {
  if (!popupElement) return;

  attachMediaThumbHandlers(popupElement);

  const detailBtn = popupElement.querySelector(`#detailBtn-${post.id}`);
  if (detailBtn) {
    detailBtn.addEventListener("click", () => {
      const url = detailBtn.getAttribute("data-detail-url");
      if (!url) return;
      window.location.href = url;
    });
  }

  const copyBtn = popupElement.querySelector(`#copyLinkBtn-${post.id}`);
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const url = copyBtn.getAttribute("data-copy-url");
      if (!url) return;
      const full = `${window.location.origin}${url}`;
      try {
        await navigator.clipboard.writeText(full);
        copyBtn.textContent = "Enlace copiado";
        setTimeout(() => (copyBtn.textContent = "Copiar enlace"), 1500);
      } catch (err) {
        copyBtn.textContent = "Copia manual";
      }
    });
  }

  const reportBtn = popupElement.querySelector("#reportLocationBtn");
  if (reportBtn) {
    reportBtn.addEventListener("click", () => {
      const url = reportBtn.getAttribute("data-report-url");
      if (!url) return;
      if (window.openReportModal) {
        window.openReportModal(url);
      } else {
        window.location.href = url;
      }
    });
  }

  const historyBtn = popupElement.querySelector("#viewHistoryBtn");
  if (historyBtn) {
    historyBtn.addEventListener("click", () => {
      const url = historyBtn.getAttribute("data-history-url");
      if (!url) return;
      if (window.openReportModal) {
        window.openReportModal(url);
      } else {
        window.location.href = url;
      }
    });
  }

  const verifyBtn = popupElement.querySelector(`#verifyBtn-${post.id}`);
  if (verifyBtn) {
    verifyBtn.addEventListener("click", async () => {
      if (verifyBtn.disabled) return;
      const res = await fetch(`/api/posts/${post.id}/verify`, { method: "POST" });
      const data = await res.json();
      const countEl = popupElement.querySelector(`#verifyCount-${post.id}`);
      if (countEl && typeof data.verify_count !== "undefined") {
        countEl.textContent = data.verify_count;
      }
      if (data && data.ok) {
        verifyBtn.disabled = true;
        verifyBtn.textContent = "Verificado";
        verifyBtn.classList.add("is-verified");
        verifyBtn.setAttribute("data-verified", "1");
      }
    });
  }

  const editBtn = popupElement.querySelector(`#editBtn-${post.id}`);
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      const url = editBtn.getAttribute("data-edit-url");
      if (!url) return;
      if (window.openReportModal) {
        window.openReportModal(url);
      } else {
        window.location.href = url;
      }
    });
  }

  if (!isAdmin) return;

  const hideBtn = popupElement.querySelector(`#hideBtn-${post.id}`);
  const deleteBtn = popupElement.querySelector(`#deleteBtn-${post.id}`);

  const updateStatus = async (status) => {
    const res = await fetch(`/api/posts/${post.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    return await res.json();
  };

  if (hideBtn) {
    hideBtn.addEventListener("click", async () => {
      if (!confirm("Ocultar este reporte?")) return;
      const result = await updateStatus("hidden");
      if (result && result.ok) {
        allPosts = allPosts.filter((p) => p.id !== post.id);
        applyFilters();
        if (map && popupRef) map.closePopup(popupRef);
      }
    });
  }

  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Eliminar este reporte?")) return;
      const result = await updateStatus("deleted");
      if (result && result.ok) {
        allPosts = allPosts.filter((p) => p.id !== post.id);
        applyFilters();
        if (map && popupRef) map.closePopup(popupRef);
      }
    });
  }
}

function reportDetailHtmlForPost(post) {
  const created = post.created_at ? new Date(post.created_at) : null;
  const createdText = created ? created.toLocaleString("es-ES") : "";
  const safeTitle = escapeHtml(post.title || "Reporte");
  const safeCategory = escapeHtml(post.category?.name || "");
  const safeAnon = escapeHtml(post.anon || "Anon");
  const safeDescription = escapeHtml(post.description || "");
  const safeAddress = escapeHtml(post.address || "");
  const repressor = post && post.repressor ? post.repressor : null;
  const repressorName = repressor ? escapeHtml(repressor.full_name || "") : "";
  const repressorNick = repressor ? escapeHtml(repressor.nickname || "") : "";
  const repressorInstitution = repressor
    ? escapeHtml(repressor.institution_name || "")
    : "";
  const repressorCampus = repressor ? escapeHtml(repressor.campus_name || "") : "";
  const repressorProvince = repressor ? escapeHtml(repressor.province_name || "") : "";
  const repressorMunicipality = repressor
    ? escapeHtml(repressor.municipality_name || "")
    : "";
  const repressorImage = repressor ? safeUrl(repressor.image_url || "") : "";
  const repressorDetailUrl =
    repressor && Number.isFinite(Number(repressor.id))
      ? `/represores/${Number(repressor.id)}`
      : "";
  const repressorTypes = normalizeNameList(repressor?.types);
  const repressorCrimes = normalizeNameList(repressor?.crimes);
  const links = normalizeLinkList(post?.links);
  const repressorBlock = repressor
    ? `
      <div class="report-repressor-card">
        <div class="report-repressor-head">
          ${
            repressorImage
              ? `<img src="${repressorImage}" alt="${repressorName}" class="report-repressor-image" />`
              : ""
          }
          <div>
            <div class="report-repressor-title">${repressorName || "Represor"}</div>
            ${
              repressorNick
                ? `<div class="report-repressor-meta">Seudonimo: ${repressorNick}</div>`
                : ""
            }
            ${
              repressorTypes.length
                ? `<div class="report-repressor-meta">Tipo: ${escapeHtml(repressorTypes.join(", "))}</div>`
                : ""
            }
          </div>
        </div>
        ${
          repressorInstitution
            ? `<div class="report-repressor-meta">Institucion: ${repressorInstitution}</div>`
            : ""
        }
        ${
          repressorCampus
            ? `<div class="report-repressor-meta">Centro laboral: ${repressorCampus}</div>`
            : ""
        }
        ${
          repressorProvince || repressorMunicipality
            ? `<div class="report-repressor-meta">Provincia: ${
                repressorProvince || "N/D"
              } · Municipio: ${repressorMunicipality || "N/D"}</div>`
            : ""
        }
        ${
          repressorCrimes.length
            ? `<div class="report-repressor-meta">Delitos: ${escapeHtml(
                repressorCrimes.slice(0, 3).join(" · ")
              )}${repressorCrimes.length > 3 ? " ..." : ""}</div>`
            : ""
        }
        ${
          repressorDetailUrl
            ? `<div class="report-repressor-actions"><a class="info-btn info-btn-outline" href="${repressorDetailUrl}">Ver ficha del represor</a></div>`
            : ""
        }
      </div>
    `
    : "";
  const mediaItems = Array.isArray(post.media) ? post.media : [];
  const mediaHtml = mediaItems.length
    ? `<div class="info-media">
        ${mediaItems
          .slice(0, 4)
          .map((item) => {
            const url = typeof item === "string" ? item : item?.url;
            if (!url) return "";
            const caption = typeof item === "string" ? "" : item?.caption || "";
            const safeCaption = escapeHtml(caption);
            return `
              <button class="info-media-thumb" type="button" data-image="${url}" data-caption="${safeCaption}">
                <img src="${url}" alt="Imagen del reporte" />
              </button>
            `;
          })
          .join("")}
      </div>`
    : "";
  const editLocked = !isAdmin && (post.verify_count ?? 0) >= 10;
  const verifiedByMe = !!post.verified_by_me;
  const verifyLabel = verifiedByMe ? "Verificado" : "Verificar";
  const verifyDisabled = verifiedByMe ? "disabled data-verified=\"1\"" : "";

  return `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${safeTitle}</h3>
      <div class="report-detail-meta">${safeCategory}</div>
      <div class="report-detail-meta">${safeAnon}</div>
      ${createdText ? `<div class="report-detail-meta">${createdText}</div>` : ""}
      <p class="report-detail-description">${safeDescription || "Sin descripcion."}</p>
      ${repressorBlock}
      ${mediaHtml}
      ${
        links.length
          ? `<div class="report-detail-links">
               ${links
                 .map((link) => {
                   const href = safeUrl(link.href);
                   if (!href) return "";
                   const label = escapeHtml(link.label || link.href);
                   return `<div><a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a></div>`;
                 })
                 .join("")}
            </div>`
          : ""
      }
      <div class="info-actions">
        <button id="detailBtn-${post.id}" data-detail-url="/reporte/${post.id}" class="info-btn info-btn-outline">Ver detalle</button>
        <button id="copyLinkBtn-${post.id}" data-copy-url="/reporte/${post.id}" class="info-btn info-btn-outline">Copiar enlace</button>
        <button id="reportLocationBtn" data-report-url="/reportar-ubicacion/${post.id}" class="info-btn info-btn-outline">Reportar ubicacion</button>
        <button id="viewHistoryBtn" data-history-url="/reporte/${post.id}/historial" class="info-btn info-btn-outline info-btn-blue">Ver historial</button>
        <button id="verifyBtn-${post.id}" data-verify-id="${post.id}" class="info-btn info-btn-solid ${verifiedByMe ? "is-verified" : ""}" ${verifyDisabled}>${verifyLabel}</button>
        <span id="verifyCount-${post.id}" class="info-badge">${post.verify_count ?? 0}</span>
        ${
          editLocked
            ? `<span style="font-size:11px;color:#777;">Edicion bloqueada: 10+ verificaciones. Puedes comentar y reportar ubicacion si hay datos erroneos.</span>`
            : `<button id="editBtn-${post.id}" data-edit-url="/reporte/${post.id}/editar" class="info-btn info-btn-outline">Editar</button>`
        }
        ${
          isAdmin
            ? `
              <button id="hideBtn-${post.id}" data-status="hidden" class="info-btn info-btn-outline">Ocultar</button>
              <button id="deleteBtn-${post.id}" data-status="deleted" class="info-btn info-btn-outline">Eliminar</button>
            `
            : ""
        }
      </div>
      ${post.address ? `<div class="report-detail-address">${safeAddress}</div>` : ""}
    </div>
  `;
}

function triggerReportDetailReveal() {
  if (!reportDetailPanel) return;
  reportDetailPanel.classList.remove("is-empty");
  reportDetailPanel.classList.remove("is-revealing");
  // Force reflow to restart the animation when selecting another report.
  void reportDetailPanel.offsetWidth;
  reportDetailPanel.classList.add("is-revealing");
}

function detailEmptyLabelForMode(mode) {
  const currentMode = String(mode || "").trim().toLowerCase();
  if (currentMode === "repressors") {
    return "Haz click en un territorio para ver fichas de represores.";
  }
  if (currentMode === "prisoners") {
    return "Haz click en un territorio para ver fichas de prisioneros.";
  }
  if (currentMode === "ais") {
    return "Haz click en un buque en el mapa para ver detalles.";
  }
  if (currentMode === "flights") {
    return "Haz click en un avion en el mapa para ver detalles.";
  }
  if (currentMode === "protests") {
    return "Haz click en un evento para ver detalles.";
  }
  if (currentMode === "connectivity") {
    return "Haz click en una provincia para ver detalles de conectividad.";
  }
  return "Haz click en un simbolo en el mapa para ver detalles.";
}

function setReportDetailEmptyState(isEmpty) {
  if (!reportDetailPanel) return;
  reportDetailPanel.classList.toggle("is-empty", Boolean(isEmpty));
}

function renderReportDetail(post, options = {}) {
  if (!reportDetailPanel) return;
  reportDetailPanel.hidden = false;
  if (!post) {
    selectedReportId = null;
    setReportDetailEmptyState(true);
    reportDetailPanel.classList.remove("is-revealing");
    const emptyLabel = String(options.emptyLabel || detailEmptyLabelForMode(activeBaseMode)).trim();
    reportDetailPanel.innerHTML = `<div class="report-detail-empty">${escapeHtml(emptyLabel)}</div>`;
    return;
  }

  selectedReportId = Number(post.id) || null;
  setReportDetailEmptyState(false);
  try {
    reportDetailPanel.innerHTML = reportDetailHtmlForPost(post);
    triggerReportDetailReveal();
    attachPopupActions(post, reportDetailPanel, null);
  } catch (error) {
    console.error("No se pudo renderizar el detalle del reporte", error, post);
    const safeTitle = escapeHtml(post.title || "Reporte");
    const safeDescription = escapeHtml(post.description || "Sin descripcion.");
    setReportDetailEmptyState(false);
    reportDetailPanel.classList.remove("is-revealing");
    reportDetailPanel.innerHTML = `
      <div class="report-detail-content">
        <h3 class="report-detail-title">${safeTitle}</h3>
        <p class="report-detail-description">${safeDescription}</p>
      </div>
    `;
  }
  if (options.scrollToTop !== false && mapSideScroll) {
    mapSideScroll.scrollTop = 0;
  }
}

function renderMarkers(posts) {
  clearMarkers();

  posts.forEach((post) => {
    const lat = Number(post.latitude);
    const lng = Number(post.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

    const slug = post.category?.slug || "otros";
    const iconClass = CATEGORY_ICONS[slug] || "fa-location-dot";
    const imageUrl = CATEGORY_IMAGES[slug];

    const marker = L.marker([lat, lng], {
      title: post.title,
      icon: createMarkerIcon(iconClass, imageUrl, slug, false),
    });

    // Add marker to the category-specific cluster group
    if (markerClustersByCategory[slug]) {
      markerClustersByCategory[slug].addLayer(marker);
    } else {
      marker.addTo(map);
    }

    marker.on("click", (event) => {
      if (event?.originalEvent) {
        L.DomEvent.stopPropagation(event.originalEvent);
      }
      closeActivePopup();
      renderReportDetail(post);
      ensureContextPanelVisible({ mobileState: "full" });
    });

    markers.push(marker);
    markerIndex.set(post.id, { marker, post });
    renderGeometry(post);
  });

  if (selectedReportId) {
    const selectedEntry = markerIndex.get(selectedReportId);
    if (selectedEntry?.post) {
      renderReportDetail(selectedEntry.post, { scrollToTop: false });
    } else {
      renderReportDetail(null);
    }
  }
}

function openPostOnMap(post) {
  if (!post || !map) return;
  const lat = Number(post.latitude);
  const lng = Number(post.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

  map.setView([lat, lng], Math.max(map.getZoom(), 14));
  const entry = markerIndex.get(post.id);
  if (entry?.post) {
    renderReportDetail(entry.post);
    ensureContextPanelVisible({ mobileState: "full" });
    return;
  }
  renderReportDetail(post);
  ensureContextPanelVisible({ mobileState: "full" });
}

function updateLegendCounts(posts) {
  const total = Array.isArray(posts) ? posts.length : 0;
  const counts = {};
  (posts || []).forEach((post) => {
    const id = post.category?.id;
    if (!id) return;
    counts[id] = (counts[id] || 0) + 1;
  });

  document.querySelectorAll(".legend-count").forEach((el) => {
    const raw = String(el.id || "").replace("legend-count-", "");
    const value = raw === "all" ? total : counts[parseInt(raw, 10)] || 0;
    el.textContent = value;
  });
}

window.handleNewReport = function (payload) {
  if (!payload || !map) return;
  if (
    activeBaseMode === "connectivity" ||
    activeBaseMode === "protests" ||
    activeBaseMode === "repressors" ||
    activeBaseMode === "prisoners" ||
    activeBaseMode === "ais" ||
    activeBaseMode === "flights"
  ) {
    if (Array.isArray(allPosts) && payload.status === "approved") {
      allPosts.unshift(payload);
    }
    updateLegendCounts(allPosts);
    if (activeBaseMode === "repressors") {
      refreshRepressorLayer();
      refreshRepressorStats();
    }
    if (activeBaseMode === "prisoners") {
      refreshPrisonerLayer();
      refreshPrisonerStats();
    }
    if (activeBaseMode === "flights") {
      refreshFlightsLayer();
    }
    refreshAlerts();
    return;
  }

  const lat = Number(payload.latitude);
  const lng = Number(payload.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

  const slug = payload.category?.slug;
  const iconClass = CATEGORY_ICONS[slug] || "fa-location-dot";
  const imageUrl = CATEGORY_IMAGES[slug];

  if (payload.status !== "approved") {
    const marker = L.marker([lat, lng], {
      title: payload.title || "Reporte pendiente",
      icon: createMarkerIcon("fa-hourglass-half", imageUrl, slug, true),
    }).addTo(map);

    marker.bindPopup(
      `
      <div style="color:#111;max-width:240px;">
        <strong>Reporte enviado a moderacion.</strong>
        <div style="font-size:12px;margin-top:6px;">Se mostrara cuando sea aprobado.</div>
      </div>
      `,
      MAP_POPUP_OPTIONS
    );

    pendingMarkers.push(marker);
    map.setView([lat, lng], Math.max(map.getZoom(), 12));
    marker.openPopup();
    refreshAlerts();
    return;
  }

  if (Array.isArray(allPosts)) {
    allPosts.unshift(payload);
  }
  updateLegendCounts(allPosts);
  applyFilters();
  map.setView([lat, lng], Math.max(map.getZoom(), 12));
  refreshAlerts();
};

function clearConnectivityLayer() {
  if (connectivityGeoLayer && map) {
    map.removeLayer(connectivityGeoLayer);
  }
  connectivityGeoLayer = null;
}

function normalizeProvinceName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function getConnectivitySeries(payload) {
  if (payload?.http_requests_window) return payload.http_requests_window;
  return payload?.http_requests_24h || {};
}

function getConnectivitySeriesForProvince(payload, provinceName) {
  const byProvince = payload?.http_requests_window_by_province || {};
  const selected = normalizeProvinceName(provinceName);
  if (selected && byProvince && typeof byProvince === "object") {
    const entries = Object.entries(byProvince);
    for (let idx = 0; idx < entries.length; idx += 1) {
      const [name, summary] = entries[idx];
      if (normalizeProvinceName(name) === selected) return summary || {};
    }
  }
  return getConnectivitySeries(payload);
}

function stopConnectivityPolling() {
  if (!connectivityRefreshTimer) return;
  clearInterval(connectivityRefreshTimer);
  connectivityRefreshTimer = null;
}

function styleForConnectivityFeature(feature) {
  const status = feature?.properties?.status || "unknown";
  const color = CONNECTIVITY_STATUS_COLORS[status] || CONNECTIVITY_STATUS_COLORS.unknown;
  const province = feature?.properties?.province || "";
  const selected =
    !!selectedConnectivityProvince &&
    normalizeProvinceName(province) === normalizeProvinceName(selectedConnectivityProvince);
  return {
    color: selected ? "#f8fafc" : "#0f172a",
    weight: selected ? 2.2 : 1.2,
    opacity: 0.85,
    fillColor: color,
    fillOpacity: selected ? 0.7 : status === "unknown" ? 0.24 : 0.48,
  };
}

function onConnectivityFeature(feature, layer) {
  const province = feature?.properties?.province || "Provincia";
  const status = feature?.properties?.status || "unknown";
  const label = feature?.properties?.status_label || CONNECTIVITY_STATUS_LABELS[status] || "Sin datos";
  const score = feature?.properties?.score;
  const scoreLabel = Number.isFinite(Number(score)) ? `${Number(score).toFixed(1)}%` : "N/D";
  layer.bindTooltip(`${province}: ${label} (${scoreLabel})`, {
    sticky: true,
    direction: "top",
  });

  layer.on("click", () => {
    selectedConnectivityProvince = province;
    connectivityRegionFocused = normalizeProvinceName(province);
    if (connectivityGeoLayer?.setStyle) {
      connectivityGeoLayer.setStyle(styleForConnectivityFeature);
    }
    syncSelectedProvinceStateFromPayload(connectivityLastPayload);
    renderConnectivityRegionChart(connectivityLastPayload);
    renderConnectivityProvincePanel(connectivityLastPayload);
    ensureContextPanelVisible({ mobileState: "full" });
  });
}

function renderConnectivityData(payload) {
  if (!map || !payload) return;

  clearConnectivityLayer();

  const geojson = payload.geojson || {};
  const features = Array.isArray(geojson.features) ? geojson.features : [];
  if (!features.length) return;

  connectivityGeoLayer = L.geoJSON(geojson, {
    style: styleForConnectivityFeature,
    onEachFeature: onConnectivityFeature,
  }).addTo(map);
}

async function fetchConnectivityData() {
  const params = new URLSearchParams();
  if ([2, 6, 24].includes(Number(connectivityWindowHours))) {
    params.set("window_hours", String(connectivityWindowHours));
  }
  const url = params.toString() ? `/api/connectivity/latest?${params}` : "/api/connectivity/latest";
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("No se pudo cargar conectividad");
  return await res.json();
}

function updateConnectivityUpdatedLabel(payload) {
  if (!connectivityUpdatedLabel) return;
  const snapshot = payload?.snapshot;
  const windowInfo = payload?.window || {};
  const windowHours = Number(windowInfo.hours);
  const windowPrefix = [2, 6, 24].includes(windowHours)
    ? `Ventana: ultimas ${windowHours}h`
    : "";
  if (!snapshot?.observed_at_utc) {
    connectivityUpdatedLabel.textContent = windowPrefix
      ? `${windowPrefix} | Sin datos recientes.`
      : "Sin datos recientes.";
    return;
  }
  const observed = formatUtcAndCuba(snapshot.observed_at_utc);
  const staleText = payload?.stale ? " (dato no reciente)" : "";
  let text = observed
    ? `Ultima actualizacion (UTC): ${observed}${staleText}`
    : `Ultima actualizacion (UTC): N/D${staleText}`;
  if (windowPrefix) {
    const score = Number(windowInfo.national_score);
    const statusLabel = windowInfo.national_status_label || "Sin datos";
    const scoreText = Number.isFinite(score) ? `${score.toFixed(1)}%` : "N/D";
    text = `${windowPrefix} | Estado ventana: ${statusLabel} (${scoreText}) | ${text}`;
  }
  if (!payload?.has_geojson) {
    text += " | GeoJSON provincial no configurado.";
  }
  connectivityUpdatedLabel.textContent = text;
}

function updateConnectivityTrafficPanel(payload) {
  if (
    !connectivityTrafficPanel ||
    !connectivityTrafficValue ||
    !connectivityTrafficDelta ||
    !connectivityTrafficDrop ||
    !connectivityTrafficNote
  ) {
    return;
  }
  const traffic = getConnectivitySeries(payload);
  const available = !!traffic.available;
  const seriesMain = Array.isArray(traffic.series_main) ? traffic.series_main : [];
  const seriesPrev = Array.isArray(traffic.series_previous_aligned)
    ? traffic.series_previous_aligned
    : [];

  if (!available || !seriesMain.length) {
    connectivityTrafficValue.textContent = "N/D";
    connectivityTrafficDelta.textContent = "Variacion vs control: N/D";
    connectivityTrafficDrop.textContent = "Caida maxima: N/D";
    connectivityTrafficNote.textContent = traffic.reason || "Sin serie disponible para la ventana activa.";
    if (connectivitySparkMain) connectivitySparkMain.setAttribute("d", "");
    if (connectivitySparkPrev) connectivitySparkPrev.setAttribute("d", "");
    return;
  }

  const latestMain = Number(traffic.latest_main_value);
  const latestPrev = Number(traffic.latest_previous_value);
  const deltaPct = Number(traffic.delta_pct);
  const maxDrop = Number(traffic.max_drop_from_peak_pct);
  const hours = Number(traffic.window_hours || payload?.window?.hours);
  const hoursLabel = [2, 6, 24].includes(hours) ? `${hours}h` : "ventana";

  connectivityTrafficValue.textContent = `Ultimo valor: ${formatMetricValue(latestMain)}`;
  connectivityTrafficDelta.textContent = `Variacion vs control: ${formatPercentValue(deltaPct)} (${formatMetricValue(
    latestPrev
  )})`;
  connectivityTrafficDrop.textContent = `Caida maxima ${hoursLabel}: ${formatPercentValue(maxDrop)}`;

  const latestTs = traffic.latest_timestamp_utc
    ? formatUtcAndCuba(traffic.latest_timestamp_utc)
    : "";
  const pointCount = seriesMain.length;
  connectivityTrafficNote.textContent = latestTs
    ? `Puntos: ${pointCount} · Ultimo punto (UTC): ${latestTs}`
    : `Puntos: ${pointCount}`;

  const prevMap = new Map(
    seriesPrev.map((item) => {
      const value = Number(item?.value);
      return [item?.timestamp_utc || "", Number.isFinite(value) ? value : NaN];
    })
  );
  const mainValues = seriesMain.map((item) => Number(item?.value));
  const prevValues = seriesMain.map((item) => {
    const key = item?.timestamp_utc || "";
    return prevMap.has(key) ? prevMap.get(key) : NaN;
  });

  const allValues = mainValues
    .concat(prevValues)
    .filter((value) => Number.isFinite(Number(value)))
    .map((value) => Number(value));
  const minValue = allValues.length ? Math.min(...allValues) : 0;
  const maxValue = allValues.length ? Math.max(...allValues) : 1;

  if (connectivitySparkMain) {
    connectivitySparkMain.setAttribute(
      "d",
      buildSparklinePath(mainValues, minValue, maxValue)
    );
  }
  if (connectivitySparkPrev) {
    connectivitySparkPrev.setAttribute(
      "d",
      buildSparklinePath(prevValues, minValue, maxValue)
    );
  }
}

function renderConnectivityAlertPanel(payload) {
  if (!connectivityAlertPanel || !connectivityAlertBadge || !connectivityAlertCopy || !connectivityAlertList) {
    return;
  }

  const radar = payload?.cloudflare_radar || {};
  const alerts = radar?.alerts || {};
  const active = Array.isArray(alerts?.active) ? alerts.active : [];
  const latest = alerts?.latest || null;
  const activeCount = Math.max(0, Number(alerts?.active_count) || active.length);
  const activeOutages = Math.max(0, Number(alerts?.active_outages) || 0);
  const activeAnomalies = Math.max(0, Number(alerts?.active_anomalies) || 0);

  connectivityAlertBadge.classList.remove("is-alert", "is-outage");
  if (!payload) {
    connectivityAlertBadge.textContent = "Sin datos";
    connectivityAlertCopy.textContent = "No fue posible cargar alertas de Cloudflare Radar.";
    connectivityAlertList.innerHTML = '<div class="connectivity-alert-empty">Sin eventos activos.</div>';
    return;
  }

  if (!activeCount) {
    connectivityAlertBadge.textContent = "Sin alertas activas";
    connectivityAlertCopy.textContent = "Sin alertas activas recientes detectadas por Cloudflare Radar.";
    connectivityAlertList.innerHTML = '<div class="connectivity-alert-empty">Sin eventos activos.</div>';
    return;
  }

  connectivityAlertBadge.classList.add("is-alert");
  if (activeOutages > 0) {
    connectivityAlertBadge.classList.add("is-outage");
  }
  connectivityAlertBadge.textContent = `${activeCount} activa${activeCount === 1 ? "" : "s"}`;

  if (latest) {
    const latestType = String(latest.alert_type || "").trim().toLowerCase() === "outage"
      ? "Interrupción"
      : "Anomalía";
    const latestWhen = formatUtcAndCuba(latest.start_date);
    const cause = latest.outage_cause ? ` · Causa: ${latest.outage_cause}` : "";
    connectivityAlertCopy.textContent = `${latestType} más reciente: ${latestWhen}${cause}`;
  } else {
    connectivityAlertCopy.textContent = `${activeOutages} interrupciones y ${activeAnomalies} anomalías activas.`;
  }

  const alertRows = active
    .slice(0, 4)
    .map((item, idx) => {
      const type = String(item?.alert_type || "").trim().toLowerCase() === "outage"
        ? "Interrupción"
        : "Anomalía";
      const when = formatUtcAndCuba(item?.start_date);
      const headline = String(item?.description || item?.event_type || "").trim();
      const subline = [];
      if (item?.outage_cause) subline.push(`Causa: ${item.outage_cause}`);
      if (item?.status) subline.push(`Estado: ${item.status}`);
      if (Number.isFinite(Number(item?.magnitude))) {
        subline.push(`Magnitud: ${Number(item.magnitude).toFixed(2)}`);
      }
      return `
        <div class="connectivity-alert-item">
          <div class="connectivity-alert-item-head">
            <strong>${escapeHtml(type)} #${idx + 1}</strong>
            <span>${escapeHtml(when)}</span>
          </div>
          ${
            headline
              ? `<div class="connectivity-alert-item-copy">${escapeHtml(headline)}</div>`
              : ""
          }
          ${
            subline.length
              ? `<div class="connectivity-alert-item-meta">${escapeHtml(subline.join(" · "))}</div>`
              : ""
          }
        </div>
      `;
    })
    .join("");
  connectivityAlertList.innerHTML =
    alertRows || '<div class="connectivity-alert-empty">Sin eventos activos.</div>';
}

function renderConnectivityQualityPanel(payload) {
  if (
    !connectivityQualityPanel ||
    !connectivityQualityDownloadValue ||
    !connectivityQualityDownloadMeta ||
    !connectivityQualityLatencyValue ||
    !connectivityQualityLatencyMeta ||
    !connectivityQualityNote
  ) {
    return;
  }

  const radar = payload?.cloudflare_radar || {};
  const speed = radar?.speed || {};
  const latest = speed?.latest || {};
  const averages = speed?.averages_7d || {};
  if (!payload || !speed?.available) {
    connectivityQualityDownloadValue.textContent = "N/D";
    connectivityQualityDownloadMeta.textContent = "Global: N/D";
    connectivityQualityLatencyValue.textContent = "N/D";
    connectivityQualityLatencyMeta.textContent = "Global: N/D";
    connectivityQualityNote.textContent = "Sin datos recientes de velocidad/latencia.";
    return;
  }

  connectivityQualityDownloadValue.textContent = formatMbps(latest?.download_mbps);
  connectivityQualityDownloadMeta.textContent = `Global: ${formatMbps(
    latest?.global_download_mbps
  )} (${formatSignedPercentDelta(latest?.download_delta_pct)})`;
  connectivityQualityLatencyValue.textContent = formatMilliseconds(latest?.latency_ms);
  connectivityQualityLatencyMeta.textContent = `Global: ${formatMilliseconds(
    latest?.global_latency_ms
  )} (${formatSignedPercentDelta(latest?.latency_delta_pct)})`;

  const avgDownload = formatMbps(averages?.download_mbps);
  const avgLatency = formatMilliseconds(averages?.latency_ms);
  const updatedAt = radar?.updated_at_utc ? formatUtcAndCuba(radar.updated_at_utc) : "N/D";
  connectivityQualityNote.textContent = `Promedio 7d Cuba: descarga ${avgDownload}, latencia ${avgLatency}. Actualizado: ${updatedAt}.`;
}

function renderConnectivityAudiencePanel(payload) {
  if (
    !connectivityAudiencePanel ||
    !connectivityAudienceMobileBar ||
    !connectivityAudienceDesktopBar ||
    !connectivityAudienceHumanBar ||
    !connectivityAudienceBotBar ||
    !connectivityAudienceMobileValue ||
    !connectivityAudienceDesktopValue ||
    !connectivityAudienceHumanValue ||
    !connectivityAudienceBotValue
  ) {
    return;
  }

  const radar = payload?.cloudflare_radar || {};
  const audience = radar?.audience || {};
  const mobilePct = Number(audience?.device_mobile_pct);
  const desktopPct = Number(audience?.device_desktop_pct);
  const humanPct = Number(audience?.human_pct);
  const botPct = Number(audience?.bot_pct);
  const windowHours = Number(audience?.window_hours || payload?.window?.hours);
  const sampleCount = Number(audience?.sample_count);
  const hoursLabel = [2, 6, 24].includes(windowHours) ? `${windowHours}h` : "24h";

  const applyAudienceValue = (valueEl, barEl, value) => {
    valueEl.textContent = formatPercentCompact(value);
    barEl.style.width = `${clampPercentWidth(value)}%`;
  };

  const updateAudienceNote = (noteText) => {
    if (!connectivityAudienceNote) return;
    connectivityAudienceNote.textContent = noteText;
  };

  if (!payload || !audience?.available) {
    [
      [connectivityAudienceMobileValue, connectivityAudienceMobileBar],
      [connectivityAudienceDesktopValue, connectivityAudienceDesktopBar],
      [connectivityAudienceHumanValue, connectivityAudienceHumanBar],
      [connectivityAudienceBotValue, connectivityAudienceBotBar],
    ].forEach(([valueEl, barEl]) => {
      valueEl.textContent = "N/D";
      barEl.style.width = "0%";
    });
    const sampleText = Number.isFinite(sampleCount) ? sampleCount : 0;
    updateAudienceNote(`Ventana ${hoursLabel} · muestras: ${sampleText}.`);
    return;
  }

  applyAudienceValue(connectivityAudienceMobileValue, connectivityAudienceMobileBar, mobilePct);
  applyAudienceValue(connectivityAudienceDesktopValue, connectivityAudienceDesktopBar, desktopPct);
  applyAudienceValue(connectivityAudienceHumanValue, connectivityAudienceHumanBar, humanPct);
  applyAudienceValue(connectivityAudienceBotValue, connectivityAudienceBotBar, botPct);
  const sampleText = Number.isFinite(sampleCount) ? sampleCount : 1;
  const fallbackText = audience?.is_window_fallback ? " · fallback al último dato válido." : "";
  updateAudienceNote(`Ventana ${hoursLabel} · muestras: ${sampleText}${fallbackText}`);
}

function renderConnectivityRadarPanels(payload) {
  renderConnectivityAlertPanel(payload);
  renderConnectivityQualityPanel(payload);
  renderConnectivityAudiencePanel(payload);
}

function computeNotableDrops(seriesMain, seriesPrev, topN = 8) {
  const prevMap = new Map(
    (seriesPrev || []).map((item) => {
      const value = Number(item?.value);
      return [item?.timestamp_utc || "", Number.isFinite(value) ? value : NaN];
    })
  );
  const events = [];
  for (let idx = 1; idx < (seriesMain || []).length; idx += 1) {
    const current = seriesMain[idx] || {};
    const previous = seriesMain[idx - 1] || {};
    const currValue = Number(current.value);
    const prevValue = Number(previous.value);
    if (!Number.isFinite(currValue) || !Number.isFinite(prevValue) || currValue >= prevValue) continue;
    const dropAbs = prevValue - currValue;
    const dropPct = prevValue > 0 ? (dropAbs / prevValue) * 100 : null;
    const controlValue = prevMap.get(current.timestamp_utc || "");
    events.push({
      timestamp_utc: current.timestamp_utc,
      prev_value: prevValue,
      curr_value: currValue,
      drop_abs: dropAbs,
      drop_pct: Number.isFinite(dropPct) ? dropPct : null,
      control_value: Number.isFinite(controlValue) ? controlValue : null,
    });
  }
  events.sort((a, b) => {
    const aScore = Number.isFinite(a.drop_pct) ? a.drop_pct : a.drop_abs;
    const bScore = Number.isFinite(b.drop_pct) ? b.drop_pct : b.drop_abs;
    return bScore - aScore;
  });
  return events.slice(0, Math.max(1, topN));
}

function syncSelectedProvinceStateFromPayload(payload) {
  if (!selectedConnectivityProvince || !payload) return;
  const provinceList = Array.isArray(payload.provinces) ? payload.provinces : [];
  const selectedKey = normalizeProvinceName(selectedConnectivityProvince);
  const row = provinceList.find((item) => {
    const rowName = item?.province || "";
    return normalizeProvinceName(rowName) === selectedKey;
  });
  if (!row) return;
  selectedConnectivityProvinceState = {
    province: row.province,
    status: row.status || "unknown",
    status_label: row.status_label || CONNECTIVITY_STATUS_LABELS[row.status] || "Sin datos",
    score: Number.isFinite(Number(row.score)) ? Number(row.score) : null,
  };
}

function renderConnectivityProvincePanel(payload) {
  if (
    !connectivityProvincePanel ||
    !connectivityProvinceTitle ||
    !connectivityProvinceStatus ||
    !connectivityProvinceRange ||
    !connectivityProvinceChartMain ||
    !connectivityProvinceChartPrev ||
    !connectivityProvinceLog
  ) {
    return;
  }

  const hasSelection = !!selectedConnectivityProvince;
  if (!hasSelection || !payload) {
    connectivityProvinceTitle.textContent = "Selecciona una provincia";
    connectivityProvinceStatus.textContent = "Haz clic en una provincia para ver detalle horario.";
    connectivityProvinceRange.textContent = "";
    connectivityProvinceChartMain.setAttribute("d", "");
    connectivityProvinceChartPrev.setAttribute("d", "");
    connectivityProvinceLog.innerHTML =
      '<div class="connectivity-province-log-empty">Sin provincia seleccionada.</div>';
    return;
  }

  const traffic = getConnectivitySeriesForProvince(payload, selectedConnectivityProvince);
  const baseSeriesMain = Array.isArray(traffic.series_main) ? traffic.series_main : [];
  const baseSeriesPrev = Array.isArray(traffic.series_previous_aligned)
    ? traffic.series_previous_aligned
    : [];
  const provinceState = selectedConnectivityProvinceState || {};
  const seriesMain = baseSeriesMain;
  const seriesPrev = baseSeriesPrev;
  const score = Number(provinceState.score);
  const scoreText = Number.isFinite(score) ? `${score.toFixed(1)}%` : "N/D";
  const statusLabel = provinceState.status_label || "Sin datos";
  connectivityProvinceTitle.textContent = `Provincia: ${selectedConnectivityProvince}`;
  connectivityProvinceStatus.textContent = `Estado: ${statusLabel} (${scoreText}) · Datos Radar por geoId provincial (estimados).`;

  const windowInfo = payload?.window || {};
  const rangeStart = windowInfo.start_utc ? formatUtcAndCuba(windowInfo.start_utc) : "N/D";
  const rangeEnd = windowInfo.end_utc ? formatUtcAndCuba(windowInfo.end_utc) : "N/D";
  const hours = Number(windowInfo.hours);
  const hoursText = [2, 6, 24].includes(hours) ? `${hours}h` : "N/D";
  connectivityProvinceRange.textContent = `Ventana ${hoursText}: ${rangeStart} -> ${rangeEnd}`;

  if (!traffic.available || !seriesMain.length) {
    connectivityProvinceChartMain.setAttribute("d", "");
    connectivityProvinceChartPrev.setAttribute("d", "");
    connectivityProvinceLog.innerHTML =
      '<div class="connectivity-province-log-empty">Sin serie disponible para esta ventana.</div>';
    return;
  }

  const prevMap = new Map(
    seriesPrev.map((item) => {
      const value = Number(item?.value);
      return [item?.timestamp_utc || "", Number.isFinite(value) ? value : NaN];
    })
  );
  const mainValues = seriesMain.map((item) => Number(item?.value));
  const prevValues = seriesMain.map((item) => {
    const key = item?.timestamp_utc || "";
    return prevMap.has(key) ? prevMap.get(key) : NaN;
  });
  const allValues = mainValues
    .concat(prevValues)
    .filter((value) => Number.isFinite(Number(value)))
    .map((value) => Number(value));
  const minValue = allValues.length ? Math.min(...allValues) : 0;
  const maxValue = allValues.length ? Math.max(...allValues) : 1;
  connectivityProvinceChartMain.setAttribute(
    "d",
    buildSparklinePath(mainValues, minValue, maxValue, 280, 86)
  );
  connectivityProvinceChartPrev.setAttribute(
    "d",
    buildSparklinePath(prevValues, minValue, maxValue, 280, 86)
  );

  const drops = computeNotableDrops(seriesMain, seriesPrev, 10);
  if (!drops.length) {
    connectivityProvinceLog.innerHTML =
      '<div class="connectivity-province-log-empty">No se detectaron caídas notorias por hora.</div>';
    return;
  }

  connectivityProvinceLog.innerHTML = drops
    .map((drop, idx) => {
      const when = formatUtcAndCuba(drop.timestamp_utc);
      const dropPct = Number.isFinite(drop.drop_pct) ? `-${drop.drop_pct.toFixed(1)}%` : "N/D";
      const prevText = formatMetricValue(drop.prev_value);
      const currText = formatMetricValue(drop.curr_value);
      const controlText = Number.isFinite(drop.control_value)
        ? formatMetricValue(drop.control_value)
        : "N/D";
      return `
        <div class="connectivity-province-log-item">
          <div><strong>#${idx + 1}</strong> Hora: ${escapeHtml(when)}</div>
          <div>Caída: ${escapeHtml(dropPct)} (${escapeHtml(prevText)} -> ${escapeHtml(currText)})</div>
          <div>Control en esa hora: ${escapeHtml(controlText)}</div>
        </div>
      `;
    })
    .join("");
}

async function refreshConnectivityLayer() {
  if (activeBaseMode !== "connectivity") return;
  try {
    const payload = await fetchConnectivityData();
    connectivityLastPayload = payload;
    const snapshotId = payload?.snapshot?.id || null;
    const renderKey = [
      snapshotId,
      payload?.window?.hours || "",
      payload?.window?.snapshot_count || "",
      payload?.window?.national_score ?? "",
      payload?.window?.latest_observed_at_utc || "",
      payload?.window?.max_drop_from_peak_pct ?? "",
      payload?.has_geojson ? "1" : "0",
    ].join("|");
    if (renderKey !== connectivityLastRenderKey || !connectivityGeoLayer) {
      renderConnectivityData(payload);
      connectivityLastSnapshotId = snapshotId;
      connectivityLastRenderKey = renderKey;
    }
    if (selectedConnectivityProvince && connectivityGeoLayer?.setStyle) {
      connectivityGeoLayer.setStyle(styleForConnectivityFeature);
    }
    updateConnectivityUpdatedLabel(payload);
    updateConnectivityTrafficPanel(payload);
    renderConnectivityRadarPanels(payload);
    syncSelectedProvinceStateFromPayload(payload);
    renderConnectivityRegionChart(payload);
    renderConnectivityProvincePanel(payload);
  } catch (err) {
    if (connectivityUpdatedLabel) {
      connectivityUpdatedLabel.textContent = "No fue posible actualizar conectividad.";
    }
    if (connectivityRegionNote) {
      connectivityRegionNote.textContent = "No fue posible cargar la serie regional de la ventana.";
    }
    updateConnectivityTrafficPanel(null);
    renderConnectivityRadarPanels(null);
    renderConnectivityProvincePanel(null);
    renderConnectivityRegionChart(null);
  }
}

function startConnectivityPolling() {
  stopConnectivityPolling();
  const intervalMs = Math.max(30, Number(connectivityRefreshSeconds) || 300) * 1000;
  connectivityRefreshTimer = setInterval(() => {
    refreshConnectivityLayer();
  }, intervalMs);
}

async function enableConnectivityMode() {
  activeBaseMode = "connectivity";
  clearMarkers();
  closeActivePopup();
  renderReportDetail(null);
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(false);
  setConnectivityLegendVisible(true);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  ensureContextPanelVisible({ mobileState: "mid" });
  await refreshConnectivityLayer();
  startConnectivityPolling();
}

function disableConnectivityMode() {
  if (activeBaseMode !== "connectivity") return;
  activeBaseMode = "map";
  stopConnectivityPolling();
  clearConnectivityLayer();
  connectivityLastSnapshotId = null;
  connectivityLastRenderKey = null;
  connectivityLastPayload = null;
  selectedConnectivityProvince = "";
  selectedConnectivityProvinceState = null;
  connectivityRegionFocused = "";
  setConnectivityLegendVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
  updateConnectivityTrafficPanel(null);
  renderConnectivityRadarPanels(null);
  renderConnectivityProvincePanel(null);
  renderConnectivityRegionChart(null);
}

function clearRepressorLayer() {
  if (repressorLayerGroup && map) {
    map.removeLayer(repressorLayerGroup);
  }
  repressorLayerGroup = null;
}

function buildRepressorUnresolvedIcon(count) {
  const numeric = Math.max(1, Number(count) || 0);
  const label = numeric > 999 ? "999+" : String(numeric);
  return L.divIcon({
    className: "repressor-unresolved-marker-wrap",
    html: `<span class="repressor-unresolved-marker" style="background:${REPRESSOR_UNRESOLVED_COLOR};">${escapeHtml(
      label
    )}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -18],
  });
}

function confirmedResidencePopupHtml(item) {
  const repressorName = escapeHtml(item?.repressor_name || "Represor");
  const province = escapeHtml(item?.province || "N/D");
  const municipality = escapeHtml(item?.municipality || "N/D");
  const address = escapeHtml(item?.address || "");
  const imageUrl = safeUrl(item?.repressor_image_url || "");
  const typeNames = Array.isArray(item?.repressor_type_names)
    ? item.repressor_type_names.filter(Boolean).map((name) => escapeHtml(name))
    : [];
  const repressorId = Number(item?.repressor_id);
  const detailUrl = Number.isFinite(repressorId) && repressorId > 0 ? `/represores/${repressorId}` : "";
  const rawMessage = String(item?.message || "").trim();
  const shortMessage =
    rawMessage.length > 220 ? `${rawMessage.slice(0, 217).trimEnd()}...` : rawMessage;

  return `
    <div class="repressor-popup">
      ${
        imageUrl
          ? `<img src="${imageUrl}" alt="${repressorName}" class="repressor-popup-image" />`
          : ""
      }
      <div class="repressor-popup-title">${repressorName}</div>
      ${
        typeNames.length
          ? `<div class="repressor-popup-meta">Tipo: ${typeNames.join(", ")}</div>`
          : ""
      }
      <div class="repressor-popup-meta">Vivienda confirmada: ${province} · ${municipality}</div>
      ${address ? `<div class="repressor-popup-meta">Dirección: ${address}</div>` : ""}
      ${
        shortMessage
          ? `<div class="repressor-popup-meta">Nota: ${escapeHtml(shortMessage)}</div>`
          : ""
      }
      ${
        detailUrl
          ? `<a class="repressor-popup-link" href="${detailUrl}">Ver ficha del represor</a>`
          : ""
      }
    </div>
  `;
}

function unresolvedTerritoryPopupHtml(item) {
  const count = Math.max(0, Number(item?.count) || 0);
  const territory = escapeHtml(repressorTerritoryLabel(item));
  const label =
    count === 1
      ? "1 represor sin localizar en este territorio."
      : `${count.toLocaleString("es-ES")} represores sin localizar en este territorio.`;

  return `
    <div class="repressor-popup">
      <div class="repressor-popup-title">${territory}</div>
      <div class="repressor-popup-meta">${label}</div>
    </div>
  `;
}

function repressorTerritoryLabel(item) {
  const province = String(item?.province || "").trim();
  const municipality = String(item?.municipality || "").trim();
  const scope = String(item?.scope || "").trim().toLowerCase();
  if (scope === "municipality" && province && municipality) {
    return `${province} · ${municipality}`;
  }
  return province || "Territorio sin nombre";
}

function normalizeRepressorTerritoryRequest(item) {
  const scope = String(item?.scope || "").trim().toLowerCase();
  const province = String(item?.province || "").trim();
  const municipality = String(item?.municipality || "").trim();
  if (!["province", "municipality"].includes(scope)) return null;
  if (!province) return null;
  if (scope === "municipality" && !municipality) return null;
  const key = `${scope}|${province.toLowerCase()}|${municipality.toLowerCase()}`;
  return { scope, province, municipality, key };
}

function renderRepressorTerritoryDetailEmpty(message = "") {
  if (!reportDetailPanel) return;
  const text = message || "Haz click en un territorio para ver fichas de represores.";
  setReportDetailEmptyState(true);
  reportDetailPanel.classList.remove("is-revealing");
  reportDetailPanel.innerHTML = `<div class="report-detail-empty">${escapeHtml(text)}</div>`;
}

function renderRepressorTerritoryDetailLoading(territoryLabel) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${escapeHtml(territoryLabel)}</h3>
      <div class="report-detail-meta">Cargando represores sin localizar...</div>
    </div>
  `;
  triggerReportDetailReveal();
}

function renderRepressorTerritoryDetail(item, payload) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  const territoryLabel = String(payload?.territory_label || repressorTerritoryLabel(item) || "").trim();
  const entries = Array.isArray(payload?.items) ? payload.items : [];
  const count = Math.max(0, Number(payload?.count) || entries.length);
  const countLabel =
    count === 1
      ? "1 represor sin localizar"
      : `${count.toLocaleString("es-ES")} represores sin localizar`;

  if (!entries.length) {
    reportDetailPanel.innerHTML = `
      <div class="report-detail-content">
        <h3 class="report-detail-title">${escapeHtml(territoryLabel || "Territorio")}</h3>
        <div class="report-detail-meta">${countLabel}</div>
        <div class="repressor-detail-empty">No hay represores pendientes de localizar para este territorio.</div>
      </div>
    `;
    triggerReportDetailReveal();
    return;
  }

  const cardsHtml = entries
    .map((entry) => {
      const repressorId = Number(entry?.id);
      if (!Number.isFinite(repressorId) || repressorId <= 0) return "";
      const fullName = escapeHtml(entry?.full_name || "Represor");
      const nickname = String(entry?.nickname || "").trim();
      const externalId = Number(entry?.external_id);
      const imageUrl = safeUrl(entry?.image_url || "");
      const typeNames = Array.isArray(entry?.type_names)
        ? entry.type_names
            .filter((name) => String(name || "").trim())
            .map((name) => escapeHtml(name))
        : [];
      const metadata = [];
      if (Number.isFinite(externalId) && externalId > 0) {
        metadata.push(`Ficha #${externalId}`);
      }
      if (nickname) {
        metadata.push(`Seudonimo: ${escapeHtml(nickname)}`);
      }
      if (typeNames.length) {
        metadata.push(`Tipo: ${typeNames.slice(0, 2).join(", ")}${typeNames.length > 2 ? "..." : ""}`);
      }
      const detailUrl = `/represores/${repressorId}`;
      const editUrl = `/represores/${repressorId}/editar`;
      const residenceUrl = `/represores/${repressorId}/reportar-residencia`;
      const imageThumbHtml = imageUrl
        ? `
            <button
              class="info-media-thumb repressor-detail-thumb"
              type="button"
              data-image="${imageUrl}"
              data-caption="${fullName}"
            >
              <img src="${imageUrl}" alt="${fullName}" class="repressor-detail-avatar" />
            </button>
          `
        : '<div class="repressor-detail-avatar repressor-detail-avatar-empty" aria-hidden="true">?</div>';
      return `
        <article class="repressor-detail-card">
          <div class="repressor-detail-head">
            ${imageThumbHtml}
            <div class="repressor-detail-identity">
              <div class="repressor-detail-name">${fullName}</div>
              <div class="repressor-detail-meta">${metadata.join(" · ") || "Sin metadatos adicionales"}</div>
            </div>
          </div>
          <div class="repressor-detail-actions">
            <a class="info-btn info-btn-outline" href="${detailUrl}">Ver ficha</a>
            <a class="info-btn info-btn-outline" href="${editUrl}">Editar ficha</a>
            <a class="info-btn" href="${residenceUrl}">Identificar vivienda</a>
          </div>
        </article>
      `;
    })
    .filter(Boolean)
    .join("");

  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${escapeHtml(territoryLabel || "Territorio")}</h3>
      <div class="report-detail-meta">${countLabel}</div>
      <div class="repressor-detail-list">${cardsHtml}</div>
    </div>
  `;
  triggerReportDetailReveal();
  attachMediaThumbHandlers(reportDetailPanel);
  if (mapSideScroll) {
    mapSideScroll.scrollTop = 0;
  }
}

async function fetchRepressorTerritoryDetail(item) {
  const requestData = normalizeRepressorTerritoryRequest(item);
  if (!requestData) {
    renderRepressorTerritoryDetailEmpty("No se pudo determinar el territorio seleccionado.");
    return;
  }
  const territoryLabel = repressorTerritoryLabel(requestData);
  const cached = repressorUnresolvedDetailCache.get(requestData.key);
  if (cached) {
    renderRepressorTerritoryDetail(requestData, cached);
    return;
  }

  const requestSeq = ++repressorDetailRequestSeq;
  renderRepressorTerritoryDetailLoading(territoryLabel);
  const params = new URLSearchParams({
    scope: requestData.scope,
    province: requestData.province,
  });
  if (requestData.scope === "municipality") {
    params.set("municipality", requestData.municipality);
  }

  try {
    const response = await fetch(`/api/v1/repressors/unresolved-territory?${params.toString()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("No se pudo cargar el detalle del territorio.");
    }
    const payload = await response.json();
    if (requestSeq !== repressorDetailRequestSeq) return;
    repressorUnresolvedDetailCache.set(requestData.key, payload);
    renderRepressorTerritoryDetail(requestData, payload);
  } catch (_error) {
    if (requestSeq !== repressorDetailRequestSeq) return;
    renderRepressorTerritoryDetailEmpty(
      `No fue posible cargar la lista para ${territoryLabel}. Intenta nuevamente.`
    );
  }
}

function renderRepressorConfirmedDetail(item) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  const repressorId = Number(item?.repressor_id);
  const repressorName = escapeHtml(item?.repressor_name || "Represor");
  const province = escapeHtml(item?.province || "N/D");
  const municipality = escapeHtml(item?.municipality || "N/D");
  const address = escapeHtml(item?.address || "");
  const message = String(item?.message || "").trim();
  const shortMessage = message.length > 280 ? `${message.slice(0, 277).trimEnd()}...` : message;
  const imageUrl = safeUrl(item?.repressor_image_url || "");
  const typeNames = Array.isArray(item?.repressor_type_names)
    ? item.repressor_type_names
        .filter((name) => String(name || "").trim())
        .map((name) => escapeHtml(name))
    : [];
  const detailUrl = Number.isFinite(repressorId) && repressorId > 0 ? `/represores/${repressorId}` : "";
  const editUrl = Number.isFinite(repressorId) && repressorId > 0 ? `/represores/${repressorId}/editar` : "";
  const residenceUrl =
    Number.isFinite(repressorId) && repressorId > 0
      ? `/represores/${repressorId}/reportar-residencia`
      : "";

  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${repressorName}</h3>
      <div class="report-detail-meta">Vivienda confirmada: ${province} · ${municipality}</div>
      ${
        typeNames.length
          ? `<div class="repressor-detail-meta">Tipo: ${typeNames.join(", ")}</div>`
          : ""
      }
      ${
        imageUrl
          ? `
            <div class="info-media">
              <button class="info-media-thumb repressor-detail-thumb" type="button" data-image="${imageUrl}" data-caption="${repressorName}">
                <img src="${imageUrl}" alt="${repressorName}" />
              </button>
            </div>
          `
          : ""
      }
      ${address ? `<div class="repressor-detail-meta">Direccion: ${address}</div>` : ""}
      ${
        shortMessage
          ? `<p class="report-detail-description">${escapeHtml(shortMessage)}</p>`
          : ""
      }
      <div class="repressor-detail-actions">
        ${detailUrl ? `<a class="info-btn info-btn-outline" href="${detailUrl}">Ver ficha</a>` : ""}
        ${editUrl ? `<a class="info-btn info-btn-outline" href="${editUrl}">Editar ficha</a>` : ""}
        ${
          residenceUrl
            ? `<a class="info-btn" href="${residenceUrl}">Actualizar localizacion</a>`
            : ""
        }
      </div>
    </div>
  `;
  triggerReportDetailReveal();
  attachMediaThumbHandlers(reportDetailPanel);
  if (mapSideScroll) {
    mapSideScroll.scrollTop = 0;
  }
}

function renderRepressorSummary(payload, errorText = "") {
  if (!repressorSummary) return;
  if (errorText) {
    repressorSummary.textContent = errorText;
    return;
  }
  const summary = payload?.summary || {};
  const confirmed = Number(summary.confirmed_residences_points) || 0;
  const unresolved = Number(summary.unresolved_territories_points) || 0;
  const unresolvedPeople = Number(summary.without_confirmed_residence) || 0;
  const withoutTerritory = Number(summary.without_territory_reference) || 0;
  repressorSummary.textContent = `Viviendas confirmadas: ${confirmed.toLocaleString(
    "es-ES"
  )} · Territorios sin localizar: ${unresolved.toLocaleString(
    "es-ES"
  )} · Represores sin localizar: ${unresolvedPeople.toLocaleString("es-ES")} · Sin territorio: ${withoutTerritory.toLocaleString(
    "es-ES"
  )}.`;
}

function renderRepressorStats(payload, errorText = "") {
  if (!repressorStatsPanel) return;
  if (errorText) {
    repressorStatsPanel.innerHTML = `<div class="repressor-stats-empty">${escapeHtml(errorText)}</div>`;
    return;
  }

  const total = Math.max(0, Number(payload?.total_repressors) || 0);
  const byProvince = Array.isArray(payload?.by_province) ? payload.by_province : [];
  if (!byProvince.length) {
    repressorStatsPanel.innerHTML = `
      <div class="repressor-stats-total">Total país: ${total.toLocaleString("es-ES")}</div>
      <div class="repressor-stats-empty">Sin datos provinciales disponibles.</div>
    `;
    return;
  }

  const topRows = byProvince.slice(0, 16);
  const maxCount = Math.max(...topRows.map((item) => Number(item?.count) || 0), 1);
  const rowsHtml = topRows
    .map((item) => {
      const province = escapeHtml(item?.province || "N/D");
      const count = Math.max(0, Number(item?.count) || 0);
      const width = Math.max(4, Math.round((count / maxCount) * 100));
      return `
        <div class="repressor-stats-row">
          <div class="repressor-stats-label">${province}</div>
          <div class="repressor-stats-bar">
            <span style="width:${width}%"></span>
          </div>
          <div class="repressor-stats-value">${count.toLocaleString("es-ES")}</div>
        </div>
      `;
    })
    .join("");

  repressorStatsPanel.innerHTML = `
    <div class="repressor-stats-total">Total país: ${total.toLocaleString("es-ES")}</div>
    <div class="repressor-stats-list">${rowsHtml}</div>
  `;
}

async function fetchRepressorStatsData() {
  const response = await fetch("/api/v1/repressors/stats", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar el gráfico de represores.");
  }
  return await response.json();
}

async function refreshRepressorStats() {
  if (activeBaseMode !== "repressors") return;
  try {
    const payload = await fetchRepressorStatsData();
    repressorStatsPayload = payload;
    renderRepressorStats(payload);
  } catch (_error) {
    renderRepressorStats(
      repressorStatsPayload,
      "No fue posible actualizar el gráfico por provincia."
    );
  }
}

function renderRepressorLayer(payload) {
  if (!map) return;
  clearRepressorLayer();
  repressorLayerGroup = L.layerGroup();

  const confirmedItems = Array.isArray(payload?.confirmed_residences)
    ? payload.confirmed_residences
    : [];
  confirmedItems.forEach((item) => {
    const lat = Number(item?.latitude);
    const lng = Number(item?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const marker = L.marker([lat, lng], {
      icon: createMarkerIcon(
        CATEGORY_ICONS["residencia-represor"] || "fa-house-chimney-user",
        CATEGORY_IMAGES["residencia-represor"] || "",
        "residencia-represor",
        false
      ),
      title: item?.repressor_name || "Represor localizado",
    });
    marker.bindPopup(confirmedResidencePopupHtml(item), MAP_POPUP_OPTIONS);
    marker.on("click", () => {
      ensureContextPanelVisible({ mobileState: "full" });
      renderRepressorConfirmedDetail(item);
    });
    marker.addTo(repressorLayerGroup);
  });

  const unresolvedItems = Array.isArray(payload?.unresolved_territories)
    ? payload.unresolved_territories
    : [];
  unresolvedItems.forEach((item) => {
    const lat = Number(item?.latitude);
    const lng = Number(item?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const marker = L.marker([lat, lng], {
      icon: buildRepressorUnresolvedIcon(item?.count),
      title: `Sin localizar: ${Number(item?.count) || 0}`,
    });
    marker.bindPopup(unresolvedTerritoryPopupHtml(item), MAP_POPUP_OPTIONS);
    marker.on("click", () => {
      ensureContextPanelVisible({ mobileState: "full" });
      fetchRepressorTerritoryDetail(item);
    });
    marker.addTo(repressorLayerGroup);
  });

  repressorLayerGroup.addTo(map);
}

async function fetchRepressorLayerData() {
  const response = await fetch("/api/v1/repressors/map-layer", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar la capa de represores");
  }
  return await response.json();
}

async function refreshRepressorLayer() {
  if (activeBaseMode !== "repressors") return;
  try {
    const payload = await fetchRepressorLayerData();
    repressorLastPayload = payload;
    repressorUnresolvedDetailCache.clear();
    renderRepressorLayer(payload);
    renderRepressorSummary(payload);
  } catch (_error) {
    if (!repressorLastPayload) {
      clearRepressorLayer();
    }
    renderRepressorSummary(
      repressorLastPayload,
      "No fue posible actualizar la capa de represores."
    );
  }
}

async function enableRepressorMode() {
  activeBaseMode = "repressors";
  repressorDetailRequestSeq += 1;
  renderRepressorTerritoryDetailEmpty();
  clearMarkers();
  closeActivePopup();
  selectedReportId = null;
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(true);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  ensureContextPanelVisible({ mobileState: "mid" });
  renderRepressorStats(repressorStatsPayload, "Cargando gráfico de represores...");
  refreshRepressorStats();
  await refreshRepressorLayer();
}

function disableRepressorMode() {
  if (activeBaseMode !== "repressors") return;
  activeBaseMode = "map";
  repressorDetailRequestSeq += 1;
  repressorUnresolvedDetailCache.clear();
  clearRepressorLayer();
  repressorLastPayload = null;
  repressorStatsPayload = null;
  renderRepressorStats(null, "Selecciona la capa de represores para cargar el gráfico.");
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
}

function clearPrisonerLayer() {
  if (prisonerLayerGroup && map) {
    map.removeLayer(prisonerLayerGroup);
  }
  prisonerLayerGroup = null;
}

function buildPrisonerCountIcon(count) {
  const numeric = Math.max(1, Number(count) || 0);
  const label = numeric > 999 ? "999+" : String(numeric);
  return L.divIcon({
    className: "prisoner-count-marker-wrap",
    html: `<span class="prisoner-count-marker" style="background:${PRISONER_COUNT_COLOR};">${escapeHtml(
      label
    )}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -18],
  });
}

function prisonerTerritoryLabel(item) {
  const province = String(item?.province || "").trim();
  const municipality = String(item?.municipality || "").trim();
  const scope = String(item?.scope || "").trim().toLowerCase();
  if (scope === "municipality" && province && municipality) {
    return `${province} · ${municipality}`;
  }
  return province || "Territorio sin nombre";
}

function normalizePrisonerTerritoryRequest(item) {
  const scope = String(item?.scope || "").trim().toLowerCase();
  const province = String(item?.province || "").trim();
  const municipality = String(item?.municipality || "").trim();
  if (!["province", "municipality"].includes(scope)) return null;
  if (!province) return null;
  if (scope === "municipality" && !municipality) return null;
  const currentPrison = String(prisonerPrisonFilter?.value || "").trim();
  const key = `${scope}|${province.toLowerCase()}|${municipality.toLowerCase()}|${currentPrison.toLowerCase()}`;
  return { scope, province, municipality, prison: currentPrison, key };
}

function prisonerCountPopupHtml(item) {
  const territory = escapeHtml(prisonerTerritoryLabel(item));
  const count = Math.max(0, Number(item?.count) || 0);
  const prisons = Array.isArray(item?.prisons) ? item.prisons.filter(Boolean) : [];
  const countLabel =
    count === 1
      ? "1 prisionero político"
      : `${count.toLocaleString("es-ES")} prisioneros políticos`;
  const prisonsLabel = prisons.length
    ? `Prisiones registradas: ${escapeHtml(prisons.slice(0, 3).join(", "))}${
        prisons.length > 3 ? "..." : ""
      }`
    : "Sin prisión especificada";
  return `
    <div class="prisoner-popup">
      <div class="prisoner-popup-title">${territory}</div>
      <div class="prisoner-popup-meta">${countLabel}</div>
      <div class="prisoner-popup-meta">${prisonsLabel}</div>
    </div>
  `;
}

function renderPrisonerTerritoryDetailEmpty(message = "") {
  if (!reportDetailPanel) return;
  const text = message || "Haz click en un territorio para ver fichas de prisioneros.";
  setReportDetailEmptyState(true);
  reportDetailPanel.classList.remove("is-revealing");
  reportDetailPanel.innerHTML = `<div class="report-detail-empty">${escapeHtml(text)}</div>`;
}

function renderPrisonerTerritoryDetailLoading(territoryLabel) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${escapeHtml(territoryLabel)}</h3>
      <div class="report-detail-meta">Cargando fichas de prisioneros...</div>
    </div>
  `;
  triggerReportDetailReveal();
}

function renderPrisonerTerritoryDetail(item, payload) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  const territoryLabel = String(payload?.territory_label || prisonerTerritoryLabel(item) || "").trim();
  const entries = Array.isArray(payload?.items) ? payload.items : [];
  const count = Math.max(0, Number(payload?.count) || entries.length);
  const countLabel =
    count === 1
      ? "1 prisionero político"
      : `${count.toLocaleString("es-ES")} prisioneros políticos`;

  if (!entries.length) {
    reportDetailPanel.innerHTML = `
      <div class="report-detail-content">
        <h3 class="report-detail-title">${escapeHtml(territoryLabel || "Territorio")}</h3>
        <div class="report-detail-meta">${countLabel}</div>
        <div class="prisoner-detail-empty">No hay fichas registradas para este territorio.</div>
      </div>
    `;
    triggerReportDetailReveal();
    return;
  }

  const cardsHtml = entries
    .map((entry) => {
      const prisonerId = Number(entry?.id);
      if (!Number.isFinite(prisonerId) || prisonerId <= 0) return "";
      const fullName = escapeHtml(entry?.full_name || "Prisionero");
      const externalId = Number(entry?.external_id);
      const prisonName = escapeHtml(entry?.prison_name || "N/D");
      const penalStatus = escapeHtml(entry?.penal_status || "N/D");
      const imageUrl = safeUrl(entry?.image_url || "");
      const lat = Number(entry?.prison_latitude);
      const lng = Number(entry?.prison_longitude);
      const hasCoords = Number.isFinite(lat) && Number.isFinite(lng);
      const detailUrl = `/prisioneros/${prisonerId}`;
      const editUrl = `/prisioneros/${prisonerId}/editar`;
      const mapUrl = hasCoords
        ? `/map=prisioneros?lat=${lat.toFixed(6)}&lng=${lng.toFixed(6)}`
        : "";
      const metadata = [];
      if (Number.isFinite(externalId)) {
        metadata.push(`Ficha #${externalId}`);
      }
      metadata.push(`Prisión: ${prisonName}`);
      const imageThumbHtml = imageUrl
        ? `
            <button
              class="info-media-thumb prisoner-detail-thumb"
              type="button"
              data-image="${imageUrl}"
              data-caption="${fullName}"
            >
              <img src="${imageUrl}" alt="${fullName}" class="prisoner-detail-avatar" />
            </button>
          `
        : '<div class="prisoner-detail-avatar prisoner-detail-avatar-empty" aria-hidden="true">?</div>';
      return `
        <article class="prisoner-detail-card">
          <div class="prisoner-detail-head">
            ${imageThumbHtml}
            <div class="prisoner-detail-identity">
              <div class="prisoner-detail-name">${fullName}</div>
              <div class="prisoner-detail-meta">${metadata.join(" · ")}</div>
              <div class="prisoner-detail-meta">Estado penal: ${penalStatus}</div>
            </div>
          </div>
          <div class="prisoner-detail-actions">
            <a class="info-btn info-btn-outline" href="${detailUrl}">Ver ficha</a>
            <a class="info-btn info-btn-outline" href="${editUrl}">Editar ficha</a>
            ${
              mapUrl
                ? `<a class="info-btn" href="${mapUrl}">Ubicar prisión</a>`
                : `<span class="muted">Sin coordenadas de prisión</span>`
            }
          </div>
        </article>
      `;
    })
    .filter(Boolean)
    .join("");

  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${escapeHtml(territoryLabel || "Territorio")}</h3>
      <div class="report-detail-meta">${countLabel}</div>
      <div class="prisoner-detail-list">${cardsHtml}</div>
    </div>
  `;
  triggerReportDetailReveal();
  attachMediaThumbHandlers(reportDetailPanel);
  if (mapSideScroll) {
    mapSideScroll.scrollTop = 0;
  }
}

async function fetchPrisonerTerritoryDetail(item) {
  const requestData = normalizePrisonerTerritoryRequest(item);
  if (!requestData) {
    renderPrisonerTerritoryDetailEmpty("No se pudo determinar el territorio seleccionado.");
    return;
  }
  const territoryLabel = prisonerTerritoryLabel(requestData);
  const cached = prisonerTerritoryDetailCache.get(requestData.key);
  if (cached) {
    renderPrisonerTerritoryDetail(requestData, cached);
    return;
  }

  const requestSeq = ++prisonerDetailRequestSeq;
  renderPrisonerTerritoryDetailLoading(territoryLabel);
  const params = new URLSearchParams({
    scope: requestData.scope,
    province: requestData.province,
  });
  if (requestData.scope === "municipality") {
    params.set("municipality", requestData.municipality);
  }
  if (requestData.prison) {
    params.set("prison", requestData.prison);
  }

  try {
    const response = await fetch(`/api/v1/prisoners/territory?${params.toString()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("No se pudo cargar el detalle territorial.");
    }
    const payload = await response.json();
    if (requestSeq !== prisonerDetailRequestSeq) return;
    prisonerTerritoryDetailCache.set(requestData.key, payload);
    renderPrisonerTerritoryDetail(requestData, payload);
  } catch (_error) {
    if (requestSeq !== prisonerDetailRequestSeq) return;
    renderPrisonerTerritoryDetailEmpty(
      `No fue posible cargar la lista para ${territoryLabel}. Intenta nuevamente.`
    );
  }
}

function renderPrisonerSummary(payload, errorText = "") {
  if (!prisonerSummary) return;
  if (errorText) {
    prisonerSummary.textContent = errorText;
    return;
  }
  const summary = payload?.summary || {};
  const total = Number(summary.total_prisoners) || 0;
  const territories = Number(summary.territories_points) || 0;
  const withLocation = Number(summary.with_prison_location) || 0;
  const withoutLocation = Number(summary.without_prison_location) || 0;
  prisonerSummary.textContent = `Total: ${total.toLocaleString(
    "es-ES"
  )} · Territorios: ${territories.toLocaleString(
    "es-ES"
  )} · Con prisión localizada: ${withLocation.toLocaleString(
    "es-ES"
  )} · Sin ubicación de prisión: ${withoutLocation.toLocaleString("es-ES")}.`;
}

function renderPrisonerStats(payload, errorText = "") {
  if (!prisonerStatsPanel) return;
  if (errorText) {
    prisonerStatsPanel.innerHTML = `<div class="prisoner-stats-empty">${escapeHtml(errorText)}</div>`;
    return;
  }
  const total = Math.max(0, Number(payload?.total_prisoners) || 0);
  const byProvince = Array.isArray(payload?.by_province) ? payload.by_province : [];
  if (!byProvince.length) {
    prisonerStatsPanel.innerHTML = `
      <div class="prisoner-stats-total">Total país: ${total.toLocaleString("es-ES")}</div>
      <div class="prisoner-stats-empty">Sin datos provinciales disponibles.</div>
    `;
    return;
  }

  const topRows = byProvince.slice(0, 16);
  const maxCount = Math.max(...topRows.map((item) => Number(item?.count) || 0), 1);
  const rowsHtml = topRows
    .map((item) => {
      const province = escapeHtml(item?.province || "N/D");
      const count = Math.max(0, Number(item?.count) || 0);
      const width = Math.max(4, Math.round((count / maxCount) * 100));
      return `
        <div class="prisoner-stats-row">
          <div class="prisoner-stats-label">${province}</div>
          <div class="prisoner-stats-bar">
            <span style="width:${width}%"></span>
          </div>
          <div class="prisoner-stats-value">${count.toLocaleString("es-ES")}</div>
        </div>
      `;
    })
    .join("");

  prisonerStatsPanel.innerHTML = `
    <div class="prisoner-stats-total">Total país: ${total.toLocaleString("es-ES")}</div>
    <div class="prisoner-stats-list">${rowsHtml}</div>
  `;
}

function getPrisonerFilterValues() {
  return {
    province: prisonerProvinceFilter?.value || "",
    municipality: prisonerMunicipalityFilter?.value || "",
    prison: prisonerPrisonFilter?.value || "",
  };
}

function syncPrisonerFilterOptions(filters) {
  if (!filters || typeof filters !== "object") return;
  const provinceOptions = Array.isArray(filters.provinces) ? filters.provinces : [];
  const municipalityOptions = Array.isArray(filters.municipalities) ? filters.municipalities : [];
  const prisonOptions = Array.isArray(filters.prisons) ? filters.prisons : [];

  const updateSelect = (selectEl, options, placeholder, selected) => {
    if (!selectEl) return;
    const selectedValue = String(selected || "").trim();
    const html =
      `<option value="">${placeholder}</option>` +
      options
        .map((value) => {
          const text = String(value || "").trim();
          if (!text) return "";
          const isSelected = text === selectedValue ? " selected" : "";
          return `<option value="${escapeHtml(text)}"${isSelected}>${escapeHtml(text)}</option>`;
        })
        .join("");
    selectEl.innerHTML = html;
  };

  const selectedProvince = String(filters.selected_province || prisonerProvinceFilter?.value || "").trim();
  const selectedMunicipality = String(
    filters.selected_municipality || prisonerMunicipalityFilter?.value || ""
  ).trim();
  const selectedPrison = String(filters.selected_prison || prisonerPrisonFilter?.value || "").trim();

  updateSelect(prisonerProvinceFilter, provinceOptions, "Todas", selectedProvince);
  updateSelect(prisonerMunicipalityFilter, municipalityOptions, "Todos", selectedMunicipality);
  updateSelect(prisonerPrisonFilter, prisonOptions, "Todas", selectedPrison);
}

function buildPrisonerQueryString() {
  const params = new URLSearchParams();
  const { province, municipality, prison } = getPrisonerFilterValues();
  if (province) params.set("province", province);
  if (municipality) params.set("municipality", municipality);
  if (prison) params.set("prison", prison);
  return params.toString();
}

async function fetchPrisonerStatsData() {
  const query = buildPrisonerQueryString();
  const url = query ? `/api/v1/prisoners/stats?${query}` : "/api/v1/prisoners/stats";
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar el gráfico de prisioneros.");
  }
  return await response.json();
}

async function refreshPrisonerStats() {
  if (activeBaseMode !== "prisoners") return;
  try {
    const payload = await fetchPrisonerStatsData();
    prisonerStatsPayload = payload;
    renderPrisonerStats(payload);
  } catch (_error) {
    renderPrisonerStats(
      prisonerStatsPayload,
      "No fue posible actualizar el gráfico por provincia."
    );
  }
}

function renderPrisonerLayer(payload) {
  if (!map) return;
  clearPrisonerLayer();
  prisonerLayerGroup = L.layerGroup();
  const points = Array.isArray(payload?.points) ? payload.points : [];
  points.forEach((item) => {
    const lat = Number(item?.latitude);
    const lng = Number(item?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const marker = L.marker([lat, lng], {
      icon: buildPrisonerCountIcon(item?.count),
      title: `Prisioneros políticos: ${Number(item?.count) || 0}`,
    });
    marker.bindPopup(prisonerCountPopupHtml(item), MAP_POPUP_OPTIONS);
    marker.on("click", () => {
      ensureContextPanelVisible({ mobileState: "full" });
      fetchPrisonerTerritoryDetail(item);
    });
    marker.addTo(prisonerLayerGroup);
  });
  prisonerLayerGroup.addTo(map);
}

async function fetchPrisonerLayerData() {
  const query = buildPrisonerQueryString();
  const url = query ? `/api/v1/prisoners/map-layer?${query}` : "/api/v1/prisoners/map-layer";
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar la capa de prisioneros");
  }
  return await response.json();
}

async function refreshPrisonerLayer() {
  if (activeBaseMode !== "prisoners") return;
  try {
    const payload = await fetchPrisonerLayerData();
    prisonerLastPayload = payload;
    prisonerTerritoryDetailCache.clear();
    syncPrisonerFilterOptions(payload?.filters);
    renderPrisonerLayer(payload);
    renderPrisonerSummary(payload);
  } catch (_error) {
    if (!prisonerLastPayload) {
      clearPrisonerLayer();
    }
    renderPrisonerSummary(
      prisonerLastPayload,
      "No fue posible actualizar la capa de prisioneros."
    );
  }
}

function wirePrisonerFilters() {
  const triggerRefresh = () => {
    if (activeBaseMode !== "prisoners") return;
    prisonerTerritoryDetailCache.clear();
    refreshPrisonerLayer();
    refreshPrisonerStats();
  };

  const bindOnce = (el) => {
    if (!el || el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    el.addEventListener("change", triggerRefresh);
  };

  bindOnce(prisonerProvinceFilter);
  bindOnce(prisonerMunicipalityFilter);
  bindOnce(prisonerPrisonFilter);
}

async function enablePrisonerMode() {
  activeBaseMode = "prisoners";
  prisonerDetailRequestSeq += 1;
  prisonerTerritoryDetailCache.clear();
  renderPrisonerTerritoryDetailEmpty();
  clearMarkers();
  closeActivePopup();
  selectedReportId = null;
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(true);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  ensureContextPanelVisible({ mobileState: "mid" });
  wirePrisonerFilters();
  renderPrisonerStats(prisonerStatsPayload, "Cargando gráfico de prisioneros...");
  refreshPrisonerStats();
  await refreshPrisonerLayer();
}

function disablePrisonerMode() {
  if (activeBaseMode !== "prisoners") return;
  activeBaseMode = "map";
  prisonerDetailRequestSeq += 1;
  prisonerTerritoryDetailCache.clear();
  clearPrisonerLayer();
  prisonerLastPayload = null;
  prisonerStatsPayload = null;
  renderPrisonerStats(null, "Selecciona la capa de prisioneros para cargar el gráfico.");
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
}

function clearAISLayer() {
  if (aisLayerGroup && map) {
    map.removeLayer(aisLayerGroup);
  }
  aisLayerGroup = null;
}

function stopAISPolling() {
  if (!aisRefreshTimer) return;
  clearInterval(aisRefreshTimer);
  aisRefreshTimer = null;
}

function startAISPolling() {
  stopAISPolling();
  const intervalMs = Math.max(60, Number(aisRefreshSeconds) || 1800) * 1000;
  aisRefreshTimer = setInterval(() => {
    refreshAISLayer();
  }, intervalMs);
}

function buildAISMarkerIcon(confidence) {
  const safeConfidence = Math.max(0, Math.min(1, Number(confidence) || 0));
  const borderAlpha = 0.55 + safeConfidence * 0.45;
  const color = `rgba(14, 165, 233, ${Math.max(0.65, safeConfidence).toFixed(2)})`;
  return L.divIcon({
    className: "ais-marker-wrap",
    html: `<span class="ais-marker-dot" style="background:${color};border-color:rgba(255,255,255,${borderAlpha.toFixed(
      2
    )});"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -10],
  });
}

function formatAISValue(value, unit = "") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  return `${numeric.toFixed(1)}${unit}`;
}

function formatAISConfidence(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/D";
  return `${Math.round(Math.max(0, Math.min(1, numeric)) * 100)}%`;
}

function aisPopupHtml(item) {
  const vesselName = escapeHtml(item?.ship_name || "Buque sin nombre");
  const destination = escapeHtml(item?.destination_raw || "N/D");
  const portName = escapeHtml(item?.matched_port_name || "Puerto no resuelto");
  const confidence = escapeHtml(formatAISConfidence(item?.match_confidence));
  const speed = escapeHtml(formatAISValue(item?.sog, " kn"));
  const course = escapeHtml(formatAISValue(item?.cog, "°"));
  const mmsi = escapeHtml(item?.mmsi || "N/D");
  return `
    <div class="ais-popup">
      <div class="ais-popup-title">${vesselName}</div>
      <div class="ais-popup-meta">MMSI: ${mmsi}</div>
      <div class="ais-popup-meta">Destino: ${destination}</div>
      <div class="ais-popup-meta">Puerto objetivo: ${portName}</div>
      <div class="ais-popup-meta">Confianza: ${confidence}</div>
      <div class="ais-popup-meta">Velocidad: ${speed} · Rumbo: ${course}</div>
    </div>
  `;
}

function renderAISVesselDetail(item) {
  if (!reportDetailPanel) return;
  setReportDetailEmptyState(false);
  const vesselName = escapeHtml(item?.ship_name || "Buque sin nombre");
  const destination = escapeHtml(item?.destination_raw || "N/D");
  const portName = escapeHtml(item?.matched_port_name || "Puerto no resuelto");
  const confidence = escapeHtml(formatAISConfidence(item?.match_confidence));
  const speed = escapeHtml(formatAISValue(item?.sog, " kn"));
  const course = escapeHtml(formatAISValue(item?.cog, "°"));
  const heading = escapeHtml(formatAISValue(item?.heading, "°"));
  const mmsi = escapeHtml(item?.mmsi || "N/D");
  const imo = escapeHtml(item?.imo || "N/D");
  const callSign = escapeHtml(item?.call_sign || "N/D");
  const updatedAt = escapeHtml(formatUtcAndCuba(item?.last_seen_at_utc || ""));

  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${vesselName}</h3>
      <div class="report-detail-meta">MMSI: ${mmsi} · IMO: ${imo} · Call Sign: ${callSign}</div>
      <div class="report-detail-meta">Destino reportado: ${destination}</div>
      <div class="report-detail-meta">Puerto cubano detectado: ${portName}</div>
      <div class="report-detail-meta">Confianza de match: ${confidence}</div>
      <div class="report-detail-meta">SOG: ${speed} · COG: ${course} · Heading: ${heading}</div>
      <div class="report-detail-meta">Última señal: ${updatedAt || "N/D"}</div>
    </div>
  `;
  triggerReportDetailReveal();
  if (mapSideScroll) mapSideScroll.scrollTop = 0;
}

function renderAISPortList(payload) {
  if (!aisPortList) return;
  const rows = Array.isArray(payload?.summary?.by_port) ? payload.summary.by_port : [];
  if (!rows.length) {
    aisPortList.innerHTML = `<div class="ais-port-empty">No hay puertos detectados en este snapshot.</div>`;
    return;
  }
  aisPortList.innerHTML = rows
    .slice(0, 20)
    .map((row) => {
      const port = escapeHtml(row?.port || "N/D");
      const count = Math.max(0, Number(row?.count) || 0).toLocaleString("es-ES");
      return `<div class="ais-port-row"><span>${port}</span><strong>${count}</strong></div>`;
    })
    .join("");
}

function renderAISSummary(payload, errorText = "") {
  if (!aisSummary) return;
  if (errorText) {
    aisSummary.textContent = errorText;
    return;
  }
  const total = Math.max(0, Number(payload?.summary?.total_points) || 0);
  const latestRun = payload?.latest_run || {};
  const matchedVessels = Math.max(0, Number(latestRun?.matched_vessels) || 0);
  const status = String(latestRun?.status || "N/D").trim();
  const stale = Boolean(payload?.stale);
  const staleLabel = stale ? "desactualizado" : "vigente";
  aisSummary.textContent = `Puntos en mapa: ${total.toLocaleString(
    "es-ES"
  )} · Match diarios: ${matchedVessels.toLocaleString("es-ES")} · Run: ${status} (${staleLabel}).`;
}

function renderAISLayer(payload) {
  if (!map) return;
  clearAISLayer();
  aisLayerGroup = L.layerGroup();

  const points = Array.isArray(payload?.points) ? payload.points : [];
  points.forEach((item) => {
    const lat = Number(item?.latitude);
    const lng = Number(item?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const marker = L.marker([lat, lng], {
      icon: buildAISMarkerIcon(item?.match_confidence),
      title: item?.ship_name || item?.mmsi || "Buque",
    });
    marker.bindPopup(aisPopupHtml(item), MAP_POPUP_OPTIONS);
    marker.on("click", () => {
      ensureContextPanelVisible({ mobileState: "full" });
      renderAISVesselDetail(item);
    });
    marker.addTo(aisLayerGroup);
  });

  aisLayerGroup.addTo(map);
  renderAISPortList(payload);
}

async function fetchAISLayerData() {
  const response = await fetch("/api/v1/ais/cuba-targets", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar la capa AIS");
  }
  return await response.json();
}

async function refreshAISLayer() {
  if (activeBaseMode !== "ais") return;
  try {
    const payload = await fetchAISLayerData();
    aisLastPayload = payload;
    renderAISLayer(payload);
    renderAISSummary(payload);
  } catch (_error) {
    if (!aisLastPayload) {
      clearAISLayer();
    }
    renderAISSummary(aisLastPayload, "No fue posible actualizar la capa AIS.");
  }
}

async function enableAISMode() {
  if (!isAdmin) return;
  activeBaseMode = "ais";
  clearMarkers();
  closeActivePopup();
  selectedReportId = null;
  renderReportDetail(null);
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(true);
  setFlightsOverlayVisible(false);
  ensureContextPanelVisible({ mobileState: "mid" });
  renderAISSummary(aisLastPayload, "Cargando capa AIS...");
  await refreshAISLayer();
  startAISPolling();
}

function disableAISMode() {
  if (activeBaseMode !== "ais") return;
  activeBaseMode = "map";
  stopAISPolling();
  clearAISLayer();
  aisLastPayload = null;
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
}

function clearFlightsLayer() {
  if (flightsLayerGroup && map) {
    map.removeLayer(flightsLayerGroup);
  }
  flightsLayerGroup = null;
}

function clearFlightsTrack() {
  if (flightsTrackLayer && map) {
    map.removeLayer(flightsTrackLayer);
  }
  flightsTrackLayer = null;
}

function stopFlightsPolling() {
  if (!flightsRefreshTimer) return;
  clearInterval(flightsRefreshTimer);
  flightsRefreshTimer = null;
}

function startFlightsPolling() {
  stopFlightsPolling();
  const intervalMs = Math.max(30, Number(flightsRefreshSeconds) || 300) * 1000;
  flightsRefreshTimer = setInterval(() => {
    refreshFlightsLayer();
  }, intervalMs);
}

function buildFlightsMarkerIcon(heading) {
  const color = FLIGHTS_MARKER_COLOR;
  const numericHeading = Number(heading);
  const normalizedHeading = Number.isFinite(numericHeading)
    ? ((numericHeading % 360) + 360) % 360
    : 0;
  return L.divIcon({
    className: "flights-marker-wrap",
    html: `<span class="flights-marker-plane" style="--flight-marker-color:${color};--flight-marker-heading:${normalizedHeading.toFixed(
      1
    )}deg;" aria-hidden="true"><i class="fa-solid fa-plane-up"></i></span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -16],
  });
}

function resolveFlightDetailCache(item) {
  const eventId = Number(item?.event_id);
  if (Number.isFinite(eventId) && flightsDetailCacheByEvent.has(eventId)) {
    return flightsDetailCacheByEvent.get(eventId);
  }
  const aircraftId = Number(item?.aircraft_id);
  if (Number.isFinite(aircraftId) && flightsDetailCacheByAircraft.has(aircraftId)) {
    return flightsDetailCacheByAircraft.get(aircraftId);
  }
  return null;
}

function cacheFlightDetail(item, detailPayload, trackPayload) {
  const entry = {
    detailPayload,
    trackPayload,
    cachedAt: Date.now(),
  };
  const eventId = Number(item?.event_id);
  if (Number.isFinite(eventId)) {
    flightsDetailCacheByEvent.set(eventId, entry);
  }
  const aircraftId = Number(item?.aircraft_id);
  if (Number.isFinite(aircraftId)) {
    flightsDetailCacheByAircraft.set(aircraftId, entry);
  }
  return entry;
}

function formatFlightAirportIndicator(name, city, country, fallbackName = "Aeropuerto N/D") {
  const airportName = String(name || "").trim() || fallbackName;
  const cityName = String(city || "").trim() || airportName;
  const countryName = String(country || "").trim() || "N/D";
  return `${airportName} (${cityName}, ${countryName})`;
}

function buildFlightPopupData(item, detailPayload = null, trackPayload = null) {
  const merged = {
    ...item,
    call_sign: item?.call_sign || "",
    model: item?.model || "",
    origin_airport_name: item?.origin_airport_name || "",
    origin_city: item?.origin_city || "",
    origin_country: item?.origin_country || "",
    destination_airport_name: item?.destination_airport_name || "",
    destination_city: item?.destination_city || "",
    destination_country: item?.destination_country || "",
  };

  const aircraft = detailPayload?.aircraft || {};
  if (aircraft?.call_sign) merged.call_sign = aircraft.call_sign;
  if (aircraft?.model) merged.model = aircraft.model;

  const historyRows = Array.isArray(detailPayload?.history) ? detailPayload.history : [];
  const eventId = Number(item?.event_id);
  let eventRow = null;
  if (Number.isFinite(eventId)) {
    eventRow = historyRows.find((row) => Number(row?.event_id) === eventId) || null;
  }
  if (!eventRow && historyRows.length) {
    eventRow = historyRows[0];
  }
  if (eventRow) {
    merged.origin_airport_name = eventRow?.origin_airport_name || merged.origin_airport_name;
    merged.origin_city = eventRow?.origin_city || merged.origin_city;
    merged.origin_country = eventRow?.origin_country || merged.origin_country;
    merged.destination_airport_name =
      eventRow?.destination_airport_name || merged.destination_airport_name;
    merged.destination_city = eventRow?.destination_city || merged.destination_city;
    merged.destination_country = eventRow?.destination_country || merged.destination_country;
  }

  const trackEvent = trackPayload?.event || {};
  merged.origin_airport_name = trackEvent?.origin_airport_name || merged.origin_airport_name;
  merged.origin_country = trackEvent?.origin_country || merged.origin_country;
  merged.destination_airport_name =
    trackEvent?.destination_airport_name || merged.destination_airport_name;
  merged.destination_country = trackEvent?.destination_country || merged.destination_country;
  const routeOrigin = trackPayload?.route?.origin || {};
  const routeDestination = trackPayload?.route?.destination || {};
  merged.origin_city = routeOrigin?.city || merged.origin_city;
  merged.destination_city = routeDestination?.city || merged.destination_city;

  return merged;
}

function flightsPopupHtml(item) {
  const popupData = buildFlightPopupData(item);
  const callSign = escapeHtml(popupData?.call_sign || "Vuelo");
  const model = escapeHtml(popupData?.model || "Modelo N/D");
  const origin = escapeHtml(
    formatFlightAirportIndicator(
      popupData?.origin_airport_name,
      popupData?.origin_city,
      popupData?.origin_country,
      "Origen N/D"
    )
  );
  const destination = escapeHtml(
    formatFlightAirportIndicator(
      popupData?.destination_airport_name,
      popupData?.destination_city,
      popupData?.destination_country,
      "Destino Cuba"
    )
  );
  return `
    <div class="flights-popup">
      <div class="flights-popup-title">${callSign}</div>
      <div class="flights-popup-meta">${model}</div>
      <div class="flights-popup-meta"><strong>Origen:</strong> ${origin}</div>
      <div class="flights-popup-meta"><strong>Destino:</strong> ${destination}</div>
    </div>
  `;
}

function renderFlightsAirportsList(payload) {
  if (!flightsAirportsList) return;
  const rows = Array.isArray(payload?.summary?.by_destination_airport)
    ? payload.summary.by_destination_airport
    : [];
  if (!rows.length) {
    flightsAirportsList.innerHTML = `<div class="flights-airports-empty">Sin datos de aeropuertos en esta ventana.</div>`;
    return;
  }
  flightsAirportsList.innerHTML = rows
    .slice(0, 20)
    .map((row) => {
      const airport = escapeHtml(row?.airport || "Aeropuerto Cuba");
      const count = Math.max(0, Number(row?.count) || 0).toLocaleString("es-ES");
      return `<div class="flights-airports-row"><span>${airport}</span><strong>${count}</strong></div>`;
    })
    .join("");
}

function renderFlightsSummary(payload, errorText = "") {
  if (!flightsSummary || !flightsMeta) return;
  if (errorText) {
    flightsSummary.textContent = errorText;
    flightsMeta.textContent = "No se pudo actualizar la capa.";
    return;
  }

  const summary = payload?.summary || {};
  const totalFlights = Math.max(0, Number(summary?.total_flights) || 0);
  const destinationAirports = Math.max(0, Number(summary?.destination_airports) || 0);
  const stale = Boolean(payload?.stale);
  const staleLabel = stale ? "desactualizado" : "vigente";
  const run = payload?.latest_run || {};
  const status = String(run?.status || "N/D").trim();
  const safeMode = Boolean(run?.safe_mode);
  const safeModeLabel = safeMode ? "modo seguro activo" : "modo normal";
  const generatedAt = formatUtcLabel(payload?.snapshot?.generated_at_utc || "");

  flightsSummary.textContent = `Vuelos en mapa: ${totalFlights.toLocaleString(
    "es-ES"
  )} · Aeropuertos destino: ${destinationAirports.toLocaleString("es-ES")} · Snapshot ${staleLabel}.`;
  flightsMeta.textContent = `Run: ${status} · ${safeModeLabel} · Actualizado: ${
    generatedAt || "N/D"
  }.`;
}

function drawFlightTrack(trackPayload) {
  if (!map) return;
  clearFlightsTrack();

  const points = Array.isArray(trackPayload?.track?.points) ? trackPayload.track.points : [];
  const latlngs = points
    .map((point) => [Number(point?.latitude), Number(point?.longitude)])
    .filter((pair) => Number.isFinite(pair[0]) && Number.isFinite(pair[1]));
  const rawRouteOrigin = trackPayload?.route?.origin || {};
  const rawRouteDestination = trackPayload?.route?.destination || {};
  const routeOriginCandidate = [Number(rawRouteOrigin?.latitude), Number(rawRouteOrigin?.longitude)];
  const routeDestinationCandidate = [
    Number(rawRouteDestination?.latitude),
    Number(rawRouteDestination?.longitude),
  ];
  const hasRouteOrigin = Number.isFinite(routeOriginCandidate[0]) && Number.isFinite(routeOriginCandidate[1]);
  const hasRouteDestination =
    Number.isFinite(routeDestinationCandidate[0]) && Number.isFinite(routeDestinationCandidate[1]);

  const fallbackOrigin = latlngs[0];
  const fallbackDestination = latlngs.length ? latlngs[latlngs.length - 1] : null;
  const routeOrigin = hasRouteOrigin ? routeOriginCandidate : fallbackOrigin || null;
  const routeDestination = hasRouteDestination
    ? routeDestinationCandidate
    : fallbackDestination || routeOrigin || null;

  if (!latlngs.length && !routeOrigin && !routeDestination) return;

  flightsTrackLayer = L.layerGroup();

  if (latlngs.length >= 2) {
    const trackLine = L.polyline(latlngs, {
      color: "#94a3b8",
      weight: 1.5,
      opacity: 0.35,
      dashArray: "4 6",
    });
    trackLine.addTo(flightsTrackLayer);
  }

  const aircraftPoint = latlngs.length
    ? latlngs[latlngs.length - 1]
    : routeDestination || routeOrigin || null;

  if (routeOrigin) {
    L.circleMarker(routeOrigin, {
      radius: 4,
      color: "#ffffff",
      weight: 1.5,
      fillColor: "#ef4444",
      fillOpacity: 0.98,
    }).addTo(flightsTrackLayer);
  }

  if (routeDestination) {
    L.circleMarker(routeDestination, {
      radius: 4,
      color: "#ffffff",
      weight: 1.5,
      fillColor: "#3b82f6",
      fillOpacity: 0.98,
    }).addTo(flightsTrackLayer);
  }

  if (routeOrigin && aircraftPoint) {
    const originToAircraft = L.polyline([routeOrigin, aircraftPoint], {
      color: "#ef4444",
      weight: 3,
      opacity: 0.92,
    });
    originToAircraft.addTo(flightsTrackLayer);
  }

  if (aircraftPoint && routeDestination) {
    const aircraftToDestination = L.polyline([aircraftPoint, routeDestination], {
      color: "#3b82f6",
      weight: 3,
      opacity: 0.92,
    });
    aircraftToDestination.addTo(flightsTrackLayer);
  }

  if (aircraftPoint) {
    L.circleMarker(aircraftPoint, {
      radius: 5,
      color: "#ffffff",
      weight: 2,
      fillColor: "#f97316",
      fillOpacity: 0.95,
    }).addTo(flightsTrackLayer);
  }

  flightsTrackLayer.addTo(map);
}

function cleanupFlightsPhotoModal() {
  if (flightsPhotoModalNode && flightsPhotoModalNode.parentElement) {
    flightsPhotoModalNode.remove();
  }
  flightsPhotoModalNode = null;
}

function renderFlightDetailLoading(item) {
  if (!reportDetailPanel) return;
  cleanupFlightsPhotoModal();
  setReportDetailEmptyState(false);
  const callSign = escapeHtml(item?.call_sign || "Vuelo");
  reportDetailPanel.innerHTML = `
    <div class="report-detail-content">
      <h3 class="report-detail-title">${callSign}</h3>
      <div class="report-detail-meta">Cargando detalle de avión y track...</div>
    </div>
  `;
  triggerReportDetailReveal();
  if (mapSideScroll) mapSideScroll.scrollTop = 0;
}

function renderFlightDetail(item, detailPayload, trackPayload) {
  if (!reportDetailPanel) return;
  cleanupFlightsPhotoModal();
  setReportDetailEmptyState(false);

  const aircraft = detailPayload?.aircraft || {};
  const summary30d = detailPayload?.summary_30d || {};
  const history = Array.isArray(detailPayload?.history) ? detailPayload.history : [];
  const origins = Array.isArray(summary30d?.origins) ? summary30d.origins : [];
  const destinations = Array.isArray(summary30d?.destinations) ? summary30d.destinations : [];
  const callSign = escapeHtml(aircraft?.call_sign || item?.call_sign || "Vuelo");
  const model = escapeHtml(aircraft?.model || item?.model || "Modelo N/D");
  const registration = escapeHtml(aircraft?.registration || item?.registration || "N/D");
  const operator = escapeHtml(aircraft?.operator_name || "N/D");
  const tripsToCuba = Math.max(0, Number(summary30d?.trips_to_cuba) || 0).toLocaleString("es-ES");
  const photoUrl = safeUrl(aircraft?.photo_url || item?.photo_url || "");
  const photoSource = String(aircraft?.photo_source || "none");
  const photoSourceLabel =
    photoSource === "manual" ? "Foto asignada manualmente" : photoSource === "api" ? "Foto de la API" : "Sin foto";
  const photoUploadEnabled = Boolean(
    detailPayload?.photo_upload_enabled ?? detailPayload?.cloudinary_enabled
  );
  const aircraftId = Number(aircraft?.id || item?.aircraft_id);
  const latestTrackPointCount = Math.max(0, Number(trackPayload?.track?.point_count) || 0);
  const canUploadPhoto = photoUploadEnabled && Number.isFinite(aircraftId);
  const hasPhoto = Boolean(photoUrl);

  const topOrigins = origins
    .slice(0, 4)
    .map((row) => `${escapeHtml(row?.origin || "N/D")} (${Math.max(0, Number(row?.count) || 0)})`)
    .join(" · ");
  const topDestinations = destinations
    .slice(0, 4)
    .map((row) => `${escapeHtml(row?.destination || "N/D")} (${Math.max(0, Number(row?.count) || 0)})`)
    .join(" · ");

  const historyRows = history
    .slice(0, 8)
    .map((row) => {
      const origin = escapeHtml(
        formatFlightAirportIndicator(
          row?.origin_airport_name,
          row?.origin_city,
          row?.origin_country,
          "Origen N/D"
        )
      );
      const destination = escapeHtml(
        formatFlightAirportIndicator(
          row?.destination_airport_name,
          row?.destination_city,
          row?.destination_country,
          "Destino N/D"
        )
      );
      const when = escapeHtml(formatUtcAndCuba(row?.last_seen_at_utc || ""));
      const status = escapeHtml(row?.status || "N/D");
      return `<div class=\"flights-history-row\"><strong>${origin} -> ${destination}</strong><span>${when} · ${status}</span></div>`;
    })
    .join("");

  const uploadFormMarkup = `
    <form class=\"flights-photo-form\" data-flight-photo-form data-aircraft-id=\"${aircraftId}\">
      <label class=\"flights-photo-label\">Selecciona una imagen</label>
      <input type=\"file\" name=\"photo\" accept=\"image/*\" required />
      <button type=\"submit\" class=\"flights-photo-btn\">Guardar imagen</button>
      <div class=\"flights-photo-feedback\" data-flight-photo-feedback></div>
    </form>
  `;
  const inlineUploadSection = canUploadPhoto && !hasPhoto ? uploadFormMarkup : "";
  const replacePrompt = canUploadPhoto && hasPhoto
    ? `<button type=\"button\" class=\"flights-photo-replace-link\" data-flight-photo-replace-open>¿La imagen no es correcta? Reemplazar</button>`
    : "";
  const replaceModal = canUploadPhoto && hasPhoto
    ? `
      <div class=\"modal-overlay flights-photo-modal\" data-flight-photo-modal aria-hidden=\"true\">
        <div class=\"modal flights-photo-modal-shell\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Reemplazar imagen de avión\">
          <button type=\"button\" class=\"modal-close\" data-flight-photo-modal-close>&times;</button>
          <div class=\"flights-photo-modal-body\">
            <h4>Reemplazar imagen</h4>
            ${uploadFormMarkup}
            <div class=\"flights-photo-modal-actions\">
              <button type=\"button\" class=\"info-btn info-btn-outline\" data-flight-photo-modal-close>Cancelar</button>
              <button type=\"button\" class=\"info-btn\" data-flight-photo-modal-close>Cerrar</button>
            </div>
          </div>
        </div>
      </div>
    `
    : "";

  reportDetailPanel.innerHTML = `
    <div class=\"report-detail-content\">
      <h3 class=\"report-detail-title\">${callSign}</h3>
      <div class=\"report-detail-meta\">Modelo: ${model} · Matricula: ${registration}</div>
      <div class=\"report-detail-meta\">Operador: ${operator} · Viajes a Cuba (30d): ${tripsToCuba}</div>
      <div class=\"report-detail-meta\">Track disponible: ${latestTrackPointCount.toLocaleString("es-ES")} puntos</div>
      <div class=\"report-detail-meta\">Foto: ${escapeHtml(photoSourceLabel)}</div>
      ${
        photoUrl
          ? `<img class=\"flights-detail-photo\" src=\"${photoUrl}\" alt=\"Foto de aeronave\" loading=\"lazy\" />`
          : `<div class=\"report-detail-meta\">No hay foto disponible para esta aeronave.</div>`
      }
      ${replacePrompt}
      ${inlineUploadSection}
      ${replaceModal}
      <div class=\"report-detail-meta\">Orígenes frecuentes: ${topOrigins || "N/D"}</div>
      <div class=\"report-detail-meta\">Destinos en Cuba: ${topDestinations || "N/D"}</div>
      <div class=\"flights-history-list\">
        ${
          historyRows ||
          '<div class=\"report-detail-meta\">Sin historial de viajes hacia Cuba en los últimos 30 días.</div>'
        }
      </div>
    </div>
  `;
  triggerReportDetailReveal();
  if (mapSideScroll) mapSideScroll.scrollTop = 0;

  let modal = reportDetailPanel.querySelector("[data-flight-photo-modal]");
  if (modal && document.body) {
    modal.setAttribute("data-flight-photo-modal-global", "1");
    document.body.appendChild(modal);
    flightsPhotoModalNode = modal;
  }
  const openModalBtn = reportDetailPanel.querySelector("[data-flight-photo-replace-open]");
  const closeModal = () => {
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  };
  if (openModalBtn && modal) {
    openModalBtn.addEventListener("click", () => {
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    });
    modal.querySelectorAll("[data-flight-photo-modal-close]").forEach((button) => {
      button.addEventListener("click", closeModal);
    });
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });
  }

  const forms = Array.from(reportDetailPanel.querySelectorAll("[data-flight-photo-form]"));
  if (modal) {
    forms.push(...Array.from(modal.querySelectorAll("[data-flight-photo-form]")));
  }
  if (!forms.length) return;
  forms.forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = form.querySelector("input[name='photo']");
      const feedback = form.querySelector("[data-flight-photo-feedback]");
      const submitBtn = form.querySelector("button[type='submit']");
      const file = input?.files?.[0];
      if (!file) {
        if (feedback) feedback.textContent = "Selecciona una imagen primero.";
        return;
      }

      const formData = new FormData();
      formData.append("photo", file);
      if (submitBtn) submitBtn.disabled = true;
      if (feedback) feedback.textContent = "Subiendo imagen...";

      try {
        const response = await fetch(`/api/v1/flights/aircraft/${aircraftId}/photo`, {
          method: "POST",
          body: formData,
        });
        const payload = await response.json();
        if (!response.ok || !payload?.ok) {
          throw new Error(payload?.error || "No se pudo subir la foto.");
        }
        if (feedback) feedback.textContent = "Imagen actualizada.";
        closeModal();
        await showFlightDetail(item);
      } catch (error) {
        if (feedback) feedback.textContent = error?.message || "No se pudo subir la foto.";
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });
}

async function fetchFlightsLayerData() {
  const params = new URLSearchParams();
  params.set("window_hours", String(flightsWindowHours));
  const url = `/api/v1/flights/cuba-layer?${params.toString()}`;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar la capa de vuelos.");
  }
  return await response.json();
}

async function fetchFlightDetail(aircraftId, eventId) {
  const safeId = Number(aircraftId);
  if (!Number.isFinite(safeId)) {
    throw new Error("Avión inválido.");
  }
  const params = new URLSearchParams();
  const safeEventId = Number(eventId);
  if (Number.isFinite(safeEventId)) {
    params.set("event_id", String(safeEventId));
  }
  const queryString = params.toString();
  const response = await fetch(
    `/api/v1/flights/aircraft/${safeId}/detail${queryString ? `?${queryString}` : ""}`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error("No se pudo cargar detalle del avión.");
  }
  return await response.json();
}

async function fetchFlightTrack(eventId) {
  const safeId = Number(eventId);
  if (!Number.isFinite(safeId)) {
    throw new Error("Evento de vuelo inválido.");
  }
  const response = await fetch(`/api/v1/flights/events/${safeId}/track`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo cargar track del vuelo.");
  }
  return await response.json();
}

async function showFlightDetail(item, marker = null) {
  const aircraftId = Number(item?.aircraft_id);
  const eventId = Number(item?.event_id);
  if (!Number.isFinite(aircraftId) || !Number.isFinite(eventId)) {
    return;
  }

  const cached = resolveFlightDetailCache(item);
  if (marker && cached?.detailPayload) {
    const cachedPopupData = buildFlightPopupData(item, cached.detailPayload, cached.trackPayload);
    marker.setPopupContent(flightsPopupHtml(cachedPopupData));
    if (marker.isPopupOpen()) {
      marker.getPopup()?.update();
    }
  }

  const requestSeq = ++flightsDetailRequestSeq;
  renderFlightDetailLoading(item);
  try {
    const [detailPayload, trackPayload] = await Promise.all([
      fetchFlightDetail(aircraftId, eventId),
      fetchFlightTrack(eventId),
    ]);
    if (requestSeq !== flightsDetailRequestSeq || activeBaseMode !== "flights") return;
    cacheFlightDetail(item, detailPayload, trackPayload);
    if (marker) {
      const popupData = buildFlightPopupData(item, detailPayload, trackPayload);
      marker.setPopupContent(flightsPopupHtml(popupData));
      if (marker.isPopupOpen()) {
        marker.getPopup()?.update();
      }
    }
    drawFlightTrack(trackPayload);
    renderFlightDetail(item, detailPayload, trackPayload);
  } catch (error) {
    if (requestSeq !== flightsDetailRequestSeq || activeBaseMode !== "flights") return;
    cleanupFlightsPhotoModal();
    setReportDetailEmptyState(false);
    reportDetailPanel.innerHTML = `
      <div class=\"report-detail-content\">
        <h3 class=\"report-detail-title\">Detalle no disponible</h3>
        <div class=\"report-detail-meta\">${escapeHtml(error?.message || "No se pudo cargar el detalle.")}</div>
      </div>
    `;
  }
}
function renderFlightsLayer(payload) {
  if (!map) return;
  clearFlightsLayer();
  clearFlightsTrack();
  flightsLayerGroup = L.layerGroup();

  const points = Array.isArray(payload?.points) ? payload.points : [];
  points.forEach((item) => {
    const lat = Number(item?.latitude);
    const lng = Number(item?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const cached = resolveFlightDetailCache(item);
    const popupData =
      cached?.detailPayload || cached?.trackPayload
        ? buildFlightPopupData(item, cached.detailPayload, cached.trackPayload)
        : item;
    const marker = L.marker([lat, lng], {
      icon: buildFlightsMarkerIcon(item?.heading),
      title: item?.call_sign || item?.registration || "Vuelo",
    });
    marker.bindPopup(flightsPopupHtml(popupData), MAP_POPUP_OPTIONS);
    marker.on("click", () => {
      ensureContextPanelVisible({ mobileState: "full" });
      showFlightDetail(item, marker);
    });
    marker.addTo(flightsLayerGroup);
  });

  flightsLayerGroup.addTo(map);
}

async function refreshFlightsLayer() {
  if (activeBaseMode !== "flights") return;
  try {
    const payload = await fetchFlightsLayerData();
    flightsLastPayload = payload;
    renderFlightsLayer(payload);
    renderFlightsSummary(payload);
    renderFlightsAirportsList(payload);
  } catch (_error) {
    if (!flightsLastPayload) {
      clearFlightsLayer();
      clearFlightsTrack();
    }
    renderFlightsSummary(flightsLastPayload, "No fue posible actualizar la capa de vuelos.");
    renderFlightsAirportsList(flightsLastPayload);
  }
}

async function enableFlightsMode() {
  if (!isAdmin) return;
  activeBaseMode = "flights";
  cleanupFlightsPhotoModal();
  flightsDetailRequestSeq += 1;
  clearMarkers();
  closeActivePopup();
  selectedReportId = null;
  renderReportDetail(null);
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(true);
  ensureContextPanelVisible({ mobileState: "mid" });
  renderFlightsSummary(flightsLastPayload, "Cargando capa de vuelos...");
  renderFlightsAirportsList(flightsLastPayload);
  await refreshFlightsLayer();
  startFlightsPolling();
}

function disableFlightsMode() {
  if (activeBaseMode !== "flights") return;
  activeBaseMode = "map";
  cleanupFlightsPhotoModal();
  flightsDetailRequestSeq += 1;
  stopFlightsPolling();
  clearFlightsLayer();
  clearFlightsTrack();
  flightsLastPayload = null;
  setFlightsOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
}

function clearProtestLayer() {
  if (protestLayerGroup && map) {
    map.removeLayer(protestLayerGroup);
  }
  protestLayerGroup = null;
}

function stopProtestPolling() {
  if (!protestRefreshTimer) return;
  clearInterval(protestRefreshTimer);
  protestRefreshTimer = null;
}

function startProtestPolling() {
  stopProtestPolling();
  const intervalMs = Math.max(30, Number(protestRefreshSeconds) || 300) * 1000;
  protestRefreshTimer = setInterval(() => {
    refreshProtestLayer();
  }, intervalMs);
}

function parseIsoDay(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const [year, month, day] = raw.split("-").map((part) => Number(part));
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (Number.isNaN(date.getTime())) return null;
  return raw;
}

function dayToDateUtc(dayString) {
  const safe = parseIsoDay(dayString);
  if (!safe) return null;
  const [year, month, day] = safe.split("-").map((part) => Number(part));
  return new Date(Date.UTC(year, month - 1, day));
}

function formatDayUtc(dayString) {
  const date = dayToDateUtc(dayString);
  if (!date) return "N/D";
  return new Intl.DateTimeFormat("es-ES", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function formatDayCuba(dayString) {
  const date = dayToDateUtc(dayString);
  if (!date) return "N/D";
  return new Intl.DateTimeFormat("es-ES", {
    timeZone: "America/Havana",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function dayOffset(startDay, endDay) {
  const start = dayToDateUtc(startDay);
  const end = dayToDateUtc(endDay);
  if (!start || !end) return 0;
  const diff = Math.round((end.getTime() - start.getTime()) / 86400000);
  return Math.max(0, diff);
}

function dayByOffset(startDay, offset) {
  const start = dayToDateUtc(startDay);
  if (!start) return "";
  const numericOffset = Math.max(0, Number(offset) || 0);
  const date = new Date(start.getTime() + numericOffset * 86400000);
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getProtestColor(feature) {
  const eventType = feature?.properties?.event_type || "context_only";
  return (
    feature?.properties?.color ||
    PROTEST_EVENT_COLORS[eventType] ||
    PROTEST_EVENT_COLORS.context_only
  );
}

function createProtestCircleIcon(feature) {
  const color = getProtestColor(feature);
  return L.divIcon({
    className: "protest-marker-icon-wrap",
    html: `<span class="protest-marker-icon" style="--protest-marker-color:${color}"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -10],
  });
}

async function deleteProtestEntry(protestId, options = {}) {
  const safeId = Number(protestId);
  if (!Number.isFinite(safeId) || safeId <= 0) return false;

  const buttonEl = options.buttonEl || null;
  const noteEl = options.noteEl || null;
  if (buttonEl?.disabled) return false;
  if (!confirm("Eliminar esta protesta? Esta accion es permanente.")) return false;

  if (buttonEl) buttonEl.disabled = true;
  if (noteEl) {
    noteEl.textContent = "Eliminando protesta...";
    noteEl.classList.remove("is-error");
  }

  try {
    const response = await fetch(`/api/protests/${safeId}`, { method: "DELETE" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result?.ok) {
      throw new Error(result?.error || "No se pudo eliminar la protesta.");
    }
    protestSelectedFeatureId = null;
    await refreshProtestLayer({ force: true });
    return true;
  } catch (error) {
    if (noteEl) {
      noteEl.textContent = error?.message || "No se pudo eliminar la protesta.";
      noteEl.classList.add("is-error");
    }
    return false;
  } finally {
    if (buttonEl) buttonEl.disabled = false;
  }
}

function protestPopupHtml(feature) {
  const props = feature?.properties || {};
  const title = escapeHtml(props.title || "Evento");
  const eventLabel = escapeHtml(PROTEST_EVENT_LABELS[props.event_type] || "Evento");
  const confidence = Number(props.confidence_score);
  const confidenceLabel = Number.isFinite(confidence) ? `${confidence.toFixed(1)}%` : "N/D";
  const place = escapeHtml(
    props.matched_feature_name ||
      props.matched_place_text ||
      props.matched_municipality ||
      props.matched_province ||
      "Ubicacion no resuelta"
  );
  const sourceName = escapeHtml(props.source_name || "RSS");
  const sourceUrl = safeUrl(props.source_url || "");
  const published = props.source_published_at_utc
    ? escapeHtml(formatUtcAndCuba(props.source_published_at_utc))
    : "N/D";
  const protestId = Number(props.id);
  const canAdminDelete =
    Boolean(props.can_admin_delete) && Number.isFinite(protestId) && protestId > 0;
  const sourceLinkHtml = sourceUrl
    ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer">Ver publicacion original</a>`
    : "<span>Sin enlace fuente</span>";
  const adminActionsHtml = canAdminDelete
    ? `
      <div class="protest-popup-actions">
        <button type="button" class="protest-btn protest-btn-danger" data-protest-popup-delete-id="${protestId}">
          Eliminar protesta
        </button>
      </div>
      <div class="protest-popup-admin-note protest-detail-admin-note" data-protest-popup-admin-note></div>
    `
    : "";
  return `
    <div style="color:#111;max-width:280px;">
      <h3 style="margin:0 0 6px;">${title}</h3>
      <div style="font-size:12px;margin-bottom:4px;"><strong>${eventLabel}</strong> · Confianza ${confidenceLabel}</div>
      <div style="font-size:12px;margin-bottom:4px;">Lugar: ${place}</div>
      <div style="font-size:12px;margin-bottom:4px;">Fecha: ${published}</div>
      <div style="font-size:12px;margin-bottom:4px;">Fuente: ${sourceName}</div>
      <div style="font-size:12px;">${sourceLinkHtml}</div>
      ${adminActionsHtml}
    </div>
  `;
}

function attachProtestPopupActions(feature, popupElement) {
  if (!popupElement) return;
  const props = feature?.properties || {};
  const protestId = Number(props.id);
  const canAdminDelete =
    Boolean(props.can_admin_delete) && Number.isFinite(protestId) && protestId > 0;
  if (!canAdminDelete) return;

  const deleteBtn = popupElement.querySelector("[data-protest-popup-delete-id]");
  const adminNote = popupElement.querySelector("[data-protest-popup-admin-note]");
  if (!deleteBtn) return;

  deleteBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await deleteProtestEntry(protestId, {
      buttonEl: deleteBtn,
      noteEl: adminNote,
    });
  });
}

function renderProtestDetail(feature) {
  if (!protestDetailPanel) return;
  if (!feature) {
    protestDetailPanel.innerHTML =
      '<div class="protest-detail-empty">Haz clic en un evento para ver detalles y enlace original.</div>';
    return;
  }

  const props = feature.properties || {};
  const title = escapeHtml(props.title || "Evento");
  const eventLabel = escapeHtml(PROTEST_EVENT_LABELS[props.event_type] || "Evento");
  const confidence = Number(props.confidence_score);
  const confidenceLabel = Number.isFinite(confidence) ? `${confidence.toFixed(1)}%` : "N/D";
  const place = escapeHtml(
    props.matched_feature_name ||
      props.matched_place_text ||
      props.matched_municipality ||
      props.matched_province ||
      "Ubicacion no resuelta"
  );
  const sourceName = escapeHtml(props.source_name || "RSS");
  const sourceUrl = safeUrl(props.source_url || "");
  const sourceUrlLabel = escapeHtml(props.source_url || "");
  const protestId = Number(props.id);
  const canAdminDelete =
    Boolean(props.can_admin_delete) && Number.isFinite(protestId) && protestId > 0;
  const published = props.source_published_at_utc
    ? escapeHtml(formatUtcAndCuba(props.source_published_at_utc))
    : "N/D";

  const keywords = props.detected_keywords || {};
  const keywordList = []
    .concat(keywords.strong || [], keywords.context || [], keywords.weak || [])
    .filter((value, index, self) => value && self.indexOf(value) === index)
    .slice(0, 12)
    .map((value) => escapeHtml(value))
    .join(", ");

  const adminActionsHtml =
    canAdminDelete
      ? `
        <div class="protest-detail-actions">
          <button type="button" class="protest-btn protest-btn-danger" data-protest-delete-id="${protestId}">
            Eliminar protesta
          </button>
        </div>
        <div class="protest-detail-admin-note" data-protest-admin-note></div>
      `
      : "";

  protestDetailPanel.innerHTML = `
    <div class="protest-detail-title">${title}</div>
    <div class="protest-detail-meta">Tipo: ${eventLabel} · Confianza: ${confidenceLabel}</div>
    <div class="protest-detail-meta">Lugar detectado: ${place}</div>
    <div class="protest-detail-meta">Fecha: ${published}</div>
    <div class="protest-detail-meta">Fuente: ${sourceName}</div>
    <div class="protest-detail-meta">Palabras clave: ${keywordList || "N/D"}</div>
    ${
      sourceUrl
        ? `<a class="protest-detail-link" href="${sourceUrl}" target="_blank" rel="noopener noreferrer">${sourceUrlLabel}</a>`
        : '<div class="protest-detail-meta">Sin enlace fuente</div>'
    }
    ${adminActionsHtml}
  `;

  if (!canAdminDelete) return;
  const deleteBtn = protestDetailPanel.querySelector("[data-protest-delete-id]");
  const adminNote = protestDetailPanel.querySelector("[data-protest-admin-note]");
  if (!deleteBtn) return;

  deleteBtn.addEventListener("click", async () => {
    await deleteProtestEntry(protestId, {
      buttonEl: deleteBtn,
      noteEl: adminNote,
    });
  });
}

function renderProtestSummary(payload) {
  if (!protestSummary) return;
  const total = Number(payload?.features_total || 0);
  const mode = payload?.filters?.mode || "day";
  const selectedDay = payload?.timeline?.selected_day_utc;
  const selectedStart = payload?.timeline?.selected_start_day_utc;
  const selectedEnd = payload?.timeline?.selected_end_day_utc;
  if (mode === "range" && selectedStart && selectedEnd) {
    protestSummary.textContent = `Eventos en rango UTC ${selectedStart} -> ${selectedEnd}: ${total}`;
    return;
  }
  if (selectedDay) {
    protestSummary.textContent = `Eventos del dia UTC ${selectedDay}: ${total}`;
    return;
  }
  protestSummary.textContent = total
    ? `Eventos visibles en la vista activa: ${total}`
    : "Sin datos de protestas para la vista activa.";
}

function syncProtestTimelineControls(payload) {
  const timeline = payload?.timeline || {};
  protestTimelineStartDay = parseIsoDay(timeline.start_day_utc) || "";
  protestTimelineEndDay = parseIsoDay(timeline.end_day_utc) || protestTimelineStartDay;
  protestSelectedDay = parseIsoDay(timeline.selected_day_utc) || protestTimelineEndDay || protestTimelineStartDay;
  protestSelectedStartDay = parseIsoDay(timeline.selected_start_day_utc) || "";
  protestSelectedEndDay = parseIsoDay(timeline.selected_end_day_utc) || "";
  protestSelectedMode = payload?.filters?.mode || "day";

  if (protestTimelineSlider) {
    const max = dayOffset(protestTimelineStartDay, protestTimelineEndDay);
    protestTimelineSlider.min = "0";
    protestTimelineSlider.max = String(max);
    protestTimelineSlider.step = "1";
    const selectedOffset = dayOffset(protestTimelineStartDay, protestSelectedDay || protestTimelineEndDay);
    protestTimelineSlider.value = String(Math.min(max, Math.max(0, selectedOffset)));
    protestTimelineSlider.disabled = protestSelectedMode === "range";
  }

  if (protestDayInput && protestSelectedDay) {
    protestDayInput.value = protestSelectedDay;
  }
  if (protestStartInput) {
    protestStartInput.value = protestSelectedStartDay || "";
  }
  if (protestEndInput) {
    protestEndInput.value = protestSelectedEndDay || "";
  }

  if (protestTimelineLabel) {
    if (protestSelectedMode === "range" && protestSelectedStartDay && protestSelectedEndDay) {
      protestTimelineLabel.textContent = `Rango UTC ${formatDayUtc(protestSelectedStartDay)} -> ${formatDayUtc(
        protestSelectedEndDay
      )} (Cuba ${formatDayCuba(protestSelectedStartDay)} -> ${formatDayCuba(protestSelectedEndDay)})`;
    } else if (protestSelectedDay) {
      protestTimelineLabel.textContent = `Dia seleccionado UTC ${formatDayUtc(
        protestSelectedDay
      )} (Cuba ${formatDayCuba(protestSelectedDay)})`;
    } else {
      protestTimelineLabel.textContent = "Sin datos historicos.";
    }
  }
}

function renderProtestData(payload) {
  if (!map) return;
  clearProtestLayer();
  const features = Array.isArray(payload?.features) ? payload.features : [];
  if (!features.length) {
    renderProtestDetail(null);
    return;
  }

  protestLayerGroup = L.layerGroup();
  let selectedFeature = null;
  features.forEach((feature) => {
    const coords = feature?.geometry?.coordinates;
    if (!Array.isArray(coords) || coords.length < 2) return;
    const lat = Number(coords[1]);
    const lng = Number(coords[0]);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const featureId = Number(feature?.properties?.id);
    const isSelected = Number.isFinite(featureId) && featureId === protestSelectedFeatureId;
    const marker = L.marker([lat, lng], {
      title: feature?.properties?.title || "Protesta",
      icon: createProtestCircleIcon(feature),
    });
    marker.bindTooltip(
      `${feature?.properties?.title || "Evento"} · ${
        PROTEST_EVENT_LABELS[feature?.properties?.event_type] || "Evento"
      }`,
      {
        direction: "top",
        sticky: true,
      }
    );
    marker.on("click", () => {
      protestSelectedFeatureId = Number(feature?.properties?.id) || null;
      renderProtestDetail(feature);
      ensureContextPanelVisible({ mobileState: "full" });
    });
    marker.addTo(protestLayerGroup);
    if (isSelected) {
      selectedFeature = feature;
    }
  });
  protestLayerGroup.addTo(map);

  if (selectedFeature) {
    renderProtestDetail(selectedFeature);
  } else {
    protestSelectedFeatureId = null;
    renderProtestDetail(null);
  }
}

async function fetchProtestData() {
  const params = new URLSearchParams();
  if (protestSelectedMode === "range" && protestSelectedStartDay && protestSelectedEndDay) {
    params.set("start", protestSelectedStartDay);
    params.set("end", protestSelectedEndDay);
  } else {
    const day = parseIsoDay(protestSelectedDay) || "";
    if (day) params.set("day", day);
  }
  const url = params.toString() ? `/api/protests/geojson?${params}` : "/api/protests/geojson";
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("No se pudo cargar la capa de protestas");
  return await response.json();
}

async function refreshProtestLayer(options = {}) {
  const force = Boolean(options && options.force);
  if (activeBaseMode !== "protests") return;
  if (protestRefreshPromise) {
    if (!force) return protestRefreshPromise;
    try {
      await protestRefreshPromise;
    } catch (_error) {
      // ignore and force a new attempt below
    }
  }

  protestRefreshPromise = (async () => {
    try {
      const payload = await fetchProtestData();
      protestLastPayload = payload;
      syncProtestTimelineControls(payload);
      renderProtestSummary(payload);
      renderProtestData(payload);
    } catch (err) {
      if (protestSummary) {
        if (protestLastPayload && Array.isArray(protestLastPayload.features)) {
          protestSummary.textContent =
            "Actualizacion temporal fallida. Mostrando la ultima capa disponible.";
        } else {
          protestSummary.textContent = "No fue posible actualizar la capa Protestas.";
        }
      }
      if (!protestLastPayload || !Array.isArray(protestLastPayload.features)) {
        renderProtestDetail(null);
        clearProtestLayer();
      }
    }
  })();

  try {
    return await protestRefreshPromise;
  } finally {
    protestRefreshPromise = null;
  }
}

async function enableProtestMode() {
  activeBaseMode = "protests";
  clearMarkers();
  closeActivePopup();
  renderReportDetail(null);
  setMapHintVisible(false);
  setReportLegendVisible(false);
  setReportDetailVisible(false);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(true);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  ensureContextPanelVisible({ mobileState: "mid" });
  await refreshProtestLayer();
  startProtestPolling();
}

function disableProtestMode() {
  if (activeBaseMode !== "protests") return;
  activeBaseMode = "map";
  stopProtestPolling();
  clearProtestLayer();
  protestLastPayload = null;
  protestSelectedFeatureId = null;
  protestSelectedMode = "day";
  protestSelectedStartDay = "";
  protestSelectedEndDay = "";
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
  renderProtestDetail(null);
}

async function applyFilters() {
  if (
    activeBaseMode === "connectivity" ||
    activeBaseMode === "protests" ||
    activeBaseMode === "repressors" ||
    activeBaseMode === "prisoners" ||
    activeBaseMode === "ais" ||
    activeBaseMode === "flights"
  ) {
    clearMarkers();
    updateLegendCounts(allPosts);
    return;
  }

  const { province, municipality } = getSelectedLocationFilters();
  let filtered = Array.isArray(allPosts) ? [...allPosts] : [];

  if (selectedLegendCategory !== "all") {
    const categoryId = Number(selectedLegendCategory);
    if (Number.isFinite(categoryId)) {
      filtered = filtered.filter((post) => Number(post.category?.id) === categoryId);
    }
  }

  if (province) {
    filtered = filtered.filter((post) => post.province === province);
  }
  if (municipality) {
    filtered = filtered.filter((post) => post.municipality === municipality);
  }

  updateLegendCounts(allPosts);
  renderMarkers(filtered);
}

async function loadAlerts() {
  const res = await fetch("/api/posts?limit=40", { cache: "no-store" });
  return await res.json();
}

function getAlertPosts(posts) {
  return (posts || []).filter((post) => isAlertCategory(post.category?.slug));
}

function isAlertPanelCollapsed() {
  return Boolean(alertConsolePanel && alertConsolePanel.classList.contains("is-collapsed"));
}

function renderAlertConsoleToggle() {
  if (!alertConsoleToggle) return;

  const collapsed = isAlertPanelCollapsed();
  const label = collapsed ? "Mostrar notificaciones" : "Ocultar notificaciones";
  const hasUnread = collapsed && alertConsoleUnreadCount > 0;
  const unreadText = alertConsoleUnreadCount > 99 ? "99+" : String(alertConsoleUnreadCount);

  if (alertConsoleToggleLabel) {
    alertConsoleToggleLabel.textContent = label;
  } else {
    alertConsoleToggle.textContent = label;
  }

  if (alertConsoleUnreadBadge) {
    alertConsoleUnreadBadge.textContent = unreadText;
    alertConsoleUnreadBadge.hidden = !hasUnread;
  }

  alertConsoleToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  if (hasUnread) {
    alertConsoleToggle.setAttribute(
      "aria-label",
      `${label}. ${alertConsoleUnreadCount} notificaciones nuevas`
    );
  } else {
    alertConsoleToggle.setAttribute("aria-label", label);
  }
}

function updateAlertUnreadCounter(posts) {
  const alerts = getAlertPosts(posts);
  const ids = alerts
    .map((post) => {
      if (!post || post.id === null || post.id === undefined) return "";
      return String(post.id);
    })
    .filter(Boolean);

  if (!alertsSnapshotReady) {
    ids.forEach((id) => knownAlertIds.add(id));
    alertsSnapshotReady = true;
    renderAlertConsoleToggle();
    return;
  }

  let newCount = 0;
  ids.forEach((id) => {
    if (!knownAlertIds.has(id)) {
      newCount += 1;
    }
    knownAlertIds.add(id);
  });

  if (newCount > 0 && isAlertPanelCollapsed()) {
    alertConsoleUnreadCount += newCount;
  }

  renderAlertConsoleToggle();
}

function renderAlerts(posts) {
  const container = document.getElementById("alertFeed");
  if (!container) return;

  const alerts = getAlertPosts(posts);
  if (!alerts.length) {
    container.innerHTML = `<div class="console-empty">Sin movimientos, desconexiones o acciones recientes.</div>`;
    return;
  }

  container.innerHTML = alerts
    .slice(0, 8)
    .map((post) => {
      const safeTitle = escapeHtml(post.title || "");
      const safeCategory = escapeHtml(post.category?.name || "");
      const safeProvince = escapeHtml(post.province || "N/D");
      const safeMunicipality = escapeHtml(post.municipality || "N/D");
      const locationText = `${safeProvince} · ${safeMunicipality}`;
      const eventTime = post.movement_at || post.created_at;
      const timeText = eventTime ? new Date(eventTime).toLocaleString("es-ES") : "";
      return `
        <div class="console-item">
          <div>
            <button
              class="console-title-row console-link"
              type="button"
              data-post-id="${post.id}"
              data-detail-url="/reporte/${post.id}"
            >${safeTitle}</button>
            <div class="console-meta">${safeCategory}</div>
            <div class="console-meta">${locationText}</div>
          </div>
          <div class="console-side">
            <div class="console-time">${timeText}</div>
          </div>
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".console-link").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const postId = Number(btn.getAttribute("data-post-id"));
      const post = Number.isFinite(postId)
        ? allPosts.find((row) => Number(row.id) === postId)
        : null;
      if (post && map) {
        await ensureMapModeForReportFocus();
        openPostOnMap(post);
        return;
      }
      const url = btn.getAttribute("data-detail-url");
      if (!url) return;
      if (window.openReportModal) {
        window.openReportModal(url);
      } else {
        window.location.href = url;
      }
    });
  });
}

async function refreshAlerts() {
  try {
    const posts = await loadAlerts();
    updateAlertUnreadCounter(posts);
    renderAlerts(posts);
  } catch (err) {
    // no-op
  }
}

function setupAlertConsoleToggle() {
  alertConsolePanel = document.getElementById("alertConsolePanel");
  alertConsoleToggle = document.getElementById("alertConsoleToggle");
  alertConsoleToggleLabel = document.getElementById("alertConsoleToggleLabel");
  alertConsoleUnreadBadge = document.getElementById("alertConsoleUnreadBadge");
  if (!alertConsolePanel || !alertConsoleToggle) return;

  const setCollapsed = (collapsed, options = {}) => {
    const persist = options.persist === true;
    alertConsolePanel.classList.toggle("is-collapsed", collapsed);
    if (!collapsed) {
      alertConsoleUnreadCount = 0;
    }
    if (persist) {
      persistAlertPanelCollapsed(collapsed);
    }
    renderAlertConsoleToggle();
  };

  alertConsoleToggle.addEventListener("click", () => {
    const collapsed = !alertConsolePanel.classList.contains("is-collapsed");
    setCollapsed(collapsed, { persist: true });
  });

  const initialCollapsed = isAlertPanelHiddenByCookie() ? true : isMobileViewport();
  setCollapsed(initialCollapsed);
}

function parseNominatimResult(item, fallbackLabel) {
  if (!item) return null;
  const lat = Number(item.lat);
  const lng = Number(item.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (!isWithinCubaBounds({ lat, lng })) return null;

  return {
    lat,
    lng,
    label: item.display_name || fallbackLabel || `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
  };
}

async function searchSuggestionsInCuba(query, limit = 5, offset = 0) {
  const q = String(query || "").trim();
  if (!q) return [];

  const size = Math.max(parseInt(limit, 10) || 5, 1);
  const start = Math.max(parseInt(offset, 10) || 0, 0);
  const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&accept-language=es&limit=${size}&offset=${start}&countrycodes=cu&q=${encodeURIComponent(
    q
  )}`;
  const res = await fetch(url, {
    headers: {
      Accept: "application/json",
    },
  });
  if (!res.ok) return [];
  const data = await res.json();
  if (!Array.isArray(data) || !data.length) return [];

  const results = [];
  data.forEach((item) => {
    const parsed = parseNominatimResult(item, q);
    if (!parsed) return;
    results.push(parsed);
  });

  return results;
}

async function searchInCuba(query) {
  const matches = await searchSuggestionsInCuba(query, 5);
  return matches[0] || null;
}

function focusSearchResult(result) {
  if (!map || !result) return;
  map.setView([result.lat, result.lng], Math.max(map.getZoom(), 16));

  if (searchMarker) {
    searchMarker.remove();
  }

  searchMarker = L.marker([result.lat, result.lng], {
    title: result.label || "Busqueda",
  }).addTo(map);
}

function setupMapSearchAutocomplete(searchInput) {
  if (!searchInput) return;
  const searchBar = searchInput.closest(".map-search-bar");
  if (!searchBar) return;

  const SEARCH_BATCH_SIZE = 6;
  const SCROLL_NEAR_BOTTOM_PX = 18;
  let suggestions = [];
  let activeIndex = -1;
  let debounceTimer = null;
  let requestToken = 0;
  let currentQuery = "";
  let nextOffset = 0;
  let isLoadingMore = false;
  let canLoadMore = false;
  let seenSuggestionKeys = new Set();
  let touchStartY = null;

  let dropdown = searchBar.querySelector(".map-search-suggestions");
  if (!dropdown) {
    dropdown = document.createElement("div");
    dropdown.className = "map-search-suggestions";
    dropdown.id = "mapSearchSuggestions";
    dropdown.setAttribute("role", "listbox");
    dropdown.hidden = true;
    searchBar.appendChild(dropdown);
  }

  searchInput.setAttribute("autocomplete", "off");
  searchInput.setAttribute("role", "combobox");
  searchInput.setAttribute("aria-autocomplete", "list");
  searchInput.setAttribute("aria-controls", dropdown.id);
  searchInput.setAttribute("aria-expanded", "false");

  const closeDropdown = () => {
    dropdown.hidden = true;
    dropdown.innerHTML = "";
    activeIndex = -1;
    searchInput.setAttribute("aria-expanded", "false");
  };

  const suggestionKey = (entry) => {
    if (!entry) return "";
    const lat = Number(entry.lat);
    const lng = Number(entry.lng);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return `${lat.toFixed(6)},${lng.toFixed(6)}`;
    }
    return String(entry.label || "");
  };

  const isNearDropdownBottom = () => {
    return dropdown.scrollTop + dropdown.clientHeight >= dropdown.scrollHeight - SCROLL_NEAR_BOTTOM_PX;
  };

  const refreshActiveItem = () => {
    const items = dropdown.querySelectorAll(".map-search-suggestion");
    items.forEach((item, idx) => {
      const isActive = idx === activeIndex;
      item.classList.toggle("is-active", isActive);
      item.setAttribute("aria-selected", isActive ? "true" : "false");
      if (isActive) {
        item.scrollIntoView({ block: "nearest" });
      }
    });
  };

  const selectSuggestion = (entry) => {
    if (!entry) return;
    searchInput.value = entry.label || searchInput.value;
    closeDropdown();
    focusSearchResult(entry);
  };

  const renderDropdown = ({ replace = true, appendFrom = 0 } = {}) => {
    if (!suggestions.length) {
      closeDropdown();
      return;
    }

    if (replace) {
      dropdown.innerHTML = "";
      appendFrom = 0;
    }

    const fragment = document.createDocumentFragment();
    for (let idx = appendFrom; idx < suggestions.length; idx += 1) {
      const entry = suggestions[idx];
      const item = document.createElement("button");
      item.type = "button";
      item.className = "map-search-suggestion";
      item.setAttribute("role", "option");
      item.setAttribute("data-idx", String(idx));
      item.setAttribute("aria-selected", idx === activeIndex ? "true" : "false");
      item.textContent = entry.label || "";
      if (!replace) {
        item.classList.add("is-revealing");
        item.addEventListener(
          "animationend",
          () => {
            item.classList.remove("is-revealing");
          },
          { once: true }
        );
      }
      item.addEventListener("mousedown", (event) => {
        event.preventDefault();
      });
      item.addEventListener("click", () => {
        const parsed = parseInt(item.getAttribute("data-idx"), 10);
        if (Number.isNaN(parsed)) return;
        selectSuggestion(suggestions[parsed]);
      });
      fragment.appendChild(item);
    }
    dropdown.appendChild(fragment);
    dropdown.hidden = false;
    searchInput.setAttribute("aria-expanded", "true");
    refreshActiveItem();
  };

  const loadMoreSuggestions = async () => {
    if (!canLoadMore || isLoadingMore) return;
    const query = searchInput.value.trim();
    if (query.length < 3) return;
    if (query !== currentQuery) return;

    isLoadingMore = true;
    const offset = nextOffset;
    const token = ++requestToken;

    try {
      const found = await searchSuggestionsInCuba(query, SEARCH_BATCH_SIZE, offset);
      if (token !== requestToken) return;
      nextOffset += SEARCH_BATCH_SIZE;

      const previousCount = suggestions.length;
      found.forEach((entry) => {
        const key = suggestionKey(entry);
        if (!key || seenSuggestionKeys.has(key)) return;
        seenSuggestionKeys.add(key);
        suggestions.push(entry);
      });

      const addedCount = suggestions.length - previousCount;
      if (addedCount > 0) {
        if (activeIndex < 0) activeIndex = 0;
        renderDropdown({ replace: false, appendFrom: previousCount });
      }

      canLoadMore = found.length === SEARCH_BATCH_SIZE;
    } catch (err) {
      if (token !== requestToken) return;
      canLoadMore = false;
    } finally {
      isLoadingMore = false;
    }
  };

  const runSearch = async () => {
    const query = searchInput.value.trim();
    if (query.length < 3) {
      suggestions = [];
      currentQuery = "";
      nextOffset = 0;
      canLoadMore = false;
      isLoadingMore = false;
      seenSuggestionKeys = new Set();
      closeDropdown();
      return;
    }

    const token = ++requestToken;
    try {
      const found = await searchSuggestionsInCuba(query, SEARCH_BATCH_SIZE, 0);
      if (token !== requestToken) return;
      seenSuggestionKeys = new Set();
      suggestions = [];
      found.forEach((entry) => {
        const key = suggestionKey(entry);
        if (!key || seenSuggestionKeys.has(key)) return;
        seenSuggestionKeys.add(key);
        suggestions.push(entry);
      });
      currentQuery = query;
      nextOffset = SEARCH_BATCH_SIZE;
      canLoadMore = found.length === SEARCH_BATCH_SIZE;
      isLoadingMore = false;
      activeIndex = suggestions.length ? 0 : -1;
      renderDropdown({ replace: true });
    } catch (err) {
      if (token !== requestToken) return;
      suggestions = [];
      currentQuery = "";
      nextOffset = 0;
      canLoadMore = false;
      isLoadingMore = false;
      seenSuggestionKeys = new Set();
      closeDropdown();
    }
  };

  dropdown.addEventListener("scroll", () => {
    if (dropdown.hidden) return;
    if (!canLoadMore || isLoadingMore) return;
    if (!isNearDropdownBottom()) return;
    loadMoreSuggestions();
  });

  dropdown.addEventListener(
    "wheel",
    (event) => {
      if (dropdown.hidden) return;
      if (!canLoadMore || isLoadingMore) return;
      if (event.deltaY <= 0) return;
      const noOverflow = dropdown.scrollHeight <= dropdown.clientHeight + 1;
      if (!noOverflow && !isNearDropdownBottom()) return;
      loadMoreSuggestions();
    },
    { passive: true }
  );

  dropdown.addEventListener(
    "touchstart",
    (event) => {
      if (!event.touches || !event.touches.length) return;
      touchStartY = event.touches[0].clientY;
    },
    { passive: true }
  );

  dropdown.addEventListener(
    "touchmove",
    (event) => {
      if (dropdown.hidden) return;
      if (!canLoadMore || isLoadingMore) return;
      if (!event.touches || !event.touches.length || touchStartY === null) return;
      const deltaY = touchStartY - event.touches[0].clientY;
      if (deltaY <= 6) return;
      const noOverflow = dropdown.scrollHeight <= dropdown.clientHeight + 1;
      if (!noOverflow && !isNearDropdownBottom()) return;
      loadMoreSuggestions();
    },
    { passive: true }
  );

  dropdown.addEventListener(
    "touchend",
    () => {
      touchStartY = null;
    },
    { passive: true }
  );

  searchInput.addEventListener("input", () => {
    if (debounceTimer) window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(runSearch, 240);
  });

  searchInput.addEventListener("focus", () => {
    if (suggestions.length) {
      dropdown.hidden = false;
      searchInput.setAttribute("aria-expanded", "true");
      refreshActiveItem();
    }
  });

  searchInput.addEventListener("keydown", async (event) => {
    if (event.key === "ArrowDown") {
      if (!suggestions.length) return;
      event.preventDefault();
      activeIndex = (activeIndex + 1) % suggestions.length;
      refreshActiveItem();
      return;
    }
    if (event.key === "ArrowUp") {
      if (!suggestions.length) return;
      event.preventDefault();
      activeIndex = activeIndex <= 0 ? suggestions.length - 1 : activeIndex - 1;
      refreshActiveItem();
      return;
    }
    if (event.key === "Escape") {
      if (dropdown.hidden) return;
      event.preventDefault();
      suggestions = [];
      closeDropdown();
      return;
    }
    if (event.key !== "Enter") return;

    event.preventDefault();
    if (suggestions.length && activeIndex >= 0) {
      selectSuggestion(suggestions[activeIndex]);
      return;
    }

    const query = searchInput.value.trim();
    if (!query) return;
    const found = await searchInCuba(query);
    if (!found) return;
    selectSuggestion(found);
  });

  document.addEventListener("click", (event) => {
    if (searchBar.contains(event.target)) return;
    suggestions = [];
    closeDropdown();
  });
}

async function initMap() {
  setupMapImageModal();
  syncLegend();
  setupAlertConsoleToggle();

  const mapEl = document.getElementById("map");
  if (!mapEl || typeof L === "undefined") {
    refreshAlerts();
    return;
  }

  isAdmin = mapEl.dataset.isAdmin === "1";
  connectivityRefreshSeconds = Number(mapEl.dataset.connectivityRefreshSeconds || 300);
  protestRefreshSeconds = Number(mapEl.dataset.protestRefreshSeconds || 300);
  aisRefreshSeconds = Number(mapEl.dataset.aisRefreshSeconds || 1800);
  flightsRefreshSeconds = Number(mapEl.dataset.flightsRefreshSeconds || 300);
  const preferredProvider = (mapEl.dataset.mapProvider || MAP_PROVIDER_LEAFLET).toLowerCase();
  mapLayerRouteTemplate = String(mapEl.dataset.layerRouteTemplate || "/map=__layer__").trim();
  const requestedBaseModeRaw = normalizeBaseMode(
    mapEl.dataset.initialBaseMode || parseBaseModeFromPath(window.location.pathname)
  );
  const requestedBaseMode =
    !isAdmin && (requestedBaseModeRaw === "ais" || requestedBaseModeRaw === "flights")
      ? "map"
      : requestedBaseModeRaw;
  mapHintElement = document.getElementById("mapHint");
  reportLegendSection = document.getElementById("reportLegendSection");
  connectivityLegendOverlay = document.getElementById("connectivityLegendOverlay");
  connectivityUpdatedLabel = document.getElementById("connectivityUpdatedLabel");
  connectivityTrafficPanel = document.getElementById("connectivityTrafficPanel");
  connectivityTrafficValue = document.getElementById("connectivityTrafficValue");
  connectivityTrafficDelta = document.getElementById("connectivityTrafficDelta");
  connectivityTrafficDrop = document.getElementById("connectivityTrafficDrop");
  connectivityTrafficNote = document.getElementById("connectivityTrafficNote");
  connectivitySparkMain = document.getElementById("connectivitySparkMain");
  connectivitySparkPrev = document.getElementById("connectivitySparkPrev");
  connectivityProvincePanel = document.getElementById("connectivityProvincePanel");
  connectivityProvinceTitle = document.getElementById("connectivityProvinceTitle");
  connectivityProvinceStatus = document.getElementById("connectivityProvinceStatus");
  connectivityProvinceRange = document.getElementById("connectivityProvinceRange");
  connectivityProvinceChartMain = document.getElementById("connectivityProvinceChartMain");
  connectivityProvinceChartPrev = document.getElementById("connectivityProvinceChartPrev");
  connectivityProvinceLog = document.getElementById("connectivityProvinceLog");
  connectivityRegionPanel = document.getElementById("connectivityRegionPanel");
  connectivityRegionChart = document.getElementById("connectivityRegionChart");
  connectivityRegionLegend = document.getElementById("connectivityRegionLegend");
  connectivityRegionNote = document.getElementById("connectivityRegionNote");
  connectivityAlertPanel = document.getElementById("connectivityAlertPanel");
  connectivityAlertBadge = document.getElementById("connectivityAlertBadge");
  connectivityAlertCopy = document.getElementById("connectivityAlertCopy");
  connectivityAlertList = document.getElementById("connectivityAlertList");
  connectivityQualityPanel = document.getElementById("connectivityQualityPanel");
  connectivityQualityDownloadValue = document.getElementById("connectivityQualityDownloadValue");
  connectivityQualityDownloadMeta = document.getElementById("connectivityQualityDownloadMeta");
  connectivityQualityLatencyValue = document.getElementById("connectivityQualityLatencyValue");
  connectivityQualityLatencyMeta = document.getElementById("connectivityQualityLatencyMeta");
  connectivityQualityNote = document.getElementById("connectivityQualityNote");
  connectivityAudiencePanel = document.getElementById("connectivityAudiencePanel");
  connectivityAudienceMobileBar = document.getElementById("connectivityAudienceMobileBar");
  connectivityAudienceDesktopBar = document.getElementById("connectivityAudienceDesktopBar");
  connectivityAudienceHumanBar = document.getElementById("connectivityAudienceHumanBar");
  connectivityAudienceBotBar = document.getElementById("connectivityAudienceBotBar");
  connectivityAudienceMobileValue = document.getElementById("connectivityAudienceMobileValue");
  connectivityAudienceDesktopValue = document.getElementById("connectivityAudienceDesktopValue");
  connectivityAudienceHumanValue = document.getElementById("connectivityAudienceHumanValue");
  connectivityAudienceBotValue = document.getElementById("connectivityAudienceBotValue");
  connectivityAudienceNote = document.getElementById("connectivityAudienceNote");
  connectivityWindowButtons = Array.from(
    document.querySelectorAll("[data-connectivity-window-hours]")
  );
  protestOverlay = document.getElementById("protestOverlay");
  protestTimelineSlider = document.getElementById("protestTimelineSlider");
  protestTimelineLabel = document.getElementById("protestTimelineLabel");
  protestDayInput = document.getElementById("protestDayInput");
  protestStartInput = document.getElementById("protestStartInput");
  protestEndInput = document.getElementById("protestEndInput");
  protestApplyDayBtn = document.getElementById("protestApplyDayBtn");
  protestApplyRangeBtn = document.getElementById("protestApplyRangeBtn");
  protestResetRangeBtn = document.getElementById("protestResetRangeBtn");
  protestSummary = document.getElementById("protestSummary");
  protestDetailPanel = document.getElementById("protestDetailPanel");
  repressorOverlay = document.getElementById("repressorOverlay");
  repressorSummary = document.getElementById("repressorSummary");
  repressorStatsPanel = document.getElementById("repressorStatsPanel");
  prisonerOverlay = document.getElementById("prisonerOverlay");
  prisonerSummary = document.getElementById("prisonerSummary");
  prisonerStatsPanel = document.getElementById("prisonerStatsPanel");
  prisonerProvinceFilter = document.getElementById("prisonerProvinceFilter");
  prisonerMunicipalityFilter = document.getElementById("prisonerMunicipalityFilter");
  prisonerPrisonFilter = document.getElementById("prisonerPrisonFilter");
  aisOverlay = document.getElementById("aisOverlay");
  aisSummary = document.getElementById("aisSummary");
  aisPortList = document.getElementById("aisPortList");
  flightsOverlay = document.getElementById("flightsOverlay");
  flightsSummary = document.getElementById("flightsSummary");
  flightsMeta = document.getElementById("flightsMeta");
  flightsAirportsList = document.getElementById("flightsAirportsList");
  flightsWindowButtons = Array.from(document.querySelectorAll("[data-flights-window-hours]"));
  reportDetailPanel = document.getElementById("reportDetailPanel");
  setActiveConnectivityWindow(connectivityWindowHours);
  setActiveFlightsWindow(flightsWindowHours);
  renderReportDetail(null);
  renderConnectivityRegionChart(null);
  renderConnectivityRadarPanels(null);
  renderProtestDetail(null);
  renderRepressorStats(null, "Selecciona la capa de represores para cargar el gráfico.");
  renderPrisonerStats(null, "Selecciona la capa de prisioneros para cargar el gráfico.");
  setReportDetailVisible(true);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);

  const nowUtc = new Date();
  const currentDayUtc = `${nowUtc.getUTCFullYear()}-${String(nowUtc.getUTCMonth() + 1).padStart(
    2,
    "0"
  )}-${String(nowUtc.getUTCDate()).padStart(2, "0")}`;
  protestSelectedDay = currentDayUtc;
  if (protestDayInput) protestDayInput.value = currentDayUtc;

  connectivityWindowButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const hours = Number(button.dataset.connectivityWindowHours);
      if (![2, 6, 24].includes(hours)) return;
      const changed = hours !== connectivityWindowHours;
      setActiveConnectivityWindow(hours);
      if (!changed) return;
      connectivityLastRenderKey = null;
      if (activeBaseMode === "connectivity") {
        await refreshConnectivityLayer();
      }
    });
  });

  flightsWindowButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const hours = Number(button.dataset.flightsWindowHours);
      if (!FLIGHTS_WINDOW_OPTIONS.includes(hours)) return;
      const changed = hours !== flightsWindowHours;
      setActiveFlightsWindow(hours);
      if (!changed) return;
      if (activeBaseMode === "flights") {
        await refreshFlightsLayer();
      }
    });
  });

  if (protestTimelineSlider) {
    protestTimelineSlider.addEventListener("change", async () => {
      if (!protestTimelineStartDay) return;
      const nextDay = dayByOffset(protestTimelineStartDay, protestTimelineSlider.value);
      if (!nextDay) return;
      protestSelectedMode = "day";
      protestSelectedStartDay = "";
      protestSelectedEndDay = "";
      protestSelectedDay = nextDay;
      if (protestDayInput) protestDayInput.value = nextDay;
      if (activeBaseMode === "protests") {
        await refreshProtestLayer();
      } else if (protestTimelineLabel) {
        protestTimelineLabel.textContent = `Dia seleccionado UTC ${formatDayUtc(
          nextDay
        )} (Cuba ${formatDayCuba(nextDay)})`;
      }
    });
  }

  if (protestApplyDayBtn) {
    protestApplyDayBtn.addEventListener("click", async () => {
      const nextDay = parseIsoDay(protestDayInput?.value);
      if (!nextDay) return;
      protestSelectedMode = "day";
      protestSelectedStartDay = "";
      protestSelectedEndDay = "";
      protestSelectedDay = nextDay;
      if (activeBaseMode === "protests") {
        await refreshProtestLayer();
      }
    });
  }

  if (protestApplyRangeBtn) {
    protestApplyRangeBtn.addEventListener("click", async () => {
      const start = parseIsoDay(protestStartInput?.value);
      const end = parseIsoDay(protestEndInput?.value);
      if (!start || !end) return;
      protestSelectedMode = "range";
      protestSelectedStartDay = start;
      protestSelectedEndDay = end;
      if (activeBaseMode === "protests") {
        await refreshProtestLayer();
      }
    });
  }

  if (protestResetRangeBtn) {
    protestResetRangeBtn.addEventListener("click", async () => {
      protestSelectedMode = "day";
      protestSelectedStartDay = "";
      protestSelectedEndDay = "";
      protestSelectedDay = currentDayUtc;
      if (protestDayInput) protestDayInput.value = currentDayUtc;
      if (protestStartInput) protestStartInput.value = "";
      if (protestEndInput) protestEndInput.value = "";
      if (activeBaseMode === "protests") {
        await refreshProtestLayer();
      } else if (protestTimelineLabel) {
        protestTimelineLabel.textContent = `Dia seleccionado UTC ${formatDayUtc(
          currentDayUtc
        )} (Cuba ${formatDayCuba(currentDayUtc)})`;
      }
    });
  }

  map = L.map(mapEl, {
    zoomControl: true,
    minZoom: 4,
    maxZoom: 19,
  });
  disableMapNativeDragDrop(map);
  setupSidePanelScrollIsolation(map);
  const layerSet = buildMainBaseLayers(preferredProvider);
  const streetsLayer = layerSet.streetsLayer;
  const satelliteLayer = layerSet.satelliteLayer;
  const satelliteLabelsLayer = layerSet.satelliteLabelsLayer;
  const connectivityBaseLayer = layerSet.connectivityBaseLayer;
  const repressorBaseLayer = layerSet.repressorBaseLayer;
  const prisonerBaseLayer = layerSet.prisonerBaseLayer;
  const protestBaseLayer = layerSet.protestBaseLayer;
  const aisBaseLayer = layerSet.aisBaseLayer;
  const flightsBaseLayer = layerSet.flightsBaseLayer;
  mainBaseLayers = {
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    repressorBaseLayer,
    prisonerBaseLayer,
    protestBaseLayer,
    aisBaseLayer,
    flightsBaseLayer,
  };

  streetsLayer.addTo(map);
  const baseLayerOptions = {
    Mapa: streetsLayer,
    Satelite: satelliteLayer,
    Conectividad: connectivityBaseLayer,
    Represores: repressorBaseLayer,
    Prisioneros: prisonerBaseLayer,
    Protestas: protestBaseLayer,
  };
  if (isAdmin) {
    baseLayerOptions["Buques Cuba (beta)"] = aisBaseLayer;
    baseLayerOptions["Vuelos Cuba (beta)"] = flightsBaseLayer;
  }
  const layersControl = L.control.layers(baseLayerOptions, {}, { collapsed: true }).addTo(map);
  decorateMapLayersControl(layersControl);

  // Initialize marker cluster groups by category
  Object.keys(CATEGORY_ICONS).forEach((slug) => {
    const clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 80,
      disableClusteringAtZoom: 17,
      iconCreateFunction: function(cluster) {
        return createClusterIcon(cluster, slug);
      }
    });
    map.addLayer(clusterGroup);
    markerClustersByCategory[slug] = clusterGroup;
  });

  setMapHintVisible(true);
  setReportLegendVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  setRepressorOverlayVisible(false);
  setPrisonerOverlayVisible(false);
  setAISOverlayVisible(false);
  setFlightsOverlayVisible(false);

  map.on("baselayerchange", (event) => {
    const nextMode = modeForBaseLayer(event.layer);
    switchBaseMode(nextMode, { syncRoute: true }).catch(() => {
      // no-op
    });
  });

  const onMobileViewport = isMobileViewport();
  const cubaBounds = cubaLatLngBounds();
  map.fitBounds(cubaBounds, { padding: onMobileViewport ? [0, 0] : [16, 16] });
  if (onMobileViewport) {
    map.setView(HAVANA_CENTER, MOBILE_HAVANA_ZOOM);
  }
  applyMapPanBoundsForMode("map");

  const params = new URLSearchParams(window.location.search);
  const latParam = parseFloat(params.get("lat"));
  const lngParam = parseFloat(params.get("lng"));
  if (Number.isFinite(latParam) && Number.isFinite(lngParam)) {
    map.setView([latParam, lngParam], Math.max(map.getZoom(), 14));
    L.marker([latParam, lngParam], { title: "Ubicacion" }).addTo(map);
  }

  const searchInput = document.getElementById("mapSearch");
  if (searchInput) {
    setupMapSearchAutocomplete(searchInput);
  }

  setupLegendCategoryFilter();
  allPosts = await loadPosts();
  await applyFilters();
  if (requestedBaseMode !== "map") {
    await switchBaseMode(requestedBaseMode, { syncRoute: true, replaceRoute: true });
  }
  await refreshAlerts();

  window.addEventListener("popstate", () => {
    const routeMode = parseBaseModeFromPath(window.location.pathname);
    switchBaseMode(routeMode, { syncRoute: false }).catch(() => {
      // no-op
    });
  });

  const provinceSelect = document.getElementById("provinceFilter");
  const municipalitySelect = document.getElementById("municipalityFilter");
  const municipalities = window.CUBA_MUNICIPALITIES || {};

  const renderMunicipalities = (province, selected) => {
    if (!municipalitySelect) return;
    let items = [];
    if (province && municipalities[province]) {
      items = municipalities[province];
    } else {
      Object.values(municipalities).forEach((list) => {
        items = items.concat(list);
      });
      items = Array.from(new Set(items)).sort();
    }
    municipalitySelect.innerHTML =
      `<option value="">Todos</option>` +
      items.map((m) => `<option value="${m}" ${m === selected ? "selected" : ""}>${m}</option>`).join("");
  };

  if (provinceSelect && municipalitySelect) {
    renderMunicipalities(provinceSelect.value, municipalitySelect.value);
    provinceSelect.addEventListener("change", () => {
      renderMunicipalities(provinceSelect.value, "");
      applyFilters();
    });
    municipalitySelect.addEventListener("change", applyFilters);
  }

  map.on("click", (event) => {
    if (
      activeBaseMode === "connectivity" ||
      activeBaseMode === "protests" ||
      activeBaseMode === "repressors" ||
      activeBaseMode === "prisoners" ||
      activeBaseMode === "ais" ||
      activeBaseMode === "flights"
    ) {
      closeActivePopup();
      return;
    }

    closeActivePopup();
    const lat = event.latlng.lat.toFixed(6);
    const lng = event.latlng.lng.toFixed(6);
    const newUrl = mapEl.dataset.newUrl;

    const popup = L.popup(MAP_POPUP_OPTIONS)
      .setLatLng(event.latlng)
      .setContent(`
        <div style="color:#111;max-width:240px;">
          <div style="font-weight:600;margin-bottom:8px;">Crear reporte aqui</div>
          <button type="button" data-create-report-btn style="background:#6ee7b7;border:none;padding:8px 10px;border-radius:6px;cursor:pointer;">Abrir formulario</button>
        </div>
      `)
      .openOn(map);

    activePopup = popup;

    const bindCreateReportButton = () => {
      const popupEl = popup.getElement();
      if (!popupEl) return false;
      L.DomEvent.disableClickPropagation(popupEl);
      const btn = popupEl.querySelector("[data-create-report-btn]");
      if (!btn) return false;
      if (btn.dataset.bound === "1") return true;
      btn.dataset.bound = "1";
      btn.addEventListener("click", (clickEvent) => {
        clickEvent.preventDefault();
        clickEvent.stopPropagation();
        const zoom = map ? map.getZoom() : "";
        const zoomParam = Number.isFinite(zoom) ? `&zoom=${zoom}` : "";
        const targetUrl = `${newUrl}?lat=${lat}&lng=${lng}${zoomParam}`;
        if (window.openReportModal) {
          window.openReportModal(targetUrl);
        } else {
          window.location.href = targetUrl;
        }
      });
      return true;
    };

    if (!bindCreateReportButton()) {
      requestAnimationFrame(bindCreateReportButton);
    }
  });

  syncMapShellHeight();

  if (alertTimer) {
    clearInterval(alertTimer);
  }
  alertTimer = setInterval(() => {
    refreshAlerts();
  }, 8000);
}
