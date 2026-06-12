# ============================================================
#  COG: HISTÓRIAS — Registro de história via botão no fórum
#  Usando Components V2 (discord.py 2.6+)
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands

# ── IDs ────────────────────────────────────────────────────
CARGO_HISTORIA_ID = 1507789725547761871
FORUM_TOPICO_ID = 1514918760190836798

# ── Cores ──────────────────────────────────────────────────
COR_CONTAINER = discord.Color.from_rgb(31, 139, 76)

# ── Textos — EDITE AQUI ────────────────────────────────────
TITULO = "**🎣📜 |▸Acesso ao Fórum de Histórias◂| 🐉✨**"
DESCRICAO = (
    "Para publicar a história do seu personagem no **Santuário de Ondrakos**, "
    "clique no botão abaixo:\n\n"
    "Ao clicar em 📖, você receberá acesso ao fórum de histórias, "
    "onde poderá criar sua própria postagem e contar a jornada do seu personagem.\n\n"
    "Nesse espaço, você poderá apresentar:\n\n"
    "🌊 ⧽ A origem do personagem\n"
    "🐉 ⧽ Sua raça ou natureza sobrenatural\n"
    "🧭 ⧽ Sua personalidade e motivações\n"
    "🔥 ⧽ Seus poderes, habilidades e fraquezas\n"
    "⚔️ ⧽ Seus conflitos, alianças e inimigos\n"
    "🌙 ⧽ Seu passado, segredos e destino\n"
    "📖 ⧽ Tudo que ajude a construir sua lenda dentro do servidor\n\n"
    "Use esse fórum para dar vida ao seu personagem, registrar sua história "
    "e deixar sua marca no santuário.\n\n"
    "✨ *Toda lenda começa com uma história.* ✨"
)
FOOTER = "© Ondrakos · 水の竜"
BOTAO_LABEL = "Pescador"
BOTAO_EMOJI = discord.PartialEmoji(name="_Lorebook", id=1514282991415853217)


# ── Botão como classe separada pra usar como accessory ─────
class BotaoRegistrar(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label=BOTAO_LABEL,
            emoji=BOTAO_EMOJI,
            style=discord.ButtonStyle.primary,
            custom_id="historia_registrar",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cargo = interaction.guild.get_role(CARGO_HISTORIA_ID)
        if not cargo:
            await interaction.followup.send("❌ Cargo não encontrado. Avise a staff!", ephemeral=True)
            return

        if cargo in interaction.user.roles:
            await interaction.followup.send(
                "🌊 Você já está registrado(a) e pode criar sua história no fórum!",
                ephemeral=True,
            )
            return

        try:
            await interaction.user.add_roles(cargo, reason="Registro de história via botão")
            await interaction.followup.send(
                "✅ Bem-vindo(a)! Você agora pode criar sua história no fórum. 🌊",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Não tenho permissão para dar este cargo. Avise a staff!", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send("❌ Erro ao registrar: " + str(e), ephemeral=True)


# ── Layout V2 — Imagem em cima ────────────────────────────
class HistoriaLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container = discord.ui.Container(
        discord.ui.MediaGallery(
            discord.MediaGalleryItem("attachment://pescador.png"),
        ),
        discord.ui.TextDisplay(TITULO),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(DESCRICAO),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.Section(
            discord.ui.TextDisplay(FOOTER),
            accessory=BotaoRegistrar(),
        ),
        accent_color=COR_CONTAINER,
    )


# ── Layout V2 — Imagem embaixo ────────────────────────────
class HistoriaLayoutImagemBaixo(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container = discord.ui.Container(
        discord.ui.TextDisplay(TITULO),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(DESCRICAO),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem("attachment://pescador.png"),
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.Section(
            discord.ui.TextDisplay(FOOTER),
            accessory=BotaoRegistrar(),
        ),
        accent_color=COR_CONTAINER,
    )


# ── Setup automático ───────────────────────────────────────
async def setup_historias_embed(bot):
    canal = bot.get_channel(FORUM_TOPICO_ID)
    if not canal:
        print("⚠️ Tópico de histórias não encontrado! ID: " + str(FORUM_TOPICO_ID))
        return

    async for msg in canal.history(limit=20):
        if msg.author == bot.user and msg.components:
            print("✅ Embed de histórias já existe, mantendo.")
            return

    try:
        arquivo = discord.File("pescador.png", filename="pescador.png")
        await canal.send(view=HistoriaLayout(), files=[arquivo])
    except FileNotFoundError:
        layout = HistoriaLayout()
        layout.container.children[0] = discord.ui.TextDisplay("")
        await canal.send(view=layout)
    print("✅ Embed de histórias criado!")


# ── Cog Principal ──────────────────────────────────────────
class HistoriasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(HistoriaLayout())
        bot.add_view(HistoriaLayoutImagemBaixo())

    @app_commands.command(name="setup_historias", description="Reenviar embed de registro de histórias")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_historias(self, interaction: discord.Interaction):
        try:
            arquivo = discord.File("pescador.png", filename="pescador.png")
            await interaction.channel.send(view=HistoriaLayout(), files=[arquivo])
        except FileNotFoundError:
            await interaction.channel.send(view=HistoriaLayout())
        await interaction.response.send_message("✅ Embed enviado!", ephemeral=True)

    @app_commands.command(name="comparar_historias", description="Envia as duas versões do embed para comparação")
    @app_commands.checks.has_permissions(administrator=True)
    async def comparar_historias(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            arquivo1 = discord.File("pescador.png", filename="pescador.png")
            await interaction.channel.send(files=[arquivo1], view=HistoriaLayout())
            arquivo2 = discord.File("pescador.png", filename="pescador.png")
            await interaction.channel.send(files=[arquivo2], view=HistoriaLayoutImagemBaixo())
        except FileNotFoundError:
            await interaction.channel.send(view=HistoriaLayout())
            await interaction.channel.send(view=HistoriaLayoutImagemBaixo())
        await interaction.followup.send("✅ Duas versões enviadas!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(HistoriasCog(bot))