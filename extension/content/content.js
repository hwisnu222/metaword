const CACHE_MS = 30_000;
const IGNORED_INPUT_TYPES = new Set([
  "button",
  "checkbox",
  "file",
  "hidden",
  "image",
  "radio",
  "reset",
  "submit",
]);

let panel = null;
let panelBody = null;
let target = null;
let files = [];
let failure = "";
let fetchedAt = 0;
let openToken = 0;
let suppressFocus = false;
let position = null;
let searchInput = null;
const thumbnailRequests = new Map();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function isEditable(node) {
  if (!node) {
    return false;
  }
  if (node.isContentEditable || node.tagName === "TEXTAREA") {
    return true;
  }
  return (
    node.tagName === "INPUT" &&
    !IGNORED_INPUT_TYPES.has(String(node.type || "text").toLowerCase())
  );
}

async function loadFiles(force = false) {
  if (!force && Date.now() - fetchedAt < CACHE_MS) {
    return;
  }

  try {
    const result = await browser.runtime.sendMessage({ type: "fetch-files" });
    if (!result.ok) {
      throw new Error(result.error);
    }
    files = result.files;
    failure = "";
  } catch (error) {
    files = [];
    failure = error.message;
  }
  fetchedAt = Date.now();
}

function insert(value) {
  if (!target || !target.isConnected) {
    return;
  }

  if (target.isContentEditable) {
    target.textContent = value;
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(target);
    range.collapse(false);
    selection?.removeAllRanges();
    selection?.addRange(range);
  } else {
    const prototype =
      target.tagName === "TEXTAREA"
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(target, value);
  }

  target.dispatchEvent(new Event("input", { bubbles: true }));
  target.dispatchEvent(new Event("change", { bubbles: true }));
  hide();
  suppressFocus = true;
  target.focus();
  queueMicrotask(() => {
    suppressFocus = false;
  });
}

function option(label, value, valueClass, wide = false) {
  const button = element(
    "button",
    wide ? "mw-option mw-option--wide" : "mw-option",
  );
  button.type = "button";
  button.title = value;
  button.append(
    element("span", "mw-label", label),
    element("span", valueClass, value),
  );
  button.addEventListener("click", () => insert(value));
  return button;
}

function optionsFor(file) {
  const rows = [];
  if (file.title?.trim()) {
    rows.push(option("Title", file.title.trim(), "mw-value"));
  }
  if (file.description?.trim()) {
    rows.push(
      option(
        "Description",
        file.description.trim(),
        "mw-value mw-value--description",
        true,
      ),
    );
  }
  const keywords = (file.keyword || []).join(", ").trim();
  if (keywords) {
    rows.push(option("Keyword", keywords, "mw-value"));
  }
  const categories = (file.category || []).join(", ").trim();
  if (categories) {
    rows.push(option("Category", categories, "mw-value"));
  }
  return rows;
}

function fileExtension(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "FILE" : name.slice(dot + 1, dot + 5).toUpperCase();
}

function loadThumbnail(path) {
  if (!thumbnailRequests.has(path)) {
    thumbnailRequests.set(
      path,
      browser.runtime
        .sendMessage({ type: "fetch-thumbnail", path })
        .then((result) => (result.ok ? result.url : null))
        .catch(() => null),
    );
  }
  return thumbnailRequests.get(path);
}

function createFileCard(file, optionNodes) {
  const item = element("li", "mw-file");
  const head = element("div", "mw-file-head");
  const thumb = element("span", "mw-thumb");
  thumb.setAttribute("aria-hidden", "true");
  thumb.append(
    element("span", "mw-thumb-fallback", fileExtension(file.name)),
  );
  const meta = element("div", "mw-file-meta");
  meta.append(element("p", "mw-name", file.name));
  head.append(thumb, meta);

  const options = element("div", "mw-options");
  options.append(...optionNodes);
  item.append(head, options);

  if (file.thumbnail) {
    loadThumbnail(file.thumbnail).then((url) => {
      if (!url) {
        return;
      }
      const image = document.createElement("img");
      image.className = "mw-thumb-image";
      image.src = url;
      image.alt = "";
      thumb.replaceChildren(image);
    });
  }

  return item;
}

function message(text, error = false) {
  return element(
    "p",
    error ? "mw-message mw-message--error" : "mw-message",
    text,
  );
}

function render() {
  panelBody.replaceChildren();

  if (failure) {
    const detail = failure.replace(/\.$/, "");
    panelBody.append(
      message(`Cannot load data: ${detail}. Start the API in the Metaword app.`, true),
    );
    return;
  }
  if (!files.length) {
    panelBody.append(message("The selected folder has no files."));
    return;
  }

  const query = searchInput.value.trim().toLowerCase();
  const visibleFiles = query
    ? files.filter((file) => file.name.toLowerCase().includes(query))
    : files;
  if (!visibleFiles.length) {
    panelBody.append(message(`No files match "${searchInput.value.trim()}".`));
    return;
  }

  const list = element("ul", "mw-list");
  for (const file of visibleFiles) {
    const optionNodes = optionsFor(file);
    if (optionNodes.length) {
      list.append(createFileCard(file, optionNodes));
    }
  }

  panelBody.append(list.children.length ? list : message("No metadata yet."));
}

function setPosition(left, top, remember = false) {
  const margin = 8;
  const width = panel.offsetWidth || 320;
  const height = panel.offsetHeight || 320;
  const next = {
    left: Math.min(
      Math.max(margin, left),
      Math.max(margin, window.innerWidth - width - margin),
    ),
    top: Math.min(
      Math.max(margin, top),
      Math.max(margin, window.innerHeight - height - margin),
    ),
  };

  panel.style.left = `${next.left}px`;
  panel.style.top = `${next.top}px`;
  if (remember) {
    position = next;
  }
}

function place() {
  if (panel.hidden) {
    return;
  }
  if (position) {
    setPosition(position.left, position.top);
    return;
  }
  if (!target) {
    return;
  }

  const rect = target.getBoundingClientRect();
  const margin = 8;
  const width = panel.offsetWidth || 320;
  const height = panel.offsetHeight || 320;
  const left = Math.min(
    Math.max(margin, rect.left),
    Math.max(margin, window.innerWidth - width - margin),
  );
  const below = rect.bottom + margin;
  const top =
    below + height <= window.innerHeight
      ? below
      : Math.max(margin, rect.top - height - margin);

  setPosition(left, top);
}

function startDrag(event) {
  if (event.button !== 0 || event.target.tagName === "BUTTON") {
    return;
  }
  event.preventDefault();

  if (!position) {
    const rect = panel.getBoundingClientRect();
    position = { left: rect.left, top: rect.top };
  }
  const startX = event.clientX;
  const startY = event.clientY;
  const startLeft = position.left;
  const startTop = position.top;
  panel.classList.add("mw-panel--dragging");

  const move = (moveEvent) => {
    setPosition(
      startLeft + moveEvent.clientX - startX,
      startTop + moveEvent.clientY - startY,
      true,
    );
  };
  const stop = () => {
    panel.classList.remove("mw-panel--dragging");
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
    document.removeEventListener("pointercancel", stop);
  };

  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", stop);
  document.addEventListener("pointercancel", stop);
}

function hide() {
  openToken += 1;
  panel.hidden = true;
}

async function open(node) {
  const token = ++openToken;
  target = node;
  await loadFiles();
  if (token !== openToken) {
    return;
  }

  render();
  panel.hidden = false;
  place();
}

function createPanel() {
  const root = element("div", "mw-panel");
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-label", "Insert metadata");
  root.hidden = true;

  const header = element("div", "mw-header");
  header.addEventListener("pointerdown", startDrag);
  header.append(element("span", "mw-brand", "Metaword"));

  const refresh = element("button", "mw-tool", "Refresh");
  refresh.type = "button";
  refresh.addEventListener("click", async () => {
    await loadFiles(true);
    render();
    place();
  });

  const close = element("button", "mw-tool", "Close");
  close.type = "button";
  close.addEventListener("click", hide);

  header.append(refresh, close);

  const searchWrap = element("div", "mw-search-wrap");
  searchInput = element("input", "mw-search");
  searchInput.type = "search";
  searchInput.placeholder = "Search files";
  searchInput.setAttribute("aria-label", "Search files by name");
  searchInput.addEventListener("input", render);
  searchWrap.append(searchInput);

  panelBody = element("div", "mw-body");
  root.append(header, searchWrap, panelBody);
  document.body.append(root);
  return root;
}

panel = createPanel();

document.addEventListener("focusin", (event) => {
  if (panel.contains(event.target)) {
    return;
  }
  if (suppressFocus && event.target === target) {
    return;
  }
  if (isEditable(event.target)) {
    open(event.target);
  } else if (!panel.contains(event.target)) {
    hide();
  }
});

document.addEventListener(
  "pointerdown",
  (event) => {
    if (
      !panel.hidden &&
      event.target !== target &&
      !panel.contains(event.target)
    ) {
      hide();
    }
  },
  true,
);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hide();
  }
});

window.addEventListener("scroll", place, true);
window.addEventListener("resize", place);
