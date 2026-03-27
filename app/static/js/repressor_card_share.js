(function () {
  const CARD_SELECTOR = "[data-repressor-card]";
  const DOWNLOAD_SELECTOR = "[data-repressor-download-btn]";
  const SHARE_SELECTOR = "[data-repressor-share-btn]";
  const VERIFY_SELECTOR = "[data-repressor-verify-btn]";
  const VERIFY_COUNT_SELECTOR = "[data-repressor-verify-count]";
  const ART_SELECTOR = ".repressor-duel-art[data-repressor-image]";
  const IMAGE_MODAL_ID = "repressorImageModal";
  const IMAGE_MODAL_IMG_ID = "repressorImageModalImg";
  const IMAGE_MODAL_CAPTION_ID = "repressorImageModalCaption";
  const IMAGE_MODAL_CLOSE_SELECTOR = "[data-close-repressor-image]";
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
      artFrame.style.minHeight = "220px";
      artFrame.style.height = "clamp(220px, 36vh, 420px)";
    }
    clone.querySelectorAll(".repressor-duel-art").forEach((img) => {
      img.style.objectFit = "contain";
      img.style.objectPosition = "top center";
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
    const shareText = `Identifica al represor\nNombre: ${name}\nTipo: ${typeText}\nFicha: ${detailUrl}\n#SOSCuba`;
    return { name, typeText, detailUrl, shareText };
  }

  function openXIntent(shareText) {
    const intentUrl = "https://twitter.com/intent/tweet?text=" + encodeURIComponent(shareText);
    window.open(intentUrl, "_blank", "noopener,noreferrer");
  }

  async function verifyRepressor(repressorId) {
    const res = await fetch(`/api/repressors/${repressorId}/verify`, { method: "POST" });
    return await res.json();
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
      openXIntent(shareText);
    } catch (error) {
      console.error(error);
      const { shareText } = buildSharePayload(card);
      openXIntent(shareText);
    } finally {
      event.currentTarget.disabled = false;
    }
  }

  function wireRepressorVerification() {
    document.querySelectorAll(VERIFY_SELECTOR).forEach((button) => {
      if (button.getAttribute("data-verified") === "1") {
        button.disabled = true;
        button.textContent = "Verificado";
        button.classList.add("is-verified");
      }
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        const repressorId = button.getAttribute("data-repressor-id");
        if (!repressorId) return;

        button.disabled = true;
        try {
          const result = await verifyRepressor(repressorId);
          const card = button.closest(CARD_SELECTOR);
          const countEl =
            (card && card.querySelector(`#repressor-verify-count-${repressorId}`)) ||
            (card && card.querySelector(VERIFY_COUNT_SELECTOR));

          if (countEl && result && typeof result.verify_count !== "undefined") {
            countEl.textContent = result.verify_count;
          }
          if (result && result.ok) {
            button.textContent = "Verificado";
            button.setAttribute("data-verified", "1");
            button.classList.add("is-verified");
            if (result.locked) {
              window.location.reload();
            }
            return;
          }
        } catch (error) {
          console.error(error);
        } finally {
          if (button.getAttribute("data-verified") !== "1") {
            button.disabled = false;
          }
        }
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
    wireRepressorVerification();
    wireImageModal();
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
        openModal(image.getAttribute("data-repressor-image"), image.getAttribute("data-repressor-caption"));
      });
      image.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openModal(image.getAttribute("data-repressor-image"), image.getAttribute("data-repressor-caption"));
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireCardActions);
  } else {
    wireCardActions();
  }
})();
