import { describe, expect, it } from "vitest";

import { isDiscordActivityLaunch } from "./launchContext";

describe("isDiscordActivityLaunch", () => {
  it("accepts Discord frame launches", () => {
    expect(isDiscordActivityLaunch("?frame_id=frame-1")).toBe(true);
  });

  it("accepts Discord instance launches", () => {
    expect(isDiscordActivityLaunch("?instance_id=instance-1")).toBe(true);
  });

  it("keeps ordinary browser visits outside the Discord Activity trust path", () => {
    expect(isDiscordActivityLaunch("")).toBe(false);
    expect(isDiscordActivityLaunch("?guild_id=123")).toBe(false);
    expect(isDiscordActivityLaunch("?redirect=frame_id%3Dfake")).toBe(false);
  });
});
