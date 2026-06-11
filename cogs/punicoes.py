# ============================================================
#  COG: PUNIÇÕES — Ban, unban, kick, mute, aviso — Ondrakos
# ============================================================

import discord
from discord.ext import commands
try:
    from discord import app_commands
except ImportError:
    from types import SimpleNamespace
    def _noop_decorator(*a, **kw):
        # Retorna o proprio objeto se chamado como decorator
        if len(a) == 1 and callable(a[0]):
            return a[0]
        return lambda f: f
    class _FakeAppCommands:
        def __getattr__(self, name):
            return _noop_decorator
        class checks:
            @staticmethod
            def has_permissions(**kw):
                return lambda f: f
        class errors:
            MissingPermissions = Exception
            CommandOnCooldown = Exception
        AppCommandError = Exception
        command = staticmethod(_noop_decorator)
    app_commands = _FakeAppCommands()
import config

DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)


class PunicoesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def enviar_punicao(self, descricao, cor, mention):
        canal = self.bot.get_channel(config.PUNICOES_CANAL_ID())
        if not canal:
            return
        embed = discord.Embed(description=mention + " " + descricao, color=cor)
        msg = await canal.send(embed=embed)
        await msg.add_reaction("⭐")

    # ── Comandos ───────────────────────────────────────────
    @app_commands.command(name="aviso", description="Dar aviso a um membro")
    @app_commands.checks.has_permissions(administrator=True)
    async def aviso(self, interaction: discord.Interaction, member: discord.Member, motivo: str = "Sem motivo informado"):
        await self.enviar_punicao(
            f"⚠️ recebeu um aviso da equipe.\n**Motivo:** {motivo}",
            discord.Color.yellow(), member.mention,
        )
        await interaction.response.send_message("✅ Aviso enviado!", ephemeral=True)

    @app_commands.command(name="removeaviso", description="Remover aviso")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeaviso(self, interaction: discord.Interaction, member: discord.Member):
        await self.enviar_punicao(
            "✅ teve seu aviso removido pela equipe.\nContinue contribuindo com responsabilidade.",
            discord.Color.green(), member.mention,
        )
        await interaction.response.send_message("✅ Aviso removido!", ephemeral=True)

    # ── Eventos automáticos ────────────────────────────────
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        canal = self.bot.get_channel(config.PUNICOES_CANAL_ID())
        if not canal:
            return
        embed = discord.Embed(
            description=user.mention + " 🐉 foi expulso das terras do dragão.\nAs chamas decidiram que sua jornada termina aqui.",
            color=discord.Color.red()
        )
        import os as _os
        ban_img = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'imagem_ban.png')
        ban_img = _os.path.normpath(ban_img)
        if _os.path.exists(ban_img):
            embed.set_image(url="attachment://imagem_ban.png")
            msg = await canal.send(embed=embed, file=discord.File(ban_img, filename="imagem_ban.png"))
        else:
            msg = await canal.send(embed=embed)
        await msg.add_reaction("<:_negativo:1507462725159358597>")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        canal = self.bot.get_channel(config.PUNICOES_CANAL_ID())
        if not canal:
            return
        embed = discord.Embed(
            description=user.mention + " ✅ foi readmitido no servidor.\nAproveite sua nova chance.",
            color=discord.Color.green()
        )
        import os as _os
        pardon_img = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'pardon_image.png'))
        if _os.path.exists(pardon_img) and _os.path.getsize(pardon_img) < 9_000_000:
            embed.set_image(url="attachment://pardon_image.png")
            msg = await canal.send(embed=embed, file=discord.File(pardon_img, filename="pardon_image.png"))
        else:
            msg = await canal.send(embed=embed)
        await msg.add_reaction("<:_positivo:1507462699699929268>")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if getattr(before, "timed_out_until", None) != getattr(after, "timed_out_until", None):
            if after.timed_out_until:
                await self.enviar_punicao(
                    "🔇 foi silenciado.\nAguarde até que a equipe permita seu retorno.",
                    discord.Color.dark_orange(), after.mention,
                )
            else:
                await self.enviar_punicao(
                    "🔊 teve sua voz liberada.\nVocê pode voltar a se comunicar no servidor.",
                    discord.Color.teal(), after.mention,
                )

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        if entry.action == discord.AuditLogAction.kick:
            canal = self.bot.get_channel(config.PUNICOES_CANAL_ID())
            if not canal:
                return
            embed = discord.Embed(
                description=entry.target.mention + " 👢 foi expulso do servidor.\nAjuste seu comportamento antes de retornar.",
                color=discord.Color.orange()
            )
            import os as _os
            ban_img = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'imagem_ban.png'))
            if _os.path.exists(ban_img) and _os.path.getsize(ban_img) < 9_000_000:
                embed.set_image(url="attachment://imagem_ban.png")
                msg = await canal.send(embed=embed, file=discord.File(ban_img, filename="imagem_ban.png"))
            else:
                msg = await canal.send(embed=embed)
            await msg.add_reaction("⭐")


async def setup(bot):
    await bot.add_cog(PunicoesCog(bot))