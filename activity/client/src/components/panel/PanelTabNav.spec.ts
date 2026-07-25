import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PanelTabNav from "./PanelTabNav.vue";

describe("PanelTabNav", () => {
  it("exposes a tablist and emits the selected tab", async () => {
    const wrapper = mount(PanelTabNav, {
      props: {
        ariaLabel: "Panel sections",
        modelValue: "general",
        tabs: [
          { key: "general", label: "General" },
          { key: "roles", label: "Roles" },
        ],
      },
    });

    expect(wrapper.get('[role="tablist"]').attributes("aria-label")).toBe("Panel sections");
    const rolesTab = wrapper.get('[role="tab"][aria-selected="false"]');
    await rolesTab.trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([["roles"]]);
  });
});
