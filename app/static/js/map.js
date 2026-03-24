let map;
let markers = [];
let markerIndex = new Map();
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
let mapAppShell;
let mapSidePanel;
let mapSideScroll;
let mapPanelToggle;
let mapSheetHandle;
let selectedReportId = null;
let selectedLegendCategory = "all";
let mobileSheetState = "mid";
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
    const protestLayer = L.gridLayer.googleMutant({
      type: "roadmap",
      maxZoom: 20,
    });
    return {
      useGoogle,
      streetsLayer: mapLayer,
      satelliteLayer,
      satelliteLabelsLayer: null,
      connectivityBaseLayer: connectivityLayer,
      protestBaseLayer: protestLayer,
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
  const protestBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });
  return {
    useGoogle,
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    protestBaseLayer,
  };
}

function cubaLatLngBounds() {
  return L.latLngBounds(
    [CUBA_BOUNDS.south, CUBA_BOUNDS.west],
    [CUBA_BOUNDS.north, CUBA_BOUNDS.east]
  );
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

  const syncViewportLayout = () => {
    syncMapShellHeight();
    if (isMobileViewport()) {
      mapAppShell.classList.remove("is-panel-collapsed");
      setMobileSheetState(mobileSheetState || "mid");
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
  markers.forEach((marker) => marker.remove());
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

async function ensureMapModeForReportFocus() {
  if (!map || !mainBaseLayers?.streetsLayer) return;

  const {
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    protestBaseLayer,
  } = mainBaseLayers;

  if (activeBaseMode === "connectivity") {
    disableConnectivityMode();
  }
  if (activeBaseMode === "protests") {
    disableProtestMode();
  }

  [satelliteLayer, connectivityBaseLayer, protestBaseLayer].forEach((layer) => {
    if (layer && map.hasLayer(layer)) {
      map.removeLayer(layer);
    }
  });

  if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
    map.removeLayer(satelliteLabelsLayer);
  }

  if (!map.hasLayer(streetsLayer)) {
    streetsLayer.addTo(map);
  }

  activeBaseMode = "map";
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);
  await applyFilters();
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
  const repressorTypes = repressor && Array.isArray(repressor.types) ? repressor.types : [];
  const repressorCrimes = repressor && Array.isArray(repressor.crimes) ? repressor.crimes : [];
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
        post.links && post.links.length
          ? `<div class="report-detail-links">
               ${post.links
                 .map((link) => {
                   const href = safeUrl(link);
                   if (!href) return "";
                   const label = escapeHtml(link);
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
  reportDetailPanel.classList.remove("is-revealing");
  // Force reflow to restart the animation when selecting another report.
  void reportDetailPanel.offsetWidth;
  reportDetailPanel.classList.add("is-revealing");
}

function renderReportDetail(post, options = {}) {
  if (!reportDetailPanel) return;
  if (!post) {
    selectedReportId = null;
    reportDetailPanel.classList.remove("is-revealing");
    reportDetailPanel.innerHTML =
      '<div class="report-detail-empty">Haz click en un reporte para ver sus detalles.</div>';
    return;
  }

  selectedReportId = Number(post.id) || null;
  reportDetailPanel.innerHTML = reportDetailHtmlForPost(post);
  triggerReportDetailReveal();
  attachPopupActions(post, reportDetailPanel, null);
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

    const slug = post.category?.slug;
    const iconClass = CATEGORY_ICONS[slug] || "fa-location-dot";
    const imageUrl = CATEGORY_IMAGES[slug];

    const marker = L.marker([lat, lng], {
      title: post.title,
      icon: createMarkerIcon(iconClass, imageUrl, slug, false),
    }).addTo(map);

    marker.on("click", () => {
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
  if (activeBaseMode === "connectivity" || activeBaseMode === "protests") {
    if (Array.isArray(allPosts) && payload.status === "approved") {
      allPosts.unshift(payload);
    }
    updateLegendCounts(allPosts);
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
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
  updateConnectivityTrafficPanel(null);
  renderConnectivityProvincePanel(null);
  renderConnectivityRegionChart(null);
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
  setReportLegendVisible(true);
  setReportDetailVisible(true);
  setMapHintVisible(true);
  renderProtestDetail(null);
}

async function applyFilters() {
  if (activeBaseMode === "connectivity" || activeBaseMode === "protests") {
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
  const preferredProvider = (mapEl.dataset.mapProvider || MAP_PROVIDER_LEAFLET).toLowerCase();
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
  reportDetailPanel = document.getElementById("reportDetailPanel");
  setActiveConnectivityWindow(connectivityWindowHours);
  renderReportDetail(null);
  renderConnectivityRegionChart(null);
  renderProtestDetail(null);
  setReportDetailVisible(true);
  setProtestOverlayVisible(false);

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
  enableMiddleClickPan(map);
  const layerSet = buildMainBaseLayers(preferredProvider);
  const streetsLayer = layerSet.streetsLayer;
  const satelliteLayer = layerSet.satelliteLayer;
  const satelliteLabelsLayer = layerSet.satelliteLabelsLayer;
  const connectivityBaseLayer = layerSet.connectivityBaseLayer;
  const protestBaseLayer = layerSet.protestBaseLayer;
  mainBaseLayers = {
    streetsLayer,
    satelliteLayer,
    satelliteLabelsLayer,
    connectivityBaseLayer,
    protestBaseLayer,
  };

  streetsLayer.addTo(map);
  L.control
    .layers(
      {
        Mapa: streetsLayer,
        Satelite: satelliteLayer,
        Conectividad: connectivityBaseLayer,
        Protestas: protestBaseLayer,
      },
      {},
      { collapsed: true }
    )
    .addTo(map);
  setMapHintVisible(true);
  setReportLegendVisible(true);
  setConnectivityLegendVisible(false);
  setProtestOverlayVisible(false);

  map.on("baselayerchange", (event) => {
    if (event.layer === connectivityBaseLayer) {
      if (activeBaseMode === "protests") {
        disableProtestMode();
      }
      if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
        map.removeLayer(satelliteLabelsLayer);
      }
      enableConnectivityMode();
      return;
    }

    if (event.layer === protestBaseLayer) {
      if (activeBaseMode === "connectivity") {
        disableConnectivityMode();
      }
      if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
        map.removeLayer(satelliteLabelsLayer);
      }
      enableProtestMode();
      return;
    }

    if (activeBaseMode === "connectivity") {
      disableConnectivityMode();
    }
    if (activeBaseMode === "protests") {
      disableProtestMode();
    }

    activeBaseMode = event.layer === satelliteLayer ? "satellite" : "map";
    if (satelliteLabelsLayer && event.layer === satelliteLayer) {
      if (!map.hasLayer(satelliteLabelsLayer)) satelliteLabelsLayer.addTo(map);
    } else if (satelliteLabelsLayer && map.hasLayer(satelliteLabelsLayer)) {
      map.removeLayer(satelliteLabelsLayer);
    }

    applyFilters();
  });

  const onMobileViewport = isMobileViewport();
  const cubaBounds = cubaLatLngBounds();
  map.fitBounds(cubaBounds, { padding: onMobileViewport ? [0, 0] : [16, 16] });
  if (onMobileViewport) {
    map.setView(HAVANA_CENTER, MOBILE_HAVANA_ZOOM);
  }
  map.setMaxBounds(cubaBounds.pad(onMobileViewport ? 0.2 : 0.35));

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
  await refreshAlerts();

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
    if (activeBaseMode === "connectivity" || activeBaseMode === "protests") {
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
