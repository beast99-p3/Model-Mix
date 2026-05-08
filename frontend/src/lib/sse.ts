export type SseHandler = (data: Record<string, unknown>) => void;

/**
 * Parse newline-delimited SSE chunks (data: {...}\\n\\n).
 */
export async function consumeSseStream(
  response: Response,
  onEvent: SseHandler,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");
  const dec = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const jsonText = line.replace(/^data:\s*/, "");
      try {
        onEvent(JSON.parse(jsonText) as Record<string, unknown>);
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
}
