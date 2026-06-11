# ============================================================
#  COG: TICKETS — Sistema completo de tickets — Ondrakos
#  Views persistentes (funcionam após reinício do bot)
# ============================================================

import discord
from discord.ext import commands
from discord.ui import Select, View, Button, Modal
import datetime
try:
    from discord.ui import TextInput
except ImportError:
    from discord.ui import InputText as TextInput
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
import config

DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)


# ── Helpers ────────────────────────────────────────────────
def is_staff(interaction: discord.Interaction) -> bool:
    staff1 = interaction.guild.get_role(config.STAFF_ROLE_ID())
    staff2 = interaction.guild.get_role(config.STAFF_MENTION_ROLE_ID())
    return (staff1 in interaction.user.roles) or (staff2 in interaction.user.roles)


def formatar_duracao(segundos: int) -> str:
    """Converte segundos em string legível: 'X horas, Y minutos'"""
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    partes = []
    if horas:
        partes.append(f"{horas} hora{'s' if horas != 1 else ''}")
    partes.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
    return ", ".join(partes)


# ── View de Avaliação (DM) — PERSISTENTE ──────────────────
class AvaliacaoView(View):
    """Enviada no DM do autor quando o ticket é fechado."""

    def __init__(self, canal_id: int, autor_id: int):
        super().__init__(timeout=None)
        self.canal_id = canal_id
        self.autor_id = autor_id

        options = [
            discord.SelectOption(label="⭐ 1 — Péssimo",    value="1", emoji="⭐"),
            discord.SelectOption(label="⭐⭐ 2 — Ruim",      value="2", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐ 3 — Regular",  value="3", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4 — Bom",     value="4", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 — Ótimo!", value="5", emoji="⭐"),
        ]
        select = Select(
            placeholder="Selecione de 1 a 5 estrelas...",
            min_values=1, max_values=1,
            options=options,
            custom_id=f"avaliacao_ticket_{canal_id}",
        )
        select.callback = self._avaliacao_callback
        self.add_item(select)

    async def _avaliacao_callback(self, interaction: discord.Interaction):
        nota = int(interaction.data["values"][0])
        estrelas = "⭐" * nota

        bot = interaction.client
        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.salvar_avaliacao_ticket(self.canal_id, nota)
        except Exception as e:
            print(f"Erro ao salvar avaliação: {e}")

        embed = discord.Embed(
            title="Obrigado pela avaliação!",
            description=f"Você avaliou o atendimento com **{estrelas}** ({nota}/5).\nSua opinião nos ajuda a melhorar! 🐉",
            color=DORORO_COLOR,
        )
        await interaction.response.edit_message(embed=embed, view=None)

        # Enviar nota no canal do ticket arquivado
        try:
            canal_ticket = interaction.client.get_channel(self.canal_id)
            if canal_ticket:
                embed_nota = discord.Embed(
                    title="⭐ Avaliação recebida",
                    description=(
                        f"<@{self.autor_id}> avaliou o atendimento com **{estrelas}** ({nota}/5)."
                    ),
                    color=DORORO_COLOR,
                )
                embed_nota.set_footer(text="© Ondrakos · 水の竜")
                await canal_ticket.send(embed=embed_nota)
        except Exception as e:
            print(f"[Tickets] Erro ao enviar nota no canal: {e}")


# ── Dropdown de Categorias ─────────────────────────────────
class TicketDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Suporte",   emoji="🎫", description="(Ajuda e suporte geral)",    value="suporte"),
            discord.SelectOption(label="Tarô",      emoji="🔮", description="(Solicitar leitura de tarô)", value="taro"),
            discord.SelectOption(label="Serviços",  emoji="⚙️", description="(Pedidos de serviços)",       value="servicos"),
            discord.SelectOption(label="Outros",    emoji="📋", description="(Outros assuntos)",            value="outros"),
        ]
        super().__init__(
            placeholder="Selecione o motivo do seu ticket...",
            min_values=1, max_values=1, options=options,
            custom_id="ticket_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        nomes_display = {
            "suporte": "🎫 Suporte", "taro": "🔮 Tarô",
            "servicos": "⚙️ Serviços", "outros": "📋 Outros",
        }
        categoria = self.values[0]
        await interaction.response.send_modal(
            TicketModal(categoria=categoria, nome_categoria=nomes_display[categoria])
        )
        await interaction.message.edit(view=TicketView())


# ── Modal de Ticket ────────────────────────────────────────
class TicketModal(Modal):
    def __init__(self, categoria: str, nome_categoria: str):
        super().__init__(title="Ticket - " + nome_categoria)
        self.categoria = categoria
        self.nome_categoria = nome_categoria
        self.descricao = TextInput(
            label="Descreva o motivo do seu ticket",
            style=discord.TextStyle.paragraph,
            placeholder="Explique com detalhes o que aconteceu...",
            required=True, max_length=1000,
        )
        self.add_item(self.descricao)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        bot = interaction.client

        emojis_canal = {
            "suporte": "🎫", "taro": "🔮", "servicos": "⚙️", "outros": "📋",
        }
        nomes_canal = {
            "suporte": "suporte", "taro": "taro", "servicos": "servicos", "outros": "outros",
        }
        emoji = emojis_canal.get(self.categoria, "📋")
        nome_base = (nomes_canal[self.categoria] + "-" + member.display_name).lower().replace(" ", "-").replace("_", "-")
        nome_canal = emoji + "│▸" + nome_base

        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await interaction.response.send_message(
                "Você já tem um ticket aberto: " + canal_existente.mention, ephemeral=True
            )
            return

        staff_role = guild.get_role(config.STAFF_ROLE_ID())
        category = bot.get_channel(config.TICKET_CATEGORY_ID())

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
        staff_mention_role = guild.get_role(config.STAFF_MENTION_ROLE_ID())
        if staff_mention_role and staff_mention_role != staff_role:
            overwrites[staff_mention_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        canal = await guild.create_text_channel(name=nome_canal, category=category, overwrites=overwrites)

        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.criar_ticket(guild.id, canal.id, member.id, self.categoria, self.descricao.value)
        except Exception as e:
            print("Erro ao salvar ticket no banco: " + str(e))

        staff_mention = "<@&" + str(config.STAFF_MENTION_ROLE_ID()) + ">"
        embed = discord.Embed(color=DORORO_COLOR)
        embed.add_field(
            name="🐉 • " + canal.name,
            value=(
                "A equipe já está ciente da abertura do seu ticket, basta aguardar que "
                "em breve será atendido.\n\n"
                "**ALGUMAS INFORMAÇÕES IMPORTANTES**\n"
                "🔴 Não floode no ticket\n"
                "🔴 Não marque membros da equipe\n"
                "🔴 Não abra ticket sem necessidade!"
            ),
            inline=False,
        )
        embed.add_field(name="📝 Motivo", value=self.descricao.value, inline=False)
        embed.set_footer(text="© Ondrakos · 水の竜")

        header = member.mention + " | " + staff_mention
        await canal.send(
            content=header, embed=embed, view=TicketAbertoView(),
            allowed_mentions=discord.AllowedMentions(roles=True, users=True),
        )
        await interaction.response.send_message("✅ Ticket aberto em " + canal.mention + "!", ephemeral=True)


# ── View Principal (Dropdown) — PERSISTENTE ────────────────
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ── View do Ticket Aberto — PERSISTENTE ────────────────────
class TicketAbertoView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, row=0, custom_id="ticket_fechar")
    async def fechar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode fechar tickets!", ephemeral=True)
            return
        await interaction.response.defer()
        canal = interaction.channel
        bot = interaction.client
        agora = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        # ── Busca dados do ticket no banco ─────────────────
        autor_id = None
        aberto_em = None
        motivo = "Não informado."
        try:
            if hasattr(bot, 'db') and bot.db:
                dados = await bot.db.get_ticket(canal.id)
                if dados:
                    autor_id = dados["user_id"]
                    # descricao é o motivo que o usuário digitou ao abrir o ticket
                    if dados["descricao"]:
                        motivo = dados["descricao"]
        except Exception as e:
            print(f"Erro ao buscar ticket: {e}")

        # ── Pega timestamp de abertura pela 1ª mensagem do canal ──
        try:
            primeira_msg = await canal.history(limit=1, oldest_first=True).__anext__()
            aberto_em = int(primeira_msg.created_at.timestamp())
        except Exception as e:
            print(f"[Tickets] Erro ao buscar primeira mensagem: {e}")

        # ── Fecha no banco ─────────────────────────────────
        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.fechar_ticket(canal.id, interaction.user.id)
        except Exception:
            pass

        # ── Move canal e trava permissões ──────────────────
        categoria_fechados = bot.get_channel(config.TICKET_CLOSED_CATEGORY_ID())
        for target, overwrite in list(canal.overwrites.items()):
            if isinstance(target, discord.Member) and target != interaction.guild.me:
                overwrite.send_messages = False
                try:
                    await canal.set_permissions(target, overwrite=overwrite)
                except Exception:
                    pass

        partes = canal.name.split("│", 1)
        if len(partes) == 2:
            emoji_atual = partes[0]
            resto = partes[1]
            novo_nome = canal.name if resto.startswith("fechado-") else emoji_atual + "│fechado-" + resto
        else:
            novo_nome = canal.name if canal.name.startswith("fechado-") else "fechado-" + canal.name

        try:
            await canal.edit(category=categoria_fechados, name=novo_nome)
        except Exception:
            pass

        # ── Embed no canal ─────────────────────────────────
        embed_canal = discord.Embed(
            description="🔒 Ticket fechado. Canal movido para arquivos.", color=discord.Color.red()
        )
        await interaction.edit_original_response(embed=embed_canal, view=TicketFechadoView())

        # ── DM pro autor ───────────────────────────────────
        if autor_id:
            try:
                autor = await bot.fetch_user(autor_id)
            except Exception:
                autor = None

            if autor:
                # Calcula tempo aberto
                if aberto_em:
                    duracao_seg = agora - int(aberto_em)
                    duracao_str = formatar_duracao(duracao_seg)
                else:
                    duracao_seg = 0
                    duracao_str = "Não disponível"

                # — Mensagem 1: Registro de Logs —
                embed_log = discord.Embed(
                    title="# 📁 Registro de Logs",
                    color=discord.Color.dark_gray(),
                )
                embed_log.description = (
                    f"O ticket {canal.mention} (`{canal.name}`) foi fechado por "
                    f"{interaction.user.mention} (`{interaction.user.id}`).\n"
                    f"**Motivo:** {motivo}\n"
                    f"**Autor:** {autor.mention}"
                )
                if aberto_em:
                    embed_log.add_field(name="**Abertura**",    value=f"<t:{int(aberto_em)}:f>", inline=True)
                    embed_log.add_field(name="**Fechamento**",  value=f"<t:{agora}:f>",           inline=True)
                embed_log.add_field(name="**Tempo total**", value=duracao_str, inline=False)

                # Botão que leva pro canal do ticket (após mover pra fechado)
                class LinkView(View):
                    def __init__(self, guild_id, channel_id):
                        super().__init__(timeout=None)
                        url = f"https://discord.com/channels/{guild_id}/{channel_id}"
                        self.add_item(discord.ui.Button(
                            label="Ver Ticket Arquivado",
                            style=discord.ButtonStyle.link,
                            emoji="📁",
                            url=url,
                        ))

                link_view = LinkView(interaction.guild.id, canal.id)

                # — Mensagem 2: Avaliação —
                embed_avaliacao = discord.Embed(
                    title="⭐ Avalie o Atendimento",
                    description="Como foi o seu atendimento neste ticket?\nSua opinião é muito importante para nós! 🐉",
                    color=DORORO_COLOR,
                )
                embed_avaliacao.set_footer(text="© Ondrakos · 水の竜")

                avaliacao_view = AvaliacaoView(canal_id=canal.id, autor_id=autor_id)

                try:
                    await autor.send(embed=embed_log, view=link_view)
                    await autor.send(embed=embed_avaliacao, view=avaliacao_view)
                except discord.Forbidden:
                    # DMs fechadas — silencioso, apenas loga no console
                    print(f"[Tickets] Não foi possível enviar DM para {autor} (DMs fechadas).")
                except Exception as e:
                    print(f"[Tickets] Erro ao enviar DM: {e}")

    @discord.ui.button(label="Assumir Ticket", style=discord.ButtonStyle.success, emoji="✋", row=0, custom_id="ticket_assumir")
    async def assumir(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode assumir tickets!", ephemeral=True)
            return
        embed = discord.Embed(
            description="✋ Ticket assumido por " + interaction.user.mention + "!",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Avisar Membro", style=discord.ButtonStyle.primary, emoji="🔔", row=0, custom_id="ticket_avisar")
    async def avisar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        for target, overwrite in list(interaction.channel.overwrites.items()):
            if isinstance(target, discord.Member) and overwrite.view_channel and not target.bot:
                await interaction.response.send_message(
                    content=target.mention + " a equipe está aguardando sua resposta!",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
                return
        await interaction.response.send_message("Membro não encontrado.", ephemeral=True)

    @discord.ui.button(label="Adicionar Membro", style=discord.ButtonStyle.secondary, row=1, custom_id="ticket_adicionar")
    async def adicionar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMembroModal())

    @discord.ui.button(label="Remover Membro", style=discord.ButtonStyle.secondary, row=1, custom_id="ticket_remover")
    async def remover(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(RemoverMembroModal())

    @discord.ui.button(label="Renomear Ticket", style=discord.ButtonStyle.secondary, row=1, custom_id="ticket_renomear")
    async def renomear(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(RenomearTicketModal())


# ── View do Ticket Fechado — PERSISTENTE ───────────────────
class TicketFechadoView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reabrir Ticket", style=discord.ButtonStyle.success, emoji="🔓", row=0, custom_id="ticket_reabrir")
    async def reabrir(self, interaction: discord.Interaction, button: Button):
        canal = interaction.channel
        bot = interaction.client

        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.reabrir_ticket(canal.id)
        except Exception:
            pass

        categoria_abertos = bot.get_channel(config.TICKET_CATEGORY_ID())
        for target, overwrite in list(canal.overwrites.items()):
            if isinstance(target, discord.Member) and target != interaction.guild.me:
                overwrite.send_messages = True
                await canal.set_permissions(target, overwrite=overwrite)
        partes_r = canal.name.split("│", 1)
        if len(partes_r) == 2:
            novo_nome = partes_r[0] + "│" + partes_r[1].replace("fechado-", "", 1)
        else:
            novo_nome = canal.name.replace("fechado-", "", 1)
        await canal.edit(category=categoria_abertos, name=novo_nome)
        embed = discord.Embed(description="🔓 Ticket reaberto.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=TicketAbertoView())

    @discord.ui.button(label="Deletar Ticket", style=discord.ButtonStyle.danger, emoji="🗑️", row=0, custom_id="ticket_deletar")
    async def deletar(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.delete()


# ── Modais Auxiliares ──────────────────────────────────────
class AdicionarMembroModal(Modal):
    def __init__(self):
        super().__init__(title="Adicionar Membro ao Ticket")
        self.user_id = TextInput(
            label="ID do usuário", placeholder="Ex: 123456789012345678", required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = await interaction.guild.fetch_member(int(self.user_id.value))
            await interaction.channel.set_permissions(
                member, view_channel=True, send_messages=True, read_message_history=True
            )
            await interaction.response.send_message(
                content=member.mention + " você foi adicionado(a) a este ticket!",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)


class RemoverMembroModal(Modal):
    def __init__(self):
        super().__init__(title="Remover Membro do Ticket")
        self.user_id = TextInput(
            label="ID do usuário", placeholder="Ex: 123456789012345678", required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = await interaction.guild.fetch_member(int(self.user_id.value))
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message(
                "✅ " + member.mention + " removido do ticket!", ephemeral=True
            )
        except Exception:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)


class RenomearTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Renomear Ticket")
        self.novo_nome = TextInput(
            label="Novo nome do canal", placeholder="Ex: suporte-johndoe", required=True
        )
        self.add_item(self.novo_nome)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.channel.edit(name=self.novo_nome.value.lower().replace(" ", "-"))
            await interaction.response.send_message("✅ Ticket renomeado!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro ao renomear.", ephemeral=True)


# ── Cog Principal ──────────────────────────────────────────
class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketView())
        bot.add_view(TicketAbertoView())
        bot.add_view(TicketFechadoView())

    @app_commands.command(name="setup_tickets", description="Configurar sistema de tickets do Ondrakos")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋  Central de Tickets — Ondrakos",
            description=(
                "🐉 Bem-vindo(a) ao Portal de Atendimento\n"
                "Descreva abaixo o motivo do seu ticket."
            ),
            color=DORORO_COLOR,
        )
        embed.set_image(url=config.IMAGEM_URL)
        await interaction.channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✅ Sistema de tickets enviado!", ephemeral=True)


# ── Setup do Cog ───────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(TicketsCog(bot))