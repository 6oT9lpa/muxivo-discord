import { describe, expect, it } from "vitest";

import { consoleUrl } from "./consoleUrl";

describe("consoleUrl", () => {
  it("accepts a configured HTTPS Console URL without adding Activity context", () => {
    expect(consoleUrl("https://console.muxivo.example/sign-in", false)).toBe(
      "https://console.muxivo.example/sign-in",
    );
  });

  it("rejects credentials, malformed URLs and insecure production URLs", () => {
    expect(consoleUrl("https://token@console.muxivo.example", false)).toBeNull();
    expect(consoleUrl("not a url", false)).toBeNull();
    expect(consoleUrl("http://console.muxivo.example", false)).toBeNull();
  });

  it("permits HTTP only when explicitly requested for local development", () => {
    expect(consoleUrl("http://localhost:5173", true)).toBe("http://localhost:5173/");
  });
});
