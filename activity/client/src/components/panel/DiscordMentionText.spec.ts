import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import DiscordMentionText from "./DiscordMentionText.vue";

describe("DiscordMentionText", () => {
  it("renders Discord user mentions as readable mention chips", () => {
    const wrapper = mount(DiscordMentionText, {
      props: { text: "<@856864404615987200> (`.arnetik` ID: 856864404615987200) removed a message" },
    });

    expect(wrapper.get(".discord-mention").text()).toBe("@.arnetik");
    expect(wrapper.text()).not.toContain("<@856864404615987200>");
  });
});
