# ============================================================
#  COG: SETUP — Configuracao dinamica do Ondrakos Bot
# ============================================================

import discord
from discord.ext import commands
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
        class errors:
            MissingPermissions = Exception
            CommandOnCooldown  = Exception
        AppCommandError = Exception
        command = staticmethod(_noop_decorator)
    app_commands = _FakeAppCommands()

import config_dynamic as dyn

# Mapeamento de nomes amigaveis para chaves do dynamic.json
CANAIS = {
    "boas-vindas":       "BOAS_VINDAS_CANAL_ID",
    "saida":             "SAIDA_CANAL_ID",
    "logs":              "LOGS_CANAL_ID",
    "musica":            "MUSICA_CANAL_ID",
    "divulgacao":        "DIVULGACAO_CANAL_ID",
    "tickets":           "TICKET_CANAL_ID",
    "tickets-categoria": "TICKET_CATEGORY_ID",
    "tickets-fechados":  "TICKET_CLOSED_CATEGORY_ID",
    "ia":                "IA_CANAL_ID",
    "ia-categoria":      "IA_CATEGORIA_ID",
    "punicoes":          "PUNICOES_CANAL_ID",
    "contador":          "CONTADOR_CANAL_ID",
}

CARGOS = {
    "staff":        "STAFF_ROLE_ID",
    "staff-mencao": "STAFF_MENTION_ROLE_ID",
    "ia-dono":      "IA_PROPRIETARIO_ID",
    "ia-dev":       "IA_DEV_ID",
}


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /setup canal
    @app_commands.command(name="setup-canal", description="Configura um canal do bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_canal(self, interaction: discord.Interaction,
                          tipo: str, canal: discord.abc.GuildChannel):
        tipo = tipo.lower().strip()
        if tipo not in CANAIS:
            lista = ", ".join(CANAIS.keys())
            await interaction.response.send_message(
                f"Tipo invalido. Opcoes: `{lista}`", ephemeral=True)
            return
        dyn.set(CANAIS[tipo], canal.id)
        await interaction.response.send_message(
            f"Canal **{tipo}** definido como {canal.mention}!", ephemeral=True)

    # /setup cargo
    @app_commands.command(name="setup-cargo", description="Configura um cargo do bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_cargo(self, interaction: discord.Interaction,
                          tipo: str, cargo: discord.Role):
        tipo = tipo.lower().strip()
        if tipo not in CARGOS:
            lista = ", ".join(CARGOS.keys())
            await interaction.response.send_message(
                f"Tipo invalido. Opcoes: `{lista}`", ephemeral=True)
            return
        dyn.set(CARGOS[tipo], cargo.id)
        await interaction.response.send_message(
            f"Cargo **{tipo}** definido como {cargo.mention}!", ephemeral=True)

    # /setup api
    @app_commands.command(name="setup-api", description="Configura uma chave de API")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_api(self, interaction: discord.Interaction, tipo: str, chave: str):
        tipo = tipo.lower().strip()
        chaves = {"groq": "GROQ_API_KEY", "spotify-id": "SPOTIFY_CLIENT_ID",
                  "spotify-secret": "SPOTIFY_CLIENT_SECRET", "site": "SITE_URL",
                  "imagem": "IMAGEM_URL"}
        if tipo not in chaves:
            await interaction.response.send_message(
                f"Tipo invalido. Opcoes: `{', '.join(chaves.keys())}`", ephemeral=True)
            return
        dyn.set(chaves[tipo], chave)
        await interaction.response.send_message(
            f"API **{tipo}** configurada!", ephemeral=True)

    # /setup status
    @app_commands.command(name="setup-status", description="Ver configuracoes atuais")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_status(self, interaction: discord.Interaction):
        data = dyn.all_data()
        embed = discord.Embed(title="Configuracoes do Bot", color=discord.Color.from_rgb(31, 139, 76))

        canais_txt = []
        for nome, key in CANAIS.items():
            val = data.get(key, 0)
            canal = interaction.guild.get_channel(val) if val else None
            canais_txt.append(f"`{nome}`: {canal.mention if canal else '❌ nao configurado'}")
        embed.add_field(name="Canais", value="\n".join(canais_txt), inline=False)

        cargos_txt = []
        for nome, key in CARGOS.items():
            val = data.get(key, 0)
            cargo = interaction.guild.get_role(val) if val else None
            cargos_txt.append(f"`{nome}`: {cargo.mention if cargo else '❌ nao configurado'}")
        embed.add_field(name="Cargos", value="\n".join(cargos_txt), inline=False)

        apis_txt = [
            f"`groq`: {'✅ configurado' if data.get('GROQ_API_KEY') else '❌'}",
            f"`spotify`: {'✅ configurado' if data.get('SPOTIFY_CLIENT_ID') else '❌'}",
            f"`site`: {data.get('SITE_URL') or '❌ nao configurado'}",
        ]
        embed.add_field(name="APIs", value="\n".join(apis_txt), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # /setup reload
    @app_commands.command(name="setup-reload", description="Recriar todos os embeds do bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_reload(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        resultados = []

        # Tickets
        from cogs.tickets import TicketView
        ticket_id = dyn.get("TICKET_CANAL_ID", 0)
        canal_tickets = interaction.guild.get_channel(ticket_id) if ticket_id else None
        if canal_tickets:
            embed = discord.Embed(
                title="Central de Atendimento — Ondrakos",
                description=(
                    "Bem-vindo a Central de Atendimento.\n"
                    "Selecione o motivo do seu ticket abaixo."
                ),
                color=discord.Color.from_rgb(31, 139, 76),
            )
            img = dyn.get("IMAGEM_URL", "")
            if img: embed.set_image(url=img)
            embed.set_footer(text="Apenas abra um ticket se realmente precisar.")
            await canal_tickets.send(embed=embed, view=TicketView())
            resultados.append("✅ Embed de tickets criado")
        else:
            resultados.append("⚠️ Canal de tickets nao configurado")

        # Musica
        from cogs.musica import setup_player_embed
        await setup_player_embed(self.bot)
        resultados.append("✅ Embed de musica criado")

        # IA
        from cogs.ia_jornalista import _criar_embed_ia
        ia_id = dyn.get("IA_CANAL_ID", 0)
        canal_ia = interaction.guild.get_channel(ia_id) if ia_id else None
        if canal_ia:
            await _criar_embed_ia(canal_ia)
            resultados.append("✅ Embed de IA criado")
        else:
            resultados.append("⚠️ Canal de IA nao configurado")

        await interaction.followup.send("\n".join(resultados), ephemeral=True)


async def setup(bot):
    await bot.add_cog(SetupCog(bot))