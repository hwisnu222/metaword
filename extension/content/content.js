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

function option(label, value, valueClass) {
  const button = element("button", "mw-option");
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

  const list = element("ul", "mw-list");
  for (const file of files) {
    const rows = optionsFor(file);
    if (!rows.length) {
      continue;
    }
    const item = element("li", "mw-file");
    item.append(element("p", "mw-name", file.name), ...rows);
    list.append(item);
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
  panelBody = element("div", "mw-body");
  root.append(header, panelBody);
  document.body.append(root);
  return root;
}

panel = createPanel();

document.addEventListener("focusin", (event) => {
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
