const API_ORIGIN = "http://127.0.0.1:8765";
const thumbnailUrls = new Map();

async function fetchThumbnail(path) {
  if (!path.startsWith("/api/thumbnail/") || path.includes("..")) {
    throw new Error("Invalid thumbnail path");
  }
  if (thumbnailUrls.has(path)) {
    return thumbnailUrls.get(path);
  }

  const request = (async () => {
    const response = await fetch(new URL(path, API_ORIGIN));
    if (!response.ok) {
      throw new Error(`API responded with ${response.status}`);
    }
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  })();
  thumbnailUrls.set(path, request);

  try {
    return await request;
  } catch (error) {
    thumbnailUrls.delete(path);
    throw error;
  }
}

browser.runtime.onMessage.addListener(async (message) => {
  try {
    if (message.type === "fetch-files") {
      const response = await fetch(`${API_ORIGIN}/api/files`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`API responded with ${response.status}`);
      }
      const data = await response.json();
      return { ok: true, files: data.files };
    }
    if (message.type === "fetch-thumbnail") {
      return { ok: true, url: await fetchThumbnail(message.path) };
    }
  } catch (error) {
    return { ok: false, error: error.message };
  }
});
