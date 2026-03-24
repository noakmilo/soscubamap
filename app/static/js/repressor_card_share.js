(function () {
  const CARD_SELECTOR = "[data-repressor-card]";
  const DOWNLOAD_SELECTOR = "[data-repressor-download-btn]";
  const SHARE_SELECTOR = "[data-repressor-share-btn]";

  let html2CanvasPromise = null;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`No se pudo cargar script: ${src}`));
      document.head.appendChild(script);
    });
  }

  async function ensureHtml2Canvas() {
    if (window.html2canvas) return window.html2canvas;
    if (html2CanvasPromise) return html2CanvasPromise;

    html2CanvasPromise = (async () => {
      try {
        await loadScript("https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js");
      } catch (firstError) {
        await loadScript("https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js");
      }
      if (!window.html2canvas) {
        throw new Error("html2canvas no disponible");
      }
      return window.html2canvas;
    })();

    return html2CanvasPromise;
  }

  async function cardToPngBlob(card) {
    const html2canvas = await ensureHtml2Canvas();
    const canvas = await html2canvas(card, {
      backgroundColor: null,
      useCORS: true,
      allowTaint: false,
      scale: Math.max(2, window.devicePixelRatio || 1),
      logging: false,
    });
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("No se pudo generar PNG"));
            return;
          }
          resolve(blob);
        },
        "image/png",
        1.0
      );
    });
  }

  function sanitizeFileName(name) {
    const safe = String(name || "repressor")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9-_ ]+/g, "")
      .trim()
      .replace(/\s+/g, "_")
      .slice(0, 80);
    return safe || "repressor";
  }

  function triggerDownload(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function buildSharePayload(card) {
    const name = card.dataset.repressorName || "Represor";
    const typeText = card.dataset.repressorTypes || "N/D";
    const detailPath = card.dataset.repressorUrl || window.location.pathname;
    const detailUrl = new URL(detailPath, window.location.origin).toString();
    const shareText = `Identifica al represor\nNombre: ${name}\nTipo: ${typeText}`;
    return { name, typeText, detailUrl, shareText };
  }

  function openXIntent(shareText, detailUrl) {
    const intentUrl =
      "https://twitter.com/intent/tweet?text=" +
      encodeURIComponent(shareText) +
      "&url=" +
      encodeURIComponent(detailUrl);
    window.open(intentUrl, "_blank", "noopener,noreferrer");
  }

  async function handleDownload(event) {
    const card = event.currentTarget.closest(CARD_SELECTOR);
    if (!card) return;
    event.currentTarget.disabled = true;
    try {
      const blob = await cardToPngBlob(card);
      const payload = buildSharePayload(card);
      const fileName = `ficha_${sanitizeFileName(payload.name)}.png`;
      triggerDownload(blob, fileName);
    } catch (error) {
      console.error(error);
      alert("No se pudo generar la imagen PNG de la ficha.");
    } finally {
      event.currentTarget.disabled = false;
    }
  }

  async function handleShare(event) {
    const card = event.currentTarget.closest(CARD_SELECTOR);
    if (!card) return;
    event.currentTarget.disabled = true;
    try {
      const { name, detailUrl, shareText } = buildSharePayload(card);
      const blob = await cardToPngBlob(card);
      const fileName = `ficha_${sanitizeFileName(name)}.png`;
      const file = new File([blob], fileName, { type: "image/png" });

      if (
        navigator.share &&
        navigator.canShare &&
        navigator.canShare({ files: [file] })
      ) {
        await navigator.share({
          files: [file],
          title: "Identifica al represor",
          text: shareText,
          url: detailUrl,
        });
        return;
      }

      if (navigator.share) {
        await navigator.share({
          title: "Identifica al represor",
          text: shareText,
          url: detailUrl,
        });
        return;
      }

      triggerDownload(blob, fileName);
      openXIntent(shareText, detailUrl);
    } catch (error) {
      console.error(error);
      const { shareText, detailUrl } = buildSharePayload(card);
      openXIntent(shareText, detailUrl);
    } finally {
      event.currentTarget.disabled = false;
    }
  }

  function wireCardActions() {
    document.querySelectorAll(DOWNLOAD_SELECTOR).forEach((button) => {
      button.addEventListener("click", handleDownload);
    });
    document.querySelectorAll(SHARE_SELECTOR).forEach((button) => {
      button.addEventListener("click", handleShare);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireCardActions);
  } else {
    wireCardActions();
  }
})();
