import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import * as api from "../api/activity.api";
import type { EffectiveMediaPolicy } from "../types/activity.types";
import { useActivityStore } from "./activity.store";

const databasePolicy: EffectiveMediaPolicy = {
  platform: "discord",
  guild_id: "123",
  source: "DATABASE",
  schema_version: "1",
  defaults_version: "media-v1",
  revision: 4,
  updated_at: "2026-07-31T00:00:00Z",
  updated_by: "456",
  runtime: { ocr_enabled: true, ocr_ready: true, yolo_enabled: false, yolo_ready: false },
  media: {
    ocr: { version: "ocr-v1", ocr: { enabled: true } },
    yolo: { version: "yolo-v1", yolo: { enabled: false } },
  } as unknown as EffectiveMediaPolicy["media"],
};

const yamlPolicy: EffectiveMediaPolicy = {
  ...databasePolicy,
  source: "YAML_DEFAULT",
  revision: 0,
  updated_at: null,
  updated_by: null,
};

function readyStore() {
  const store = useActivityStore();
  store.$patch({
    mode: "discord",
    token: "token",
    session: { guild_id: "123" } as never,
    mediaPolicy: { ...databasePolicy },
  });
  return store;
}

describe("media policy store workflow", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("saves and accepts only the policy reloaded from the server", async () => {
    vi.spyOn(api, "saveMediaPolicy").mockResolvedValue(databasePolicy);
    vi.spyOn(api, "getMediaPolicy").mockResolvedValue(databasePolicy);
    const store = readyStore();

    await store.saveMediaPolicyValue(databasePolicy.media, 3);

    expect(api.saveMediaPolicy).toHaveBeenCalledWith("123", "token", 3, databasePolicy.media);
    expect(api.getMediaPolicy).toHaveBeenCalledWith("123", "token");
    expect(store.mediaPolicy?.revision).toBe(4);
  });

  it("resets and verifies the YAML fallback", async () => {
    vi.spyOn(api, "resetMediaPolicy").mockResolvedValue(yamlPolicy);
    vi.spyOn(api, "getMediaPolicy").mockResolvedValue(yamlPolicy);
    const store = readyStore();

    await store.resetMediaPolicyValue(4);

    expect(store.mediaPolicy?.source).toBe("YAML_DEFAULT");
  });

  it("does not mutate the active policy when save reports a revision conflict", async () => {
    vi.spyOn(api, "saveMediaPolicy").mockRejectedValue(new Error("409 conflict"));
    const store = readyStore();

    await expect(store.saveMediaPolicyValue(databasePolicy.media, 3)).rejects.toThrow("409 conflict");
    expect(store.mediaPolicy?.revision).toBe(4);
  });

  it("keeps the last verified policy when reload is unavailable", async () => {
    vi.spyOn(api, "getMediaPolicy").mockRejectedValue(new Error("503 unavailable"));
    const store = readyStore();

    await expect(store.reloadMediaPolicy()).rejects.toThrow("503 unavailable");
    expect(store.mediaPolicy?.revision).toBe(4);
  });
});
