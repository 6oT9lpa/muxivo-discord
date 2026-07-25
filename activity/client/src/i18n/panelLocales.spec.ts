import { afterEach, describe, expect, it } from "vitest";
import { setLocale, t } from "./index";

describe("panel locale coverage", () => {
  afterEach(() => setLocale("en"));

  it.each(["en", "ru"] as const)("translates the redesigned panel controls in %s", (locale) => {
    setLocale(locale);
    [
      "access.role_catalog",
      "logs.stream_heading",
      "settings.ai_test_heading",
      "review.heading",
      "review.save",
    ].forEach((key) => expect(t(key)).not.toBe(key));
  });
});
