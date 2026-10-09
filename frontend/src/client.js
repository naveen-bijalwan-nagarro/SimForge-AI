export async function api(path, body) {
  const response = await fetch("/api" + path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-SimForge-Request": "1" },
    ...(body === undefined
      ? {}
      : { method: "POST", body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const text = await response.text();
    let detail;
    try {
      detail = JSON.parse(text).detail;
    } catch {
      detail = text;
    }
    if (response.status === 404 && detail === "API endpoint not found") {
      detail =
        "The running backend is out of date. Restart SimForge with scripts/start.ps1, then refresh this page.";
    }
    throw new Error(
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail || response.statusText),
    );
  }
  return response.json();
}
