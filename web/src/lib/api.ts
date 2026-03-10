/**
 * Fetch wrapper that throws with the server's error message on non-OK responses.
 */
export async function apiFetch<T>(
  url: string,
  init?: RequestInit,
  fallbackMessage = "Request failed",
): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? body?.detail ?? fallbackMessage);
  }
  return res.json();
}
