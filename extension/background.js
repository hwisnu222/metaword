const API_URL = "http://127.0.0.1:8765/api/files";

browser.runtime.onMessage.addListener(async (message) => {
  if (message.type !== "fetch-files") {
    return;
  }

  try {
    const response = await fetch(API_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`API responded with ${response.status}`);
    }
    const data = await response.json();
    return { ok: true, files: data.files };
  } catch (error) {
    return { ok: false, error: error.message };
  }
});
