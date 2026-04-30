/**
 * @fileoverview Base HTTP client and query serialization helpers.
 */

type QueryValue = string | number | boolean | undefined | null;
type QueryParams = Record<string, QueryValue>;

/**
 * Utility to serialize an object into URL search parameters, ignoring null/undefined values.
 */
function serializeQuery(params: QueryParams) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    search.set(key, String(value));
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

/**
 * A generic HTTP client wrapper around the browser fetch API.
 * Handles common tasks like error checking, JSON parsing, and query serialization.
 */
export class HttpClient {
  private readonly fetcher: typeof fetch;

  public constructor(fetcher: typeof fetch = fetch) {
    this.fetcher = typeof window !== "undefined" ? fetcher.bind(window) : fetcher;
  }

  private async request(path: string, options: RequestInit): Promise<Response> {
    const response = await this.fetcher(path, options);
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response;
  }

  /** Makes a GET request and parses the JSON response. */
  public async get<T>(path: string, query: QueryParams = {}): Promise<T> {
    const response = await this.request(`${path}${serializeQuery(query)}`, { method: "GET" });
    return response.json() as Promise<T>;
  }

  /** Makes a GET request but safely returns null if the server responds with a 404. */
  public async getOrNullOnNotFound<T>(path: string, query: QueryParams = {}): Promise<T | null> {
    const response = await this.fetcher(`${path}${serializeQuery(query)}`, {
      method: "GET",
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }

    return response.json() as Promise<T>;
  }

  /** Makes a POST request with a JSON body. */
  public async post<T>(path: string, body: unknown): Promise<T> {
    const response = await this.request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return response.json() as Promise<T>;
  }

  /** Makes a PUT request with a JSON body. */
  public async put<T>(path: string, body: unknown): Promise<T> {
    const response = await this.request(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return response.json() as Promise<T>;
  }

  /** Makes a DELETE request. */
  public async delete<T>(path: string): Promise<T> {
    const response = await this.request(path, { method: "DELETE" });
    return response.json() as Promise<T>;
  }
}
