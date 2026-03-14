(function () {
  const t = (key, vars = {}) => {
    let str = (window.TRANSLATIONS || {})[key] || key;
    Object.entries(vars).forEach(([k, v]) => {
      str = str.replaceAll(`{${k}}`, String(v));
    });
    return str;
  };

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
    toggle.textContent = t("status_alerts_unavailable");
    statusEl.textContent = t("status_notifications_disabled");
    statusEl.classList.add("is-muted");
    return;
  }

  if (!hasPushSupport) {
    toggle.disabled = true;
    toggle.textContent = t("button_install_pwa");
    if (isMobile) {
      statusEl.textContent = t("status_install_pwa_instructions");
    } else {
      statusEl.textContent = t("status_push_not_supported");
    }
    statusEl.classList.add("is-muted");
    return;
  }

  const setState = (state) => {
    if (state === "subscribed") {
      toggle.dataset.state = "on";
      toggle.textContent = t("button_disable_alerts");
      statusEl.textContent = t("status_alerts_active");
      return;
    }
    if (state === "blocked") {
      toggle.dataset.state = "blocked";
      toggle.disabled = true;
      toggle.textContent = t("button_alerts_blocked");
      statusEl.textContent = t("status_enable_browser_notifications");
      return;
    }
    toggle.dataset.state = "off";
    toggle.textContent = t("button_enable_alerts");
    statusEl.textContent = t("status_alert_categories");
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
      toggle.textContent = t("status_alerts_unavailable");
      statusEl.textContent = t("error_notification_service_init");
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
      statusEl.textContent = t("error_subscription_failed");
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
        statusEl.textContent = t("error_unsubscribe_failed");
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
