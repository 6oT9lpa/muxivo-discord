import { describe, expect, it } from "vitest";
import { parseLogEmbed } from "./logPresentation";

describe("parseLogEmbed", () => {
  it("parses serialized Discord audit embeds", () => {
    const embed = parseLogEmbed(JSON.stringify({
      content: "за минет",
      title: "Сообщение удалено (ID: 123)",
      fields: [{ name: "Автор", value: "arnetik", inline: false }],
      footer: { text: "Время: 12:49" },
    }));

    expect(embed).toMatchObject({
      content: "за минет",
      title: "Сообщение удалено (ID: 123)",
      footer: "Время: 12:49",
      fields: [{ name: "Автор", value: "arnetik", inline: false }],
    });
  });

  it("returns null for ordinary scalar details", () => {
    expect(parseLogEmbed({ reason: "manual" })).toBeNull();
  });
});
