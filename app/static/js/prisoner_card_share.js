(function () {
  const CARD_SELECTOR = "[data-prisoner-card]";
  const DOWNLOAD_SELECTOR = "[data-prisoner-download-btn]";
  const SHARE_SELECTOR = "[data-prisoner-share-btn]";
  const ART_SELECTOR = ".repressor-duel-art[data-prisoner-image]";
  const IMAGE_MODAL_ID = "prisonerImageModal";
  const IMAGE_MODAL_IMG_ID = "prisonerImageModalImg";
  const IMAGE_MODAL_CAPTION_ID = "prisonerImageModalCaption";
  const IMAGE_MODAL_CLOSE_SELECTOR = "[data-close-prisoner-image]";
  const DESKTOP_CAPTURE_WIDTH_PX = 720;

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
      } catch (_firstError) {
        await loadScript("https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js");
      }
      if (!window.html2canvas) {
        throw new Error("html2canvas no disponible");
      }
      return window.html2canvas;
    })();

    return html2CanvasPromise;
  }

  function buildCaptureContainer() {
    const wrapper = document.createElement("div");
    wrapper.style.position = "fixed";
    wrapper.style.left = "-10000px";
    wrapper.style.top = "0";
    wrapper.style.zIndex = "-1";
    wrapper.style.pointerEvents = "none";
    wrapper.style.opacity = "0";
    wrapper.style.background = "transparent";
    return wrapper;
  }

  async function waitForImages(root) {
    const images = Array.from(root.querySelectorAll("img"));
    if (!images.length) return;
    await Promise.all(
      images.map((img) => {
        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
        return new Promise((resolve) => {
          const done = () => resolve();
          img.addEventListener("load", done, { once: true });
          img.addEventListener("error", done, { once: true });
        });
      })
    );
  }

  function buildCardClone(card) {
    const clone = card.cloneNode(true);
    clone.style.width = `${DESKTOP_CAPTURE_WIDTH_PX}px`;
    clone.style.maxWidth = `${DESKTOP_CAPTURE_WIDTH_PX}px`;
    clone.style.height = "auto";
    clone.style.minHeight = "0";
    clone.style.overflow = "visible";
    clone.style.aspectRatio = "auto";
    clone.style.padding = "14px";
    clone.style.gap = "10px";

    const head = clone.querySelector(".repressor-duel-head");
    if (head) {
      head.style.flexDirection = "row";
      head.style.alignItems = "flex-start";
      head.style.justifyContent = "space-between";
      head.style.gap = "12px";
    }

    const name = clone.querySelector(".repressor-duel-name");
    if (name) {
      name.style.fontSize = "24px";
    }

    const code = clone.querySelector(".repressor-duel-code");
    if (code) {
      code.style.textAlign = "right";
    }

    const artFrame = clone.querySelector(".repressor-duel-art-frame");
    if (artFrame) {
      artFrame.style.background = "#262324";
      artFrame.style.width = "360px";
      artFrame.style.justifySelf = "center";
      artFrame.style.minHeight = "0";
      artFrame.style.height = "auto";
      artFrame.style.aspectRatio = "1 / 1";
    }

    clone.querySelectorAll(".repressor-duel-art").forEach((img) => {
      img.style.width = "100%";
      img.style.height = "100%";
      img.style.objectFit = "cover";
      img.style.objectPosition = "center";
      img.style.background = "#262324";
    });

    const grid = clone.querySelector(".repressor-duel-grid");
    if (grid) {
      grid.style.gridTemplateColumns = "repeat(2, minmax(0, 1fr))";
    }

    const actions = clone.querySelector(".repressor-duel-actions");
    if (actions) {
      actions.style.display = "flex";
      actions.style.flexWrap = "wrap";
      actions.style.gridTemplateColumns = "none";
    }
    return clone;
  }

  async function cardToPngBlob(card) {
    const html2canvas = await ensureHtml2Canvas();
    const wrapper = buildCaptureContainer();
    const clone = buildCardClone(card);
    wrapper.appendChild(clone);
    document.body.appendChild(wrapper);
    try {
      await waitForImages(clone);
      const canvas = await html2canvas(clone, {
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
    } finally {
      wrapper.remove();
    }
  }

  function sanitizeFileName(name) {
    const safe = String(name || "prisionero")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9-_ ]+/g, "")
      .trim()
      .replace(/\s+/g, "_")
      .slice(0, 80);
    return safe || "prisionero";
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
    const name = card.dataset.prisonerName || "Prisionero";
    const prison = card.dataset.prisonerPrison || "N/D";
    const detailPath = card.dataset.prisonerUrl || window.location.pathname;
    const detailUrl = new URL(detailPath, window.location.origin).toString();
    const shareText = `Ficha de prisionero político\nNombre: ${name}\nPrisión: ${prison}\nFicha: ${detailUrl}\n#SOSCuba #LibertadParaLosPresosPoliticos`;
    return { name, detailUrl, shareText };
  }

  function openXIntent(shareText) {
    const intentUrl = "https://twitter.com/intent/tweet?text=" + encodeURIComponent(shareText);
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

      if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: "Ficha de prisionero político",
          text: shareText,
          url: detailUrl,
        });
        return;
      }

      if (navigator.share) {
        await navigator.share({
          title: "Ficha de prisionero político",
          text: shareText,
          url: detailUrl,
        });
        return;
      }

      triggerDownload(blob, fileName);
      openXIntent(shareText);
    } catch (error) {
      console.error(error);
      const { shareText } = buildSharePayload(card);
      openXIntent(shareText);
    } finally {
      event.currentTarget.disabled = false;
    }
  }

  function wireImageModal() {
    const modal = document.getElementById(IMAGE_MODAL_ID);
    const modalImg = document.getElementById(IMAGE_MODAL_IMG_ID);
    const modalCaption = document.getElementById(IMAGE_MODAL_CAPTION_ID);
    if (!modal || !modalImg) return;

    const closeModal = () => {
      modal.setAttribute("aria-hidden", "true");
      modal.classList.remove("open");
      modalImg.src = "";
      if (modalCaption) modalCaption.textContent = "";
    };

    document.querySelectorAll(IMAGE_MODAL_CLOSE_SELECTOR).forEach((button) => {
      button.addEventListener("click", closeModal);
    });

    const openModal = (imageUrl, captionText) => {
      const url = String(imageUrl || "").trim();
      if (!url) return;
      modalImg.src = url;
      if (modalCaption) modalCaption.textContent = String(captionText || "").trim();
      modal.setAttribute("aria-hidden", "false");
      modal.classList.add("open");
    };

    document.querySelectorAll(ART_SELECTOR).forEach((image) => {
      image.addEventListener("click", () => {
        openModal(image.getAttribute("data-prisoner-image"), image.getAttribute("data-prisoner-caption"));
      });
      image.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openModal(image.getAttribute("data-prisoner-image"), image.getAttribute("data-prisoner-caption"));
      });
    });
  }

  function wireCardActions() {
    document.querySelectorAll(DOWNLOAD_SELECTOR).forEach((button) => {
      button.addEventListener("click", handleDownload);
    });
    document.querySelectorAll(SHARE_SELECTOR).forEach((button) => {
      button.addEventListener("click", handleShare);
    });
    wireImageModal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireCardActions);
  } else {
    wireCardActions();
  }
})();
