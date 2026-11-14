import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON body. */
  json?: unknown;
  /** Multipart body (file uploads). */
  form?: FormData;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
};

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : String(d)))
      .join("; ");
  }
  return "Something went wrong";
}

/** Call the Heimdall API as the signed-in user. Throws `ApiError` with the server's message. */
export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { data } = await supabase().auth.getSession();
  const headers: Record<string, string> = {};
  if (data.session) headers.Authorization = `Bearer ${data.session.access_token}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      signal: options.signal,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the Heimdall API. Is the backend running?");
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      message = describe((await response.json()).detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
