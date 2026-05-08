/** FastAPI/Pydantic errors: `detail` may be a string or an array of { loc, msg, type }. */

export function formatFastApiError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const msg = (item as { msg?: string }).msg;
        const loc = (item as { loc?: unknown }).loc;
        const where =
          Array.isArray(loc) && loc.length
            ? `${loc.filter((x) => typeof x === "string").join(".")}: `
            : "";
        return `${where}${msg ?? JSON.stringify(item)}`;
      }
      return JSON.stringify(item);
    });
    return parts.join("; ") || fallback;
  }
  return fallback;
}
