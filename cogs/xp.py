# ============================================================
#  COG: XP — Sistema de níveis e ranking por digitação
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
import random
import asyncio
import datetime
import config


# Cooldown de XP por usuário
xp_cooldown = {}
XP_COOLDOWN_SEGUNDOS = 60
XP_POR_MENSAGEM_MIN = 15
XP_POR_MENSAGEM_MAX = 25


def xp_para_proximo_nivel(level: int) -> int:
    return 100 * (level + 1) ** 2


def gerar_barra_progresso(xp_atual: int, xp_necessario: int, tamanho: int = 10) -> str:
    progresso = min(xp_atual / xp_necessario, 1.0) if xp_necessario > 0 else 0
    preenchido = int(progresso * tamanho)
    vazio = tamanho - preenchido
    return "🟦" * preenchido + "⬛" * vazio


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atualizar_ranking_diario.start()

    def cog_unload(self):
        self.atualizar_ranking_diario.cancel()

    # ── Novo membro → registrar no XP ─────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        if hasattr(self.bot, 'db') and self.bot.db:
            await self.bot.db.registrar_membro(member.id, member.guild.id)

    # ── Membro saiu → remover do XP ───────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        if hasattr(self.bot, 'db') and self.bot.db:
            await self.bot.db.remover_membro_xp(member.id, member.guild.id)

    # ── Ganhar XP por mensagem ─────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id != config.CONTADOR_MEMBROS_CANAL_ID:
            return

        uid = message.author.id
        guild_id = message.guild.id
        agora = message.created_at.timestamp()

        chave = f"{uid}-{guild_id}"
        ultimo = xp_cooldown.get(chave, 0)
        if agora - ultimo < XP_COOLDOWN_SEGUNDOS:
            return
        xp_cooldown[chave] = agora

        if not hasattr(self.bot, 'db') or not self.bot.db:
            return

        quantidade = random.randint(XP_POR_MENSAGEM_MIN, XP_POR_MENSAGEM_MAX)
        resultado = await self.bot.db.add_xp(uid, guild_id, quantidade)

        if resultado["subiu"]:
            try:
                embed = discord.Embed(
                    title="🌊 Subiu de Nível!",
                    description=(
                        "🎉 " + message.author.mention + " alcançou o **nível "
                        + str(resultado["level"]) + "**!\n"
                        "Continue mergulhando nas profundezas!"
                    ),
                    color=discord.Color.dark_blue(),
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                await message.channel.send(embed=embed, delete_after=15)
            except Exception:
                pass

    # ── /nivel ─────────────────────────────────────────────
    @app_commands.command(name="nivel", description="Ver seu nível e XP")
    async def nivel(self, interaction: discord.Interaction, membro: discord.Member = None):
        alvo = membro or interaction.user
        if not hasattr(self.bot, 'db') or not self.bot.db:
            await interaction.response.send_message("❌ Banco de dados não disponível.", ephemeral=True)
            return

        dados = await self.bot.db.get_xp(alvo.id, interaction.guild.id)
        if not dados:
            await interaction.response.send_message(
                alvo.display_name + " ainda não tem XP registrado.", ephemeral=True
            )
            return

        xp = dados["xp"]
        level = dados["level"]
        mensagens = dados["mensagens"]
        xp_proximo = xp_para_proximo_nivel(level)
        xp_level_anterior = xp_para_proximo_nivel(level - 1) if level > 0 else 0
        xp_no_nivel = xp - xp_level_anterior
        xp_necessario_nivel = xp_proximo - xp_level_anterior

        barra = gerar_barra_progresso(xp_no_nivel, xp_necessario_nivel)

        pos_data = await self.bot.db.posicao_usuario(alvo.id, interaction.guild.id)
        posicao = pos_data["posicao"] if pos_data else "?"
        total = await self.bot.db.total_membros_xp(interaction.guild.id)

        embed = discord.Embed(
            title="🌊 Perfil de " + alvo.display_name,
            color=discord.Color.dark_blue(),
        )
        embed.set_thumbnail(url=alvo.display_avatar.url)
        embed.add_field(name="📊 Nível", value="**" + str(level) + "**", inline=True)
        embed.add_field(name="✨ XP Total", value="**" + str(xp) + "**", inline=True)
        embed.add_field(name="🏆 Ranking", value="**#" + str(posicao) + "** de " + str(total), inline=True)
        embed.add_field(
            name="📈 Progresso",
            value=barra + "\n" + str(xp_no_nivel) + " / " + str(xp_necessario_nivel) + " XP",
            inline=False,
        )
        embed.add_field(name="💬 Mensagens", value=str(mensagens), inline=True)
        embed.set_footer(text="© Ondrakos · 水の竜")

        await interaction.response.send_message(embed=embed)

    # ── /ranking ───────────────────────────────────────────
    @app_commands.command(name="ranking", description="Ver o ranking de XP do servidor")
    async def ranking(self, interaction: discord.Interaction):
        if not hasattr(self.bot, 'db') or not self.bot.db:
            await interaction.response.send_message("❌ Banco de dados não disponível.", ephemeral=True)
            return

        await interaction.response.defer()

        top = await self.bot.db.ranking_xp(interaction.guild.id, 10)
        total = await self.bot.db.total_membros_xp(interaction.guild.id)

        if not top:
            await interaction.followup.send("Ninguém no ranking ainda!")
            return

        medalhas = ["🥇", "🥈", "🥉"]
        linhas = []
        for i, r in enumerate(top):
            medalha = medalhas[i] if i < 3 else "**" + str(i + 1) + ".**"
            try:
                member = await interaction.guild.fetch_member(r["user_id"])
                nome = member.display_name
            except Exception:
                nome = "Usuário #" + str(r["user_id"])
            linhas.append(
                medalha + " " + nome
                + " — Nível **" + str(r["level"])
                + "** | " + str(r["xp"]) + " XP"
            )

        uid = interaction.user.id
        user_no_top = any(r["user_id"] == uid for r in top)

        if not user_no_top:
            pos_data = await self.bot.db.posicao_usuario(uid, interaction.guild.id)
            if pos_data:
                restantes = total - 10
                if restantes > 0:
                    linhas.append("\n*... e mais " + str(restantes) + " membros ...*")
                linhas.append(
                    "\n**" + str(pos_data["posicao"]) + ".** " + interaction.user.display_name
                    + " — Nível **" + str(pos_data["level"])
                    + "** | " + str(pos_data["xp"]) + " XP"
                )
        else:
            restantes = total - 10
            if restantes > 0:
                linhas.append("\n*... e mais " + str(restantes) + " membros no ranking*")

        embed = discord.Embed(
            title="🏆 Ranking — Ondrakos",
            description="\n".join(linhas),
            color=discord.Color.dark_blue(),
        )
        embed.set_footer(text="© Ondrakos · 水の竜 | " + str(total) + " membros | Ganhe XP conversando!")
        await interaction.followup.send(embed=embed)

    # ── /addxp ─────────────────────────────────────────────
    @app_commands.command(name="addxp", description="Adicionar XP a um membro")
    @app_commands.checks.has_permissions(administrator=True)
    async def addxp(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if not hasattr(self.bot, 'db') or not self.bot.db:
            await interaction.response.send_message("❌ Banco de dados não disponível.", ephemeral=True)
            return
        resultado = await self.bot.db.add_xp(membro.id, interaction.guild.id, quantidade)
        await interaction.response.send_message(
            "✅ " + str(quantidade) + " XP adicionados para " + membro.mention
            + "! (Total: " + str(resultado["xp"]) + " XP, Nível " + str(resultado["level"]) + ")",
            ephemeral=True,
        )

    # ── Ranking diário à meia-noite BRT ────────────────────
    @tasks.loop(hours=24)
    async def atualizar_ranking_diario(self):
        for guild in self.bot.guilds:
            if not hasattr(self.bot, 'db') or not self.bot.db:
                return
            top = await self.bot.db.ranking_xp(guild.id, 3)
            if not top:
                return

            medalhas = ["🥇", "🥈", "🥉"]
            linhas = []
            for i, r in enumerate(top):
                try:
                    member = await guild.fetch_member(r["user_id"])
                    nome = member.display_name
                except Exception:
                    nome = "Usuário #" + str(r["user_id"])
                linhas.append(
                    medalhas[i] + " " + nome
                    + " — Nível **" + str(r["level"])
                    + "** | " + str(r["xp"]) + " XP"
                )

            canal = self.bot.get_channel(config.CONTADOR_MEMBROS_CANAL_ID)
            if canal:
                embed = discord.Embed(
                    title="🏆 Pódio do Dia",
                    description="\n".join(linhas),
                    color=discord.Color.dark_blue(),
                )
                embed.set_footer(text="© Ondrakos · 水の竜 | Ranking atualizado à meia-noite BRT")
                await canal.send(embed=embed)

    @atualizar_ranking_diario.before_loop
    async def before_ranking(self):
        await self.bot.wait_until_ready()
        BRT = datetime.timezone(datetime.timedelta(hours=-3))
        agora_brt = datetime.datetime.now(BRT)
        amanha_brt = (agora_brt + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        espera = (amanha_brt - agora_brt).total_seconds()
        print(
            f"[XP] ⏳ Pódio agendado para {amanha_brt.strftime('%d/%m/%Y 00:00 BRT')} "
            f"(em {espera/3600:.1f}h)"
        )
        await asyncio.sleep(espera)


async def setup(bot):
    await bot.add_cog(XPCog(bot))