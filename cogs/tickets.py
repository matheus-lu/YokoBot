# ============================================================
#  COG: TICKETS — Sistema completo de tickets V2 — Ondrakos
#  Views persistentes (funcionam após reinício do bot)
# ============================================================

import discord
import os
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
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    partes = []
    if horas:
        partes.append(f"{horas} hora{'s' if horas != 1 else ''}")
    partes.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
    return ", ".join(partes)


# ── View de Avaliação (DM) — mantida como embed padrão ─────
class AvaliacaoView(View):
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
            min_values=1, max_values=1, options=options,
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
        try:
            canal_ticket = interaction.client.get_channel(self.canal_id)
            if canal_ticket:
                embed_nota = discord.Embed(
                    title="⭐ Avaliação recebida",
                    description=f"<@{self.autor_id}> avaliou o atendimento com **{estrelas}** ({nota}/5).",
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
            discord.SelectOption(label="Suporte",  emoji="🎫", description="(Ajuda e suporte geral)",    value="suporte"),
            discord.SelectOption(label="Tarô",     emoji="🔮", description="(Solicitar leitura de tarô)", value="taro"),
            discord.SelectOption(label="Serviços", emoji="⚙️", description="(Pedidos de serviços)",       value="servicos"),
            discord.SelectOption(label="Outros",   emoji="📋", description="(Outros assuntos)",            value="outros"),
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
        tem_img = any(a.filename == "tickets.png" for a in interaction.message.attachments)
        tem_sep = any(a.filename == "sep_anuncio.png" for a in interaction.message.attachments)
        await interaction.message.edit(view=TicketLayout(tem_img=tem_img, tem_sep=tem_sep))


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

        emojis_canal = {"suporte": "🎫", "taro": "🔮", "servicos": "⚙️", "outros": "📋"}
        nomes_canal  = {"suporte": "suporte", "taro": "taro", "servicos": "servicos", "outros": "outros"}
        emoji     = emojis_canal.get(self.categoria, "📋")
        nome_base = (nomes_canal[self.categoria] + "-" + member.display_name).lower().replace(" ", "-").replace("_", "-")
        nome_canal = emoji + "│▸" + nome_base

        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await interaction.response.send_message("Você já tem um ticket aberto: " + canal_existente.mention, ephemeral=True)
            return

        staff_role = guild.get_role(config.STAFF_ROLE_ID())
        category   = bot.get_channel(config.TICKET_CATEGORY_ID())

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        staff_mention_role = guild.get_role(config.STAFF_MENTION_ROLE_ID())
        if staff_mention_role and staff_mention_role != staff_role:
            overwrites[staff_mention_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        canal = await guild.create_text_channel(name=nome_canal, category=category, overwrites=overwrites)

        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.criar_ticket(guild.id, canal.id, member.id, self.categoria, self.descricao.value)
        except Exception as e:
            print("Erro ao salvar ticket no banco: " + str(e))

        staff_mention = "<@&" + str(config.STAFF_MENTION_ROLE_ID()) + ">"

        texto_ticket = (
            f"**🐉 • {canal.name}**\n\n"
            "A equipe já está ciente da abertura do seu ticket, basta aguardar que "
            "em breve será atendido.\n\n"
            "**ALGUMAS INFORMAÇÕES IMPORTANTES**\n"
            "🔴 Não floode no ticket\n"
            "🔴 Não marque membros da equipe\n"
            "🔴 Não abra ticket sem necessidade!\n\n"
            f"**📝 Motivo**\n{self.descricao.value}"
        )

        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _img_path = _os.path.join(_base, "ticket_aberto.png")
        tem_img = _os.path.exists(_img_path) and _os.path.getsize(_img_path) < 9_000_000

        view = TicketAbertoLayout(texto=texto_ticket, tem_img=tem_img)
        arquivos = []
        if tem_img:
            arquivos.append(discord.File(_img_path, filename="ticket_aberto.png"))

        await canal.send(
            content=member.mention + " | " + staff_mention,
            allowed_mentions=discord.AllowedMentions(roles=True, users=True),
            files=arquivos if arquivos else discord.utils.MISSING,
            view=view
        )
        await interaction.response.send_message("✅ Ticket aberto em " + canal.mention + "!", ephemeral=True)


# ── Botões do Ticket Aberto ────────────────────────────────
class FecharTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_fechar")

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode fechar tickets!", ephemeral=True)
            return
        await interaction.response.defer()
        canal = interaction.channel
        bot   = interaction.client
        agora = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        autor_id = None
        aberto_em = None
        motivo = "Não informado."
        try:
            if hasattr(bot, 'db') and bot.db:
                dados = await bot.db.get_ticket(canal.id)
                if dados:
                    autor_id = dados["user_id"]
                    if dados["descricao"]:
                        motivo = dados["descricao"]
        except Exception as e:
            print(f"Erro ao buscar ticket: {e}")

        try:
            primeira_msg = await canal.history(limit=1, oldest_first=True).__anext__()
            aberto_em = int(primeira_msg.created_at.timestamp())
        except Exception as e:
            print(f"[Tickets] Erro ao buscar primeira mensagem: {e}")

        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.fechar_ticket(canal.id, interaction.user.id)
        except Exception:
            pass

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

        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _img_fechado = _os.path.join(_base, "ticket_fechado.png")
        _sep_fechado = _os.path.join(_base, "sep_anuncio.png")
        tem_fechado = _os.path.exists(_img_fechado) and _os.path.getsize(_img_fechado) < 9_000_000
        tem_sep = _os.path.exists(_sep_fechado) and _os.path.getsize(_sep_fechado) < 9_000_000

        view = TicketFechadoLayout(texto="🔒 Ticket fechado. Canal movido para arquivos.", tem_img=tem_fechado, tem_sep=tem_sep)
        
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep_fechado, filename="sep_anuncio.png"))
        if tem_fechado:
            arquivos.append(discord.File(_img_fechado, filename="ticket_fechado.png"))

        if arquivos:
            await interaction.edit_original_response(
                attachments=arquivos,
                view=view
            )
        else:
            await interaction.edit_original_response(view=view)

        if autor_id:
            try:
                autor = await bot.fetch_user(autor_id)
            except Exception:
                autor = None

            if autor:
                duracao_str = formatar_duracao(agora - int(aberto_em)) if aberto_em else "Não disponível"
                embed_log = discord.Embed(title="# 📁 Registro de Logs", color=discord.Color.dark_gray())
                embed_log.description = (
                    f"O ticket {canal.mention} (`{canal.name}`) foi fechado por "
                    f"{interaction.user.mention} (`{interaction.user.id}`).\n"
                    f"**Motivo:** {motivo}\n"
                    f"**Autor:** {autor.mention}"
                )
                if aberto_em:
                    embed_log.add_field(name="**Abertura**",   value=f"<t:{int(aberto_em)}:f>", inline=True)
                    embed_log.add_field(name="**Fechamento**", value=f"<t:{agora}:f>",           inline=True)
                embed_log.add_field(name="**Tempo total**", value=duracao_str, inline=False)

                class LinkView(View):
                    def __init__(self, guild_id, channel_id):
                        super().__init__(timeout=None)
                        url = f"https://discord.com/channels/{guild_id}/{channel_id}"
                        self.add_item(discord.ui.Button(label="Ver Ticket Arquivado", style=discord.ButtonStyle.link, emoji="📁", url=url))

                embed_avaliacao = discord.Embed(
                    title="⭐ Avalie o Atendimento",
                    description="Como foi o seu atendimento neste ticket?\nSua opinião é muito importante para nós! 🐉",
                    color=DORORO_COLOR,
                )
                embed_avaliacao.set_footer(text="© Ondrakos · 水の竜")

                try:
                    await autor.send(embed=embed_log, view=LinkView(interaction.guild.id, canal.id))
                    await autor.send(embed=embed_avaliacao, view=AvaliacaoView(canal_id=canal.id, autor_id=autor_id))
                except discord.Forbidden:
                    print(f"[Tickets] Não foi possível enviar DM para {autor} (DMs fechadas).")
                except Exception as e:
                    print(f"[Tickets] Erro ao enviar DM: {e}")


class AssumirTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Assumir Ticket", style=discord.ButtonStyle.success, emoji="✋", custom_id="ticket_assumir")

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode assumir tickets!", ephemeral=True)
            return
        embed = discord.Embed(description="✋ Ticket assumido por " + interaction.user.mention + "!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)


class AvisarTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Avisar Membro", style=discord.ButtonStyle.primary, emoji="🔔", custom_id="ticket_avisar")

    async def callback(self, interaction: discord.Interaction):
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


class AdicionarTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Adicionar Membro", style=discord.ButtonStyle.secondary, custom_id="ticket_adicionar")

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMembroModal())


class RemoverTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Remover Membro", style=discord.ButtonStyle.secondary, custom_id="ticket_remover")

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(RemoverMembroModal())


class RenomearTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Renomear Ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_renomear")

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message("Apenas a staff pode usar este botão!", ephemeral=True)
            return
        await interaction.response.send_modal(RenomearTicketModal())


# ── Layout do Painel Principal — V2 ────────────────────────
class TicketLayout(discord.ui.LayoutView):
    def __init__(self, tem_img=False, tem_sep=False):
        super().__init__(timeout=None)

        itens = []
        if tem_sep:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.extend([
            discord.ui.TextDisplay("**🎟️ |▸ Portal de Tickets › Clã do Dragão**"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                "🐉 Bem-vindo(a) ao Portal de Atendimento\n\n"
                "🗣️⧽Precisa falar com a equipe, tirar uma dúvida ou pedir algum serviço?\n"
                "Abra um ticket e conte o que você precisa, sem pressa e do seu jeito.\n\n"
                "⛩️⧽Este espaço é para pedidos, suporte, dúvidas, serviços e assuntos que precisam ser tratados com mais calma fora dos canais principais.\n\n"
                "🪭⧽Escolha a opção certa abaixo e aguarde alguém da equipe aparecer pelo portal.\n"
                "Use com respeito para manter a energia do servidor leve e organizada.\n\n"
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        ])
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://tickets.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.extend([
            discord.ui.TextDisplay("-# Selecione o motivo do seu ticket abaixo."),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(TicketDropdown()),
        ])
        self.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))

# Alias para compatibilidade com setup.py
TicketView = TicketLayout


# ── Layout do Ticket Aberto — V2 ────────────────────────────
class TicketAbertoLayout(discord.ui.LayoutView):
    def __init__(self, texto="**🐉 Ticket Aberto**", tem_img=False, tem_sep=False):
        super().__init__(timeout=None)

        row1 = discord.ui.ActionRow(FecharTicketButton(), AssumirTicketButton(), AvisarTicketButton())
        row2 = discord.ui.ActionRow(AdicionarTicketButton(), RemoverTicketButton(), RenomearTicketButton())

        itens = []
        if tem_sep:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay(texto))
        itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://ticket_aberto.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay("-# © Ondrakos · 水の竜"))
        itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(row1)
        itens.append(row2)

        self.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))

# Alias para compatibilidade
TicketAbertoView = TicketAbertoLayout


# ── Botões do Ticket Fechado ───────────────────────────────
class ReabrirTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Reabrir Ticket", style=discord.ButtonStyle.success, emoji="🔓", custom_id="ticket_reabrir")

    async def callback(self, interaction: discord.Interaction):
        canal = interaction.channel
        bot   = interaction.client
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
        await interaction.response.edit_message(view=TicketAbertoLayout(texto="🔓 Ticket reaberto."))


class DeletarTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Deletar Ticket", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_deletar")

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.delete()


# ── Layout do Ticket Fechado — V2 ───────────────────────────
class TicketFechadoLayout(discord.ui.LayoutView):
    def __init__(self, texto="🔒 Ticket fechado.", tem_img=False, tem_sep=False):
        super().__init__(timeout=None)

        row1 = discord.ui.ActionRow(ReabrirTicketButton(), DeletarTicketButton())

        itens = []
        if tem_sep:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay(texto))
        itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://ticket_fechado.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(row1)

        self.add_item(discord.ui.Container(*itens, accent_color=discord.Color.red()))

# Alias para compatibilidade
TicketFechadoView = TicketFechadoLayout


# ── Modais Auxiliares ──────────────────────────────────────
class AdicionarMembroModal(Modal):
    def __init__(self):
        super().__init__(title="Adicionar Membro ao Ticket")
        self.user_id = TextInput(label="ID do usuário", placeholder="Ex: 123456789012345678", required=True)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = await interaction.guild.fetch_member(int(self.user_id.value))
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(
                content=member.mention + " você foi adicionado(a) a este ticket!",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)


class RemoverMembroModal(Modal):
    def __init__(self):
        super().__init__(title="Remover Membro do Ticket")
        self.user_id = TextInput(label="ID do usuário", placeholder="Ex: 123456789012345678", required=True)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = await interaction.guild.fetch_member(int(self.user_id.value))
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message("✅ " + member.mention + " removido do ticket!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)


class RenomearTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Renomear Ticket")
        self.novo_nome = TextInput(label="Novo nome do canal", placeholder="Ex: suporte-johndoe", required=True)
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
        bot.add_view(TicketLayout())
        bot.add_view(TicketAbertoLayout())
        bot.add_view(TicketFechadoLayout())

    @app_commands.command(name="setup_tickets", description="Configurar sistema de tickets do Ondrakos")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _img  = os.path.join(_base, "tickets.png")
        _sep  = os.path.join(_base, "sep_anuncio.png")
        tem_img = os.path.exists(_img) and os.path.getsize(_img) < 9_000_000
        tem_sep = os.path.exists(_sep) and os.path.getsize(_sep) < 9_000_000
        view = TicketLayout(tem_img=tem_img, tem_sep=tem_sep)
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep, filename="sep_anuncio.png"))
        if tem_img:
            arquivos.append(discord.File(_img, filename="tickets.png"))
        if arquivos:
            await interaction.channel.send(files=arquivos, view=view)
        else:
            await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Sistema de tickets enviado!", ephemeral=True)


# ── Setup do Cog ───────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(TicketsCog(bot))