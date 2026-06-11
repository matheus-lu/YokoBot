# ============================================================
#  COG: VERIFICAÇÃO - Sistema anti-bot com captcha - Ondrakos
#  Captcha: clicar no emoji certo entre 4 opções
# ============================================================

import discord
from discord.ext import commands
from discord.ui import View, Button
try:
    from discord import app_commands
except ImportError:
    from types import SimpleNamespace
    def _noop_decorator(*a, **kw):
        if len(a) == 1 and callable(a[0]): return a[0]
        return lambda f: f
    class _FakeAppCommands:
        def __getattr__(self, name): return _noop_decorator
        class checks:
            @staticmethod
            def has_permissions(**kw): return lambda f: f
        AppCommandError = Exception
        command = staticmethod(_noop_decorator)
    app_commands = _FakeAppCommands()
import random
import os
import config

DORORO_COLOR     = discord.Color.from_rgb(31, 139, 76)
CARGO_VERIFICADO = 1511225573655973958
CANAL_REGRAS     = 1480660903363084318

EMOJI_POOL = [
    "🐉", "🔮", "⛩️", "🌙", "🌸", "🍃", "🦊", "🐺",
    "🌊", "🔥", "⚡", "🌿", "🦋", "🐍", "🌺", "🦅",
    "🍀", "🌟", "🐯", "🦁", "🐲", "🌙", "🍁", "🎋",
]


def gerar_captcha():
    escolhidos = random.sample(EMOJI_POOL, 4)
    correto = random.choice(escolhidos)
    return escolhidos, correto


# ── View de Captcha (ephemeral, não persistente) ───────────
class CaptchaView(View):
    def __init__(self, emojis: list, correto: str, member: discord.Member):
        super().__init__(timeout=60)
        self.correto = correto
        self.member  = member
        self.encerrado = False

        for emoji in emojis:
            btn = Button(
                label=emoji,
                style=discord.ButtonStyle.secondary,
                custom_id=f"captcha_{emoji}_{member.id}",
            )
            btn.callback = self._fazer_callback(emoji)
            self.add_item(btn)

    def _fazer_callback(self, emoji: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message("Este captcha não é seu!", ephemeral=True)
                return
            if self.encerrado:
                await interaction.response.send_message("Este captcha já foi respondido.", ephemeral=True)
                return

            self.encerrado = True
            self.stop()

            if emoji == self.correto:
                guild = interaction.guild
                cargo = guild.get_role(CARGO_VERIFICADO)
                if cargo:
                    try:
                        await self.member.add_roles(cargo, reason="Verificação anti-bot")
                    except discord.Forbidden:
                        print(f"[Verificação] ⚠️  Sem permissão para dar cargo a {self.member}")
                    except Exception as e:
                        print(f"[Verificação] Erro ao dar cargo: {e}")

                embed_ok = discord.Embed(
                    title="✅ Verificação concluída!",
                    description=(
                        "Bem-vindo(a) ao santuário, "
                        + self.member.display_name + "! 🐉\n"
                        "Você agora tem acesso completo ao servidor."
                    ),
                    color=DORORO_COLOR,
                )
                embed_ok.set_footer(text="© Ondrakos · 水の竜")
                await interaction.response.edit_message(embed=embed_ok, view=None)

                try:
                    embed_dm = discord.Embed(
                        title="🐉 Verificação concluída - Ondrakos",
                        description=(
                            "Olá, **" + self.member.display_name + "**!\n\n"
                            "Você foi verificado(a) com sucesso no servidor **Ondrakos**.\n"
                            "O dragão reconheceu sua presença e abriu os portais para você. ⛩️\n\n"
                            "Explore os canais, participe da comunidade e escreva sua jornada entre nós!"
                        ),
                        color=DORORO_COLOR,
                    )
                    embed_dm.set_footer(text="© Ondrakos · 水の竜")
                    await self.member.send(embed=embed_dm)
                except discord.Forbidden:
                    pass
            else:
                embed_err = discord.Embed(
                    title="❌ Resposta incorreta!",
                    description="Você clicou no emoji errado. Tente novamente clicando em **Iniciar Verificação**.",
                    color=discord.Color.red(),
                )
                embed_err.set_footer(text="© Ondrakos · 水の竜")
                await interaction.response.edit_message(embed=embed_err, view=None)

        return callback

    async def on_timeout(self):
        self.encerrado = True
        self.stop()


# ── Botão de verificação como classe separada ──────────────
class BotaoVerificacao(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Iniciar Verificação",
            style=discord.ButtonStyle.success,
            emoji="🔰",
            custom_id="verificacao_iniciar",
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        guild  = interaction.guild

        cargo = guild.get_role(CARGO_VERIFICADO)
        if cargo and cargo in member.roles:
            await interaction.response.send_message("✅ Você já está verificado!", ephemeral=True)
            return

        emojis, correto = gerar_captcha()
        random.shuffle(emojis)

        embed_captcha = discord.Embed(
            title="🔐 Verificação Anti-Bot",
            description=(
                "Para confirmar que você é humano, clique no emoji abaixo:\n\n"
                "# " + correto + "\n\n"
                "Você tem **60 segundos** para responder."
            ),
            color=DORORO_COLOR,
        )
        embed_captcha.set_footer(text="© Ondrakos · 水の竜 · Apenas uma tentativa por vez")

        view_captcha = CaptchaView(emojis=emojis, correto=correto, member=member)
        await interaction.response.send_message(embed=embed_captcha, view=view_captcha, ephemeral=True)


# ── Layout V2 do embed de verificação ─────────────────────
TITULO_VER = "**🛡️ │▸Ondrakos › Verificação**"
DESCRICAO_VER = (
    "🔒 ⧽ Para confirmar que você é humano, clique no botão abaixo e siga as instruções.\n\n"
    "**Ao se verificar:**\n"
    "• Você confirma estar ciente das regras do servidor\n"
    "• Você concorda em seguir as diretrizes da comunidade\n\n"
    "⚠️ ⧽ Você não terá acesso a alguns recursos do servidor sem concluir a verificação."
)
FOOTER_VER = "-# © Ondrakos · 水の竜 · O dragão guarda o portal."


class VerificacaoLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container = discord.ui.Container(
        discord.ui.TextDisplay(TITULO_VER),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(DESCRICAO_VER),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem("attachment://verificar.png"),
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.Section(
            discord.ui.TextDisplay(FOOTER_VER),
            accessory=BotaoVerificacao(),
        ),
        accent_color=DORORO_COLOR,
    )


# ── Setup automático ───────────────────────────────────────
async def setup_verificacao_embed(bot):
    import os as _os
    CANAL_VERIFICACAO_ID = 1484792878579581009
    canal_ver = bot.get_channel(CANAL_VERIFICACAO_ID)
    if not canal_ver:
        print("[Verificação] ⚠️  Canal não encontrado.")
        return

    # Verificar se já existe — procura mensagem do bot com components (V2) ou embed com botão (legado)
    async for msg in canal_ver.history(limit=30):
        if msg.author != bot.user:
            continue
        if msg.components:
            for row in msg.components:
                for comp in getattr(row, "children", [row]):
                    if getattr(comp, "custom_id", None) == "verificacao_iniciar":
                        print("✅ Embed de verificação já existe, mantendo.")
                        return

    img_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "verificar.png")
    if _os.path.exists(img_path):
        await canal_ver.send(view=VerificacaoLayout(), files=[discord.File(img_path, filename="verificar.png")])
    else:
        layout = VerificacaoLayout()
        layout.container.children[0] = discord.ui.TextDisplay("")
        await canal_ver.send(view=layout)
    print("✅ Embed de verificação criado!")


# ── Cog Principal ──────────────────────────────────────────
class VerificacaoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(VerificacaoLayout())

    @app_commands.command(name="setup-verificacao", description="Criar o embed de verificação no canal atual")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_verificacao(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verificar.png")
        if os.path.exists(img_path):
            await interaction.channel.send(
                view=VerificacaoLayout(),
                files=[discord.File(img_path, filename="verificar.png")]
            )
        else:
            await interaction.channel.send(view=VerificacaoLayout())
        await interaction.followup.send("✅ Embed de verificação criado!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(VerificacaoCog(bot))