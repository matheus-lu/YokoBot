# ============================================================
#  COG: BOAS-VINDAS E SAÍDA — Ondrakos  水の竜
#  Usando Components V2 (discord.py 2.6+)
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands
from utils import gerar_imagem_boas_vindas
import config

ONDRAKOS_COLOR = discord.Color.from_rgb(31, 139, 76)


# ── Layout V2 de Entrada ───────────────────────────────────
class EntradaLayout(discord.ui.LayoutView):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        count = len([m for m in member.guild.members if not m.bot])
        self._container = discord.ui.Container(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem("attachment://boasvindas.png"),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                "🐉 " + member.mention + " | Um novo espírito chegou ao santuário!\n"
                "Agora somos **" + str(count) + "** membros protegidos pelo dragão.\n\n"
                "🕍 Explore os canais e sinta-se em casa entre dragões, mistérios e boas conversas.\n"
                "Que sua presença traga boas energias ao clã."
            ),
            accent_color=ONDRAKOS_COLOR,
        )
        self.add_item(self._container)


# ── Layout V2 de Saída ─────────────────────────────────────
class SaidaLayout(discord.ui.LayoutView):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        count = len([m for m in member.guild.members if not m.bot])
        self._container = discord.ui.Container(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem("attachment://saida.png"),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                "🌙 Saída - Adeus\n\n"
                "🌫️ Um espírito deixou o santuário…\n\n"
                + member.mention + " seguiu seu próprio caminho além do portal.\n"
                "Que os ventos do dragão guiem seus passos, onde quer que vá.\n\n"
                "Agora somos **" + str(count) + "** membros protegidos pelo dragão."
            ),
            accent_color=ONDRAKOS_COLOR,
        )
        self.add_item(self._container)


class BoasVindasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Contador de membros com emojis de números ──────────
    _ultimo_contador = {}

    async def atualizar_contador(self, guild):
        canal = self.bot.get_channel(config.CONTADOR_MEMBROS_CANAL_ID())
        if not canal:
            return

        membros_humanos = len([m for m in guild.members if not m.bot])

        if self._ultimo_contador.get(guild.id) == membros_humanos:
            return
        self._ultimo_contador[guild.id] = membros_humanos

        emoji_numeros = {
            "0": "<:0_:1507462391053422674>",
            "1": "<:1_:1507462414701166822>",
            "2": "<:2_:1507462434737094696>",
            "3": "<:3_:1507462459156594738>",
            "4": "<:4_:1507462497307856916>",
            "5": "<:5_:1507462526374248448>",
            "6": "<:6_:1507462550151889016>",
            "7": "<:7_:1507462578287411382>",
            "8": "<:8_:1507462608767418378>",
            "9": "<:9_:1507462635472293898>",
        }

        DRAGAO = "<:dragaozinho:1507462355531993148>"
        ZERO   = "<:0_:1507462391053422674>"

        digitos = [emoji_numeros[d] for d in str(membros_humanos)]

        if membros_humanos <= 9:
            texto_emoji = DRAGAO + " " + ZERO + " " + digitos[0]
        else:
            texto_emoji = DRAGAO + " " + " ".join(digitos)

        try:
            await canal.edit(topic=texto_emoji)
        except Exception as e:
            print("Erro ao atualizar contador: " + str(e))

    # ── Entrada ────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.atualizar_contador(member.guild)
        if member.bot:
            return
        canal = self.bot.get_channel(config.BOAS_VINDAS_CANAL_ID())
        if not canal:
            return
        try:
            avatar_bytes = await member.display_avatar.read()
            buf = gerar_imagem_boas_vindas(member.display_name, avatar_bytes, entrou=True)
            arquivo = discord.File(buf, filename="boasvindas.png")
            await canal.send(file=arquivo, view=EntradaLayout(member))
        except Exception as e:
            print("Erro boas-vindas: " + str(e))

    # ── Saída ──────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.atualizar_contador(member.guild)
        if member.bot:
            return
        canal = self.bot.get_channel(config.SAIDA_CANAL_ID())
        if not canal:
            return
        try:
            avatar_bytes = await member.display_avatar.read()
            buf = gerar_imagem_boas_vindas(member.display_name, avatar_bytes, entrou=False)
            arquivo = discord.File(buf, filename="saida.png")
            await canal.send(file=arquivo, view=SaidaLayout(member))
        except Exception as e:
            print("Erro saida: " + str(e))


async def setup(bot):
    await bot.add_cog(BoasVindasCog(bot))