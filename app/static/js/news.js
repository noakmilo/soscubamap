function newsWrapSelection(textarea, before, after, placeholder = "") {
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const value = textarea.value || "";
  const selected = value.substring(start, end) || placeholder;
  textarea.value = value.substring(0, start) + before + selected + after + value.substring(end);
  const cursor = start + before.length;
  textarea.setSelectionRange(cursor, cursor + selected.length);
  textarea.focus();
}

const newsImageObjectUrls = new Map();

function newsResolveImageTokens(source) {
  let raw = source || "";
  newsImageObjectUrls.forEach((url, idx) => {
    raw = raw.replaceAll(`news-image:${idx}`, url);
  });
  return raw;
}

function newsRenderMarkdown(source) {
  const raw = newsResolveImageTokens(source);
  if (window.marked) {
    window.marked.setOptions({ breaks: true });
    const parsed = window.marked.parse(raw);
    if (window.DOMPurify) return window.DOMPurify.sanitize(parsed);
    return parsed;
  }
  return raw.replaceAll("\n", "<br />");
}

function setupNewsEditor() {
  const textarea = document.getElementById("newsBody");
  const preview = document.getElementById("newsPreview");
  if (!textarea || !preview) return;

  const render = () => {
    preview.innerHTML = newsRenderMarkdown(textarea.value);
  };

  render();
  textarea.addEventListener("input", render);

  document.querySelectorAll(".news-form .editor-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.md;
      if (action === "bold") newsWrapSelection(textarea, "**", "**", "texto");
      if (action === "italic") newsWrapSelection(textarea, "*", "*", "texto");
      if (action === "underline") newsWrapSelection(textarea, "<u>", "</u>", "texto");
      if (action === "h2") newsWrapSelection(textarea, "\n## ", "\n", "Subtitulo");
      if (action === "h3") newsWrapSelection(textarea, "\n### ", "\n", "Subtitulo");
      if (action === "link") {
        const url = window.prompt("URL del enlace");
        if (!url) return;
        newsWrapSelection(textarea, "[", `](${url})`, "enlace");
      }
      render();
    });
  });
}

function insertNewsImage(idx) {
  const textarea = document.getElementById("newsBody");
  if (!textarea) return;
  const altInput = document.querySelector(`[data-news-image-alt="${idx}"]`);
  const alt = altInput && altInput.value.trim() ? altInput.value.trim() : "Imagen";
  newsWrapSelection(textarea, `\n![${alt}](news-image:${idx})\n`, "", "");
  const preview = document.getElementById("newsPreview");
  if (preview) preview.innerHTML = newsRenderMarkdown(textarea.value);
}

function setupNewsImages() {
  const input = document.querySelector('.news-form input[name="images"]');
  const status = document.getElementById("newsImageStatus");
  const previewList = document.getElementById("newsImagePreviewList");
  if (!input || !previewList) return;

  const maxFiles = parseInt(input.dataset.maxFiles || "3", 10);
  const maxMb = parseInt(input.dataset.maxMb || "2", 10);
  const allowedExt = (input.dataset.allowedExt || "jpg,jpeg,png,webp,heic")
    .split(",")
    .map((ext) => ext.trim().toLowerCase())
    .filter(Boolean);
  const maxBytes = maxMb * 1024 * 1024;

  const showError = (message) => {
    if (status) status.textContent = message;
  };

  const renderPreviews = () => {
    newsImageObjectUrls.clear();
    if (!input.files || input.files.length === 0) {
      previewList.innerHTML = "";
      return;
    }
    previewList.innerHTML = Array.from(input.files)
      .map((file, idx) => {
        const url = URL.createObjectURL(file);
        newsImageObjectUrls.set(idx, url);
        const label = idx === 0 ? "ALT de imagen principal" : "ALT de imagen";
        return `
          <div class="image-preview-card">
            <img src="${url}" alt="Vista previa ${idx + 1}" />
            <label class="image-caption">
              ${label}
              <input type="text" name="image_alts[]" maxlength="255" placeholder="${file.name}" data-news-image-alt="${idx}" />
            </label>
            <button type="button" class="btn-secondary news-insert-image-btn" data-news-insert-image="${idx}">
              <i class="fa-solid fa-image" aria-hidden="true"></i>
              <span>Insertar imagen</span>
            </button>
          </div>
        `;
      })
      .join("");
    previewList.querySelectorAll("[data-news-insert-image]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.getAttribute("data-news-insert-image"));
        if (Number.isFinite(idx)) insertNewsImage(idx);
      });
    });
    const textarea = document.getElementById("newsBody");
    const preview = document.getElementById("newsPreview");
    if (textarea && preview) preview.innerHTML = newsRenderMarkdown(textarea.value);
  };

  input.addEventListener("change", () => {
    if (!input.files) return;
    if (input.files.length > maxFiles) {
      showError(`Máximo ${maxFiles} imágenes por envío.`);
      input.value = "";
      renderPreviews();
      return;
    }
    for (const file of Array.from(input.files)) {
      const name = file.name || "";
      const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
      if (!allowedExt.includes(ext)) {
        showError(`Formato no permitido: ${ext || "desconocido"}.`);
        input.value = "";
        renderPreviews();
        return;
      }
      if (file.size > maxBytes) {
        showError(`Cada imagen debe ser <= ${maxMb}MB.`);
        input.value = "";
        renderPreviews();
        return;
      }
    }
    if (status) status.textContent = "";
    renderPreviews();
  });
}

function setupNewsSummary() {
  const form = document.querySelector(".news-form");
  const button = document.getElementById("generateNewsSummary");
  const status = document.getElementById("newsSummaryStatus");
  const title = document.getElementById("newsTitle");
  const body = document.getElementById("newsBody");
  const summary = document.getElementById("newsSummary");
  if (!form || !button || !body || !summary) return;

  const setStatus = (message) => {
    if (status) status.textContent = message;
  };

  button.addEventListener("click", async () => {
    const endpoint = form.dataset.summaryUrl || "";
    if (!endpoint) return;
    if (!(body.value || "").trim()) {
      setStatus("Escribe el cuerpo primero.");
      return;
    }
    button.disabled = true;
    button.dataset.loading = "true";
    setStatus("Generando resumen...");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title ? title.value : "",
          body: body.value,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "No se pudo generar el resumen.");
      }
      summary.value = payload.summary || "";
      setStatus("Resumen listo.");
    } catch (error) {
      setStatus(error.message || "No se pudo generar el resumen.");
    } finally {
      button.disabled = false;
      button.dataset.loading = "";
    }
  });
}

function setupNewsSubmit() {
  const form = document.querySelector(".news-form");
  if (!form) return;
  form.addEventListener("submit", () => {
    const submit = form.querySelector('button[type="submit"]');
    if (!submit) return;
    submit.disabled = true;
    submit.dataset.loading = "true";
    submit.textContent = submit.textContent.includes("Guardar") ? "Guardando..." : "Publicando...";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupNewsEditor();
  setupNewsImages();
  setupNewsSummary();
  setupNewsSubmit();
});
