function wrapSelection(textarea, before, after) {
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const value = textarea.value || "";
  const selected = value.substring(start, end) || "";
  const next = value.substring(0, start) + before + selected + after + value.substring(end);
  textarea.value = next;
  const cursor = start + before.length;
  textarea.setSelectionRange(cursor, cursor + selected.length);
  textarea.focus();
}

function renderMarkdown(source) {
  const raw = source || "";
  if (window.marked) {
    window.marked.setOptions({ breaks: true });
    const parsed = window.marked.parse(raw);
    if (window.DOMPurify) return window.DOMPurify.sanitize(parsed);
    return parsed;
  }
  return raw.replaceAll("\n", "<br />");
}

function setupMarkdownEditor() {
  const textarea = document.getElementById("discussionBody");
  const preview = document.getElementById("discussionPreview");
  if (!textarea || !preview) return;

  const render = () => {
    preview.innerHTML = renderMarkdown(textarea.value);
  };

  render();
  textarea.addEventListener("input", render);

  document.querySelectorAll(".editor-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.md;
      if (!action) return;
      if (action === "bold") wrapSelection(textarea, "**", "**");
      if (action === "italic") wrapSelection(textarea, "*", "*");
      if (action === "underline") wrapSelection(textarea, "<u>", "</u>");
      if (action === "link") {
        const url = window.prompt("URL del enlace");
        if (!url) return;
        wrapSelection(textarea, "[", `](${url})`);
      }
      render();
    });
  });
}

function setupLinks() {
  const addBtn = document.getElementById("addDiscussionLink");
  const list = document.getElementById("discussionLinks");
  if (!addBtn || !list) return;
  addBtn.addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "url";
    input.name = "links[]";
    input.placeholder = "https://ejemplo.com/fuente";
    list.appendChild(input);
  });
}

function setupTagPicker() {
  const container = document.getElementById("tagOptions");
  const selectedHolder = document.getElementById("selectedTags");
  if (!container || !selectedHolder) return;

  const selected = new Set();

  const syncInputs = () => {
    selectedHolder.innerHTML = "";
    selected.forEach((tag) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "tags[]";
      input.value = tag;
      selectedHolder.appendChild(input);
    });
  };

  container.querySelectorAll(".tag-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag;
      if (!tag) return;
      if (selected.has(tag)) {
        selected.delete(tag);
        chip.classList.remove("active");
      } else {
        selected.add(tag);
        chip.classList.add("active");
      }
      syncInputs();
    });
  });
}

function setupImageUploads() {
  const input = document.querySelector('input[name="images"]');
  const status = document.getElementById("discussionImageStatus");
  const previewList = document.getElementById("discussionImagePreviewList");
  if (!input || !previewList) return;

  const maxFiles = parseInt(input.dataset.maxFiles || "3", 10);
  const maxMb = parseInt(input.dataset.maxMb || "2", 10);
  const allowedExt = (input.dataset.allowedExt || "jpg,jpeg,png,webp,heic")
    .split(",")
    .map((ext) => ext.trim().toLowerCase())
    .filter(Boolean);
  const maxBytes = maxMb * 1024 * 1024;

  const showError = (message) => {
    if (!status) return;
    status.textContent = message;
  };

  const renderPreviews = () => {
    if (!input.files || input.files.length === 0) {
      previewList.innerHTML = "";
      return;
    }
    previewList.innerHTML = Array.from(input.files)
      .map((file, idx) => {
        const url = URL.createObjectURL(file);
        return `
          <div class="image-preview-card">
            <img src="${url}" alt="Vista previa ${idx + 1}" />
            <label class="image-caption">
              Descripción corta (opcional)
              <input type="text" name="image_captions[]" maxlength="255" placeholder="${file.name}" />
            </label>
          </div>
        `;
      })
      .join("");
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

function setupVotes() {
  document.querySelectorAll(".vote-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const type = btn.dataset.type;
      const id = btn.dataset.id;
      const value = parseInt(btn.dataset.value, 10);
      if (!type || !id || !value) return;
      const url =
        type === "post"
          ? `/api/discusiones/${id}/vote`
          : type === "news-comment"
            ? `/api/noticias/comentarios/${id}/vote`
            : `/api/discusiones/comentarios/${id}/vote`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      const data = await res.json();
      if (!data) return;
      const scoreEl =
        type === "post"
          ? document.getElementById(`post-score-${id}`)
          : document.getElementById(`comment-score-${id}`);
      if (scoreEl && typeof data.score !== "undefined") {
        scoreEl.textContent = data.score;
        scoreEl.classList.toggle("score-negative", data.score < 0);
      }
    });
  });
}

function setupLoadingButtons() {
  const form = document.querySelector(".discussion-form");
  if (form) {
    form.addEventListener("submit", () => {
      const submit = form.querySelector('button[type="submit"]');
      if (!submit) return;
      submit.disabled = true;
      submit.dataset.loading = "true";
      submit.textContent = "Publicando...";
    });
  }
  const commentForm = document.querySelector(".comment-form");
  if (commentForm) {
    commentForm.addEventListener("submit", () => {
      const submit = commentForm.querySelector('button[type="submit"]');
      if (!submit) return;
      submit.disabled = true;
      submit.dataset.loading = "true";
      submit.textContent = "Enviando...";
    });
  }
}

function setupReplyToggles() {
  document.querySelectorAll("[data-reply-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-reply-toggle");
      if (!id) return;
      const form = document.getElementById(`reply-form-${id}`);
      if (!form) return;
      form.classList.toggle("is-hidden");
      if (!form.classList.contains("is-hidden")) {
        const textarea = form.querySelector("textarea");
        if (textarea) textarea.focus();
      }
    });
  });
}

function setupCommentRecaptcha() {
  const forms = document.querySelectorAll("form.comment-form");
  if (!forms.length) return;
  if (!window.grecaptcha) {
    setTimeout(setupCommentRecaptcha, 400);
    return;
  }
  const status = document.getElementById("discussionRecaptchaStatus");

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      const token = grecaptcha.getResponse();
      if (!token) {
        event.preventDefault();
        if (status) {
          status.textContent = "Completa el reCAPTCHA antes de enviar.";
        } else {
          alert("Completa el reCAPTCHA antes de enviar.");
        }
        return;
      }
      let hidden = form.querySelector('input[name="g-recaptcha-response"]');
      if (!hidden) {
        hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "g-recaptcha-response";
        form.appendChild(hidden);
      }
      hidden.value = token;
    });
  });
}

function setupDiscussionGallery() {
  const modal = document.getElementById("discussionImageModal");
  const modalImg = document.getElementById("discussionImageModalImg");
  const modalCaption = document.getElementById("discussionImageModalCaption");
  if (!modal || !modalImg) return;

  const thumbs = Array.from(document.querySelectorAll(".discussion-gallery-thumb"));
  const navButtons = Array.from(document.querySelectorAll("[data-discussion-nav]"));
  let currentIndex = -1;

  const updateNavState = () => {
    if (thumbs.length <= 1) {
      navButtons.forEach((btn) => btn.classList.add("is-hidden"));
      return;
    }
    navButtons.forEach((btn) => btn.classList.remove("is-hidden"));
  };

  const openAt = (index) => {
    if (!thumbs.length) return;
    const safeIndex = ((index % thumbs.length) + thumbs.length) % thumbs.length;
    const target = thumbs[safeIndex];
    const url = target.getAttribute("data-image");
    const caption = target.getAttribute("data-caption") || "";
    if (!url) return;
    currentIndex = safeIndex;
    modalImg.src = url;
    if (modalCaption) modalCaption.textContent = caption;
    modal.setAttribute("aria-hidden", "false");
    modal.classList.add("open");
    updateNavState();
  };

  const close = () => {
    modal.setAttribute("aria-hidden", "true");
    modal.classList.remove("open");
    modalImg.src = "";
    if (modalCaption) modalCaption.textContent = "";
    currentIndex = -1;
  };

  document.querySelectorAll("[data-close-discussion-image]").forEach((btn) => {
    btn.addEventListener("click", close);
  });

  thumbs.forEach((btn, index) => {
    btn.addEventListener("click", () => {
      openAt(index);
    });
  });

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (currentIndex === -1) return;
      const direction = btn.getAttribute("data-discussion-nav");
      if (direction === "next") {
        openAt(currentIndex + 1);
      } else if (direction === "prev") {
        openAt(currentIndex - 1);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if (!modal.classList.contains("open")) return;
    if (event.key === "ArrowRight") {
      openAt(currentIndex + 1);
    } else if (event.key === "ArrowLeft") {
      openAt(currentIndex - 1);
    } else if (event.key === "Escape") {
      close();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupMarkdownEditor();
  setupLinks();
  setupImageUploads();
  setupVotes();
  setupLoadingButtons();
  setupReplyToggles();
  setupCommentRecaptcha();
  setupTagPicker();
  setupDiscussionGallery();
});
