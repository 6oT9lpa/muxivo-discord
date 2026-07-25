import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SearchableSelector from "./SearchableSelector.vue";

describe("SearchableSelector", () => {
  it("replaces the trigger with a search field and emits the selected value", async () => {
    const wrapper = mount(SearchableSelector, {
      props: {
        ariaLabel: "Users",
        emptyLabel: "No results",
        options: [
          { id: "1", label: "Niko", search: "niko 1" },
          { id: "2", label: "Luna", search: "luna 2" },
        ],
        searchPlaceholder: "Search users",
        triggerLabel: "Choose a user",
      },
    });

    await wrapper.get(".searchable-selector-trigger").trigger("click");
    expect(wrapper.get('input[type="search"]').attributes("placeholder")).toBe("Search users");
    await wrapper.get('input[type="search"]').setValue("lun");
    await wrapper.get('[role="option"]').trigger("click");

    expect(wrapper.emitted("select")).toEqual([["2"]]);
    expect(wrapper.find('input[type="search"]').exists()).toBe(false);
  });
});
