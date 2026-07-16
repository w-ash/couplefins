import { beforeEach, describe, expect, it, vi } from "vitest";
import { sendChatMessage } from "./chat-sse";

function makeSSEBody(events: Record<string, unknown>[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

function makeReadableStream(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function makeCallbacks() {
  const cb = {
    tokens: [] as string[],
    toolStarts: [] as { name: string; id: string; kind: string }[],
    toolResults: [] as {
      name: string;
      id: string;
      summary: unknown;
      isError: boolean;
    }[],
    codeStarts: [] as { id: string; command: string }[],
    codeResults: [] as {
      id: string;
      stdout: string;
      stderr: string;
      returnCode: number;
    }[],
    errors: [] as { code: string; message: string }[],
    doneCount: 0,
    onToken(text: string) {
      cb.tokens.push(text);
    },
    onToolStart(name: string, id: string, kind: string) {
      cb.toolStarts.push({ name, id, kind });
    },
    onToolResult(name: string, id: string, summary: unknown, isError: boolean) {
      cb.toolResults.push({ name, id, summary, isError });
    },
    onCodeStart(id: string, command: string) {
      cb.codeStarts.push({ id, command });
    },
    onCodeResult(
      id: string,
      stdout: string,
      stderr: string,
      returnCode: number,
    ) {
      cb.codeResults.push({ id, stdout, stderr, returnCode });
    },
    onDone() {
      cb.doneCount++;
    },
    onError(code: string, message: string) {
      cb.errors.push({ code, message });
    },
  };
  return cb;
}

describe("sendChatMessage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("streams token events", async () => {
    const body = makeSSEBody([
      { type: "token", text: "Hello" },
      { type: "token", text: " world" },
      { type: "done" },
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeReadableStream(body),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage(
      [{ role: "user", content: "Hi" }],
      cb,
      new AbortController().signal,
    );

    expect(cb.tokens).toEqual(["Hello", " world"]);
    expect(cb.doneCount).toBe(1);
  });

  it("sends the browser's local date as client_date", async () => {
    const body = makeSSEBody([{ type: "done" }]);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeReadableStream(body),
    });
    vi.stubGlobal("fetch", fetchMock);

    const cb = makeCallbacks();
    await sendChatMessage(
      [{ role: "user", content: "Hi" }],
      cb,
      new AbortController().signal,
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const sentBody = JSON.parse(init.body as string) as {
      client_date?: string;
    };
    expect(sentBody.client_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("sends the page section only when provided", async () => {
    // Fresh stream per call — a consumed ReadableStream cannot be re-read.
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        body: makeReadableStream(makeSSEBody([{ type: "done" }])),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const cb = makeCallbacks();
    const signal = new AbortController().signal;
    await sendChatMessage([], cb, signal, undefined, undefined, "budget");
    await sendChatMessage([], cb, signal);

    const bodies = fetchMock.mock.calls.map(
      (call) =>
        JSON.parse((call[1] as RequestInit).body as string) as {
          page?: string;
        },
    );
    expect(bodies[0].page).toBe("budget");
    expect(bodies[1]).not.toHaveProperty("page");
  });

  it("handles tool_start and tool_result events", async () => {
    const body = makeSSEBody([
      {
        type: "tool_start",
        name: "get_settlement_balance",
        id: "tc-1",
        kind: "read",
      },
      {
        type: "tool_start",
        name: "record_settlement",
        id: "tc-2",
        kind: "write",
      },
      // No kind field (older stream) — client defaults to "read".
      { type: "tool_start", name: "get_tags", id: "tc-3" },
      {
        type: "tool_result",
        name: "get_settlement_balance",
        id: "tc-1",
        summary: { amount: 147.5 },
        is_error: false,
      },
      { type: "token", text: "Alice owes Bob $147.50" },
      { type: "done" },
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeReadableStream(body),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.toolStarts).toEqual([
      { name: "get_settlement_balance", id: "tc-1", kind: "read" },
      { name: "record_settlement", id: "tc-2", kind: "write" },
      { name: "get_tags", id: "tc-3", kind: "read" },
    ]);
    expect(cb.toolResults).toEqual([
      {
        name: "get_settlement_balance",
        id: "tc-1",
        summary: { amount: 147.5 },
        isError: false,
      },
    ]);
    expect(cb.tokens).toEqual(["Alice owes Bob $147.50"]);
  });

  it("handles code_start and code_result events", async () => {
    const body = makeSSEBody([
      { type: "code_start", id: "srvtoolu_1", command: "print(total)" },
      {
        type: "code_result",
        id: "srvtoolu_1",
        stdout: "412.50\n",
        stderr: "",
        return_code: 0,
      },
      { type: "done" },
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeReadableStream(body),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.codeStarts).toEqual([
      { id: "srvtoolu_1", command: "print(total)" },
    ]);
    expect(cb.codeResults).toEqual([
      { id: "srvtoolu_1", stdout: "412.50\n", stderr: "", returnCode: 0 },
    ]);
    expect(cb.doneCount).toBe(1);
  });

  it("handles error events", async () => {
    const body = makeSSEBody([
      {
        type: "error",
        code: "MAX_ROUNDS_EXCEEDED",
        message: "Too many rounds",
      },
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeReadableStream(body),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.errors).toEqual([
      { code: "MAX_ROUNDS_EXCEEDED", message: "Too many rounds" },
    ]);
  });

  it("handles HTTP error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: () =>
          Promise.resolve({
            error: { code: "CHAT_UNAVAILABLE", message: "No API key" },
          }),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.errors).toEqual([
      { code: "CHAT_UNAVAILABLE", message: "No API key" },
    ]);
  });

  it("fires STREAM_ENDED when stream closes without terminal event", async () => {
    const body = makeSSEBody([{ type: "token", text: "partial" }]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeReadableStream(body),
      }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.errors).toEqual([
      {
        code: "STREAM_ENDED",
        message: expect.stringContaining("unexpectedly"),
      },
    ]);
  });

  it("handles chunked SSE data split across reads", async () => {
    const encoder = new TextEncoder();
    const event1 = 'data: {"type":"token","text":"Hel"}\n\n';
    const event2 =
      'data: {"type":"token","text":"lo"}\n\ndata: {"type":"done"}\n\n';

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(event1));
        controller.enqueue(encoder.encode(event2));
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: stream }),
    );

    const cb = makeCallbacks();
    await sendChatMessage([], cb, new AbortController().signal);

    expect(cb.tokens).toEqual(["Hel", "lo"]);
    expect(cb.doneCount).toBe(1);
  });
});
