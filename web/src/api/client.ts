export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, string>;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, string>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function customFetch<T>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, init);

  if (response.status === 204) {
    return { data: undefined, status: 204, headers: response.headers } as T;
  }

  const body = await response.json();

  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "UNKNOWN_ERROR",
      error?.message ?? "An unknown error occurred",
      error?.details,
    );
  }

  return {
    data: body,
    status: response.status,
    headers: response.headers,
  } as T;
}
