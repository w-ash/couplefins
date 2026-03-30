type EventHandler = (data: Record<string, unknown>) => void;

const listeners = new Set<EventHandler>();
let es: EventSource | null = null;

function ensureConnection(): void {
  if (es || typeof EventSource === "undefined") return;
  es = new EventSource("/api/v1/events");

  es.onmessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as Record<string, unknown>;
      for (const handler of listeners) {
        handler(data);
      }
    } catch {
      // Ignore malformed events
    }
  };

  es.onerror = () => {
    // EventSource auto-reconnects; nothing to do
  };
}

function maybeClose(): void {
  if (listeners.size === 0 && es) {
    es.close();
    es = null;
  }
}

/** Subscribe to all SSE events. Returns an unsubscribe function. */
export function subscribe(handler: EventHandler): () => void {
  listeners.add(handler);
  ensureConnection();
  return () => {
    listeners.delete(handler);
    maybeClose();
  };
}

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    if (es) {
      es.close();
      es = null;
    }
    listeners.clear();
  });
}
