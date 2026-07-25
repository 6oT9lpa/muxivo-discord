import disnake

from application.services.moderation_labeling_service import ModerationLabelingService
from presentation.embeds.base import DEFAULT_COLORS, EmbedBuilder


class LabelingGuildSelectionView(disnake.ui.View):
    _PAGE_SIZE = 25

    def __init__(self, service: ModerationLabelingService, actor_id: int, guilds: list[disnake.Guild]) -> None:
        super().__init__(timeout=180)
        self._service = service
        self._actor_id = actor_id
        self._guilds = guilds
        self._page = 0
        self._select = disnake.ui.StringSelect(custom_id=f"labeling:guild:{actor_id}:0", placeholder="Select a server", options=[])
        self._select.callback = self._on_select
        self._previous = disnake.ui.Button(label="Previous", style=disnake.ButtonStyle.secondary, custom_id=f"labeling:previous:{actor_id}")
        self._next = disnake.ui.Button(label="Next", style=disnake.ButtonStyle.secondary, custom_id=f"labeling:next:{actor_id}")
        self._previous.callback = self._on_previous
        self._next.callback = self._on_next
        self.add_item(self._select)
        self.add_item(self._previous)
        self.add_item(self._next)
        self._refresh_components()

    @property
    def page_count(self) -> int:
        return max(1, (len(self._guilds) + self._PAGE_SIZE - 1) // self._PAGE_SIZE)

    def build_embed(self) -> disnake.Embed:
        return EmbedBuilder(color=DEFAULT_COLORS["info"]).set_title("Labeling server management").set_description(f"Select a server to inspect its labeling status and assignments. Page {self._page + 1}/{self.page_count}.").build()

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.author.id == self._actor_id:
            return True
        await interaction.response.send_message(embed=self._error_embed("This management menu belongs to another user."), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    async def _on_previous(self, interaction: disnake.MessageInteraction) -> None:
        self._page = max(0, self._page - 1)
        await self._render_page(interaction)

    async def _on_next(self, interaction: disnake.MessageInteraction) -> None:
        self._page = min(self.page_count - 1, self._page + 1)
        await self._render_page(interaction)

    async def _on_select(self, interaction: disnake.MessageInteraction) -> None:
        guild_id = int(self._select.values[0])
        guild = next((item for item in self._guilds if item.id == guild_id), None)
        if guild is None:
            await interaction.response.send_message(embed=self._error_embed("The selected server is no longer available."), ephemeral=True)
            return
        try:
            trusted, assignments = await self._service.get_guild_summary(self._actor_id, guild_id)
        except PermissionError:
            await interaction.response.send_message(embed=self._error_embed("You cannot inspect this server."), ephemeral=True)
            return
        administrators = [f"<@{row['user_id']}>" for row in assignments if row["role"] == "ADMIN"]
        labelers = [f"<@{row['user_id']}>" for row in assignments if row["role"] == "LABELER"]
        owner_id = getattr(guild, "owner_id", None)
        embed = (EmbedBuilder(color=DEFAULT_COLORS["success"] if trusted else DEFAULT_COLORS["warning"]).set_title("Labeling server details").set_description(guild.name).add_field("Guild ID", str(guild.id), inline=True).add_field("Owner", f"<@{owner_id}>" if owner_id else "Unknown", inline=True).add_field("Trusted", "Yes" if trusted else "No", inline=True).add_field("Administrators", ", ".join(administrators) or "None", inline=False).add_field("Labelers", ", ".join(labelers) or "None", inline=False).build())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _render_page(self, interaction: disnake.MessageInteraction) -> None:
        self._refresh_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def _refresh_components(self) -> None:
        start = self._page * self._PAGE_SIZE
        page = self._guilds[start:start + self._PAGE_SIZE]
        self._select.options = [disnake.SelectOption(label=guild.name[:100], value=str(guild.id), description=f"ID: {guild.id}") for guild in page] or [disnake.SelectOption(label="No available servers", value="0")]
        self._select.disabled = not page
        self._select.custom_id = f"labeling:guild:{self._actor_id}:{self._page}"
        self._previous.disabled = self._page == 0
        self._next.disabled = self._page >= self.page_count - 1

    @staticmethod
    def _error_embed(description: str) -> disnake.Embed:
        return EmbedBuilder(color=DEFAULT_COLORS["moderation"]).set_title("Labeling access denied").set_description(description).build()
