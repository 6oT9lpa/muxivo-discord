import { flushPromises, mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setLocale } from "../../i18n";
import ModerationDemo from "./ModerationDemo.vue";

describe("ModerationDemo", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    setLocale("en");
  });

  it("submits a visitor message, renders the AI decision, then removes a violating message", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      risk_score: 92,
      action: "DELETE_WARN",
      primary_label: "HATE",
      labels: ["HATE", "TOXIC"],
      execution_plan: ["DELETE", "TIMEOUT"],
    }), { status: 200, headers: { "Content-Type": "application/json" } })));

    const wrapper = mount(ModerationDemo);
    await wrapper.get("input").setValue("Claim a prize using this suspicious link");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("AI check · HATE, TOXIC · risk 92% · DELETE_WARN · plan DELETE → TIMEOUT");

    expect(wrapper.text()).toContain("Policy violation: HATE, TOXIC · risk 92% · You have been timed out and cannot write in this demo.");
    expect(wrapper.get("input").attributes("disabled")).toBeDefined();

    await vi.advanceTimersByTimeAsync(900);
    expect(wrapper.text()).toContain("Message removed by Muxivo Discord policy.");
    wrapper.unmount();
  });

  it("keeps each live channel bounded and renders log embeds and the Dev Blog history", async () => {
    vi.useFakeTimers();
    const wrapper = mount(ModerationDemo);

    await vi.advanceTimersByTimeAsync(46_000);
    await nextTick();
    expect(wrapper.findAll(".demo-message")).toHaveLength(15);

    const channelButtons = wrapper.findAll(".demo-channel-button");
    await channelButtons[1].trigger("click");
    expect(wrapper.findAll(".demo-log-embed").length).toBeGreaterThan(0);

    await channelButtons[2].trigger("click");
    expect(wrapper.findAll(".demo-message.is-dev")).toHaveLength(10);
    wrapper.unmount();
  });

  it("rebuilds the simulated server in Russian after a locale change", async () => {
    setLocale("ru");
    const wrapper = mount(ModerationDemo);
    await nextTick();

    expect(wrapper.text()).toContain("Интерактивная AI-модерация");
    expect(wrapper.text()).toContain("классификатор подключён");
    expect(wrapper.text()).toContain("чат сообщества");
    wrapper.unmount();
  });
});
