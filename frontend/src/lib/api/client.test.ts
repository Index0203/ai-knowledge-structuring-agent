import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveApiBaseUrl } from "./client";

function openPageOn(hostname: string, protocol = "http:"): void {
  vi.stubGlobal("location", { hostname, protocol });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("resolveApiBaseUrl", () => {
  it("keeps localhost when the page is opened locally", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    openPageOn("localhost");

    expect(resolveApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("talks to the API on the same host when the page is opened over the LAN", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    openPageOn("192.168.1.10");

    expect(resolveApiBaseUrl()).toBe("http://192.168.1.10:8000");
  });

  it("keeps the port the API was configured with", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:18000");
    openPageOn("10.141.82.65");

    expect(resolveApiBaseUrl()).toBe("http://10.141.82.65:18000");
  });

  it("falls back to localhost when nothing is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    openPageOn("localhost");

    expect(resolveApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("respects an explicitly configured remote API", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com");
    openPageOn("192.168.1.10");

    expect(resolveApiBaseUrl()).toBe("https://api.example.com");
  });
});
