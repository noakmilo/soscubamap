(function () {
  const toggle = document.getElementById("alertPushToggle");
  const statusEl = document.getElementById("alertPushStatus");
  if (!toggle || !statusEl) return;

  const enabled = toggle.dataset.enabled === "1";
  const vapidKey = (toggle.dataset.vapidKey || "").trim();
  const ua = navigator.userAgent || "";
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (ua.includes("Mac") && navigator.maxTouchPoints > 1);
  const isAndroid = /Android/.test(ua);
  const isMobile = isIOS || isAndroid;

  const hasPushSupport = "serviceWorker" in navigator && "PushManager" in window;

  if (!enabled || !vapidKey) {
    toggle.disabled = true;
    toggle.textContent = "Alertas no disponibles";
    statusEl.textContent = "Notificaciones deshabilitadas en el servidor.";
    statusEl.classList.add("is-muted");
    return;
  }

  if (!hasPushSupport) {
    toggle.disabled = true;
    toggle.textContent = "Instala la PWA";
    if (isMobile) {
      statusEl.textContent =
        "Para activar alertas debes instalar la PWA. iOS: Compartir → Añadir a pantalla de inicio → abre desde el icono. Android: Menú ⋮ → Instalar app / Añadir a pantalla de inicio.";
    } else {
      statusEl.textContent = "Tu navegador no soporta notificaciones push.";
    }
    statusEl.classList.add("is-muted");
    return;
  }

  const setState = (state) => {
    if (state === "subscribed") {
      toggle.dataset.state = "on";
      toggle.textContent = "Desactivar alertas";
      statusEl.textContent = "Alertas activas para movimiento, desconexiones y acción represiva.";
      return;
    }
    if (state === "blocked") {
      toggle.dataset.state = "blocked";
      toggle.disabled = true;
      toggle.textContent = "Alertas bloqueadas";
      statusEl.textContent = "Activa las notificaciones en tu navegador para continuar.";
      return;
    }
    toggle.dataset.state = "off";
    toggle.textContent = "Activar alertas";
    statusEl.textContent = "Solo para movimiento, desconexiones y acción represiva.";
  };

  const urlBase64ToUint8Array = (base64String) => {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i += 1) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  };

  const registerWorker = async () => {
    return navigator.serviceWorker.register("/push-sw.js");
  };

  const syncState = async () => {
    try {
      const registration = await registerWorker();
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        setState("subscribed");
      } else if (Notification.permission === "denied") {
        setState("blocked");
      } else {
        setState("off");
      }
    } catch (err) {
      toggle.disabled = true;
      toggle.textContent = "Alertas no disponibles";
      statusEl.textContent = "No se pudo inicializar el servicio de notificaciones.";
      statusEl.classList.add("is-muted");
    }
  };

  const subscribe = async () => {
    let permission = Notification.permission;
    if (permission === "default") {
      permission = await Notification.requestPermission();
    }
    if (permission !== "granted") {
      setState("blocked");
      return;
    }

    const registration = await registerWorker();
    const existing = await registration.pushManager.getSubscription();
    const subscription =
      existing ||
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      }));

    try {
      await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(subscription.toJSON()),
      });
      setState("subscribed");
    } catch (err) {
      statusEl.textContent = "No se pudo registrar la suscripción.";
      statusEl.classList.add("is-muted");
    }
  };

  const unsubscribe = async () => {
    const registration = await registerWorker();
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      try {
        await fetch("/api/push/unsubscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
      } catch (err) {
        statusEl.textContent = "No se pudo desactivar la suscripción.";
        statusEl.classList.add("is-muted");
      }
      await subscription.unsubscribe();
    }
    setState("off");
  };

  toggle.addEventListener("click", async () => {
    if (toggle.dataset.state === "on") {
      await unsubscribe();
    } else {
      await subscribe();
    }
  });

  void syncState();
})();
