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


# ── View de Log e Avaliação (DM) — V2 ───────────────────────
class TicketFechadoDMLayout(discord.ui.LayoutView):
    def __init__(self, canal_id: int, autor_id: int, texto_log: str, url_arquivo: str):
        super().__init__(timeout=None)
        self.canal_id = canal_id
        self.autor_id = autor_id
        self.texto_log = texto_log
        self.url_arquivo = url_arquivo
        
        self._montar_layout(nota=None)
        
    def _montar_layout(self, nota=None):
        self.clear_items()
        
        # 1) Container do Log
        botao_link = discord.ui.Button(label="Ver Ticket Arquivado", style=discord.ButtonStyle.link, emoji="📁", url=self.url_arquivo)
        itens_log = [
            discord.ui.TextDisplay(self.texto_log),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(botao_link)
        ]
        self.add_item(discord.ui.Container(*itens_log, accent_color=discord.Color.dark_gray()))
        
        # 2) Container da Avaliação
        if nota is None:
            options = [
                discord.SelectOption(label="⭐ 1 — Péssimo",    value="1", emoji="⭐"),
                discord.SelectOption(label="⭐⭐ 2 — Ruim",      value="2", emoji="⭐"),
                discord.SelectOption(label="⭐⭐⭐ 3 — Regular",  value="3", emoji="⭐"),
                discord.SelectOption(label="⭐⭐⭐⭐ 4 — Bom",     value="4", emoji="⭐"),
                discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 — Ótimo!", value="5", emoji="⭐"),
            ]
            select = discord.ui.Select(
                placeholder="Selecione de 1 a 5 estrelas...",
                min_values=1, max_values=1, options=options,
                custom_id=f"avaliacao_ticket_{self.canal_id}",
            )
            select.callback = self._avaliacao_callback
            texto_ava = "**⭐ Avalie o Atendimento**\nComo foi o seu atendimento neste ticket?\nSua opinião é muito importante para nós! 🐉\n\n-# © Ondrakos · 水の竜"
            itens_ava = [
                discord.ui.TextDisplay(texto_ava),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(select)
            ]
        else:
            estrelas = "⭐" * nota
            texto_resp = f"**Obrigado pela avaliação!**\nVocê avaliou o atendimento com **{estrelas}** ({nota}/5).\nSua opinião nos ajuda a melhorar! 🐉\n\n-# © Ondrakos · 水の竜"
            itens_ava = [discord.ui.TextDisplay(texto_resp)]
            
        self.add_item(discord.ui.Container(*itens_ava, accent_color=DORORO_COLOR))

    async def _avaliacao_callback(self, interaction: discord.Interaction):
        nota = int(interaction.data["values"][0])
        estrelas = "⭐" * nota
        bot = interaction.client
        try:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.salvar_avaliacao_ticket(self.canal_id, nota)
        except Exception as e:
            print(f"Erro ao salvar avaliação: {e}")
            
        self._montar_layout(nota=nota)
        await interaction.response.edit_message(view=self)
        
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
        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _img_path = _os.path.join(_base, "tickets.png")
        _sep_path = _os.path.join(_base, "sep_anuncio.png")
        tem_img = _os.path.exists(_img_path) and _os.path.getsize(_img_path) < 9_000_000
        tem_sep = _os.path.exists(_sep_path) and _os.path.getsize(_sep_path) < 9_000_000
        
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep_path, filename="sep_anuncio.png"))
        if tem_img:
            arquivos.append(discord.File(_img_path, filename="tickets.png"))

        if arquivos:
            await interaction.message.edit(
                view=TicketLayout(tem_img=tem_img, tem_sep=tem_sep),
                attachments=arquivos
            )
        else:
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
            f"**{canal.name}**\n\n"
            "🎟️ |▸**TICKET ABERTO › Clã de Ondrakos**\n\n"
            "*A equipe já está ciente da abertura do seu ticket.*\n"
            "*Agora basta aguardar com calma que, em breve, um membro responsável irá atender sua solicitação.*\n\n"
            "📌⧽ALGUMAS INFORMAÇÕES IMPORTANTES\n\n"
            "<:_avisoverde:1507463101354606602>⧽Explique seu problema de forma clara e objetiva\n"
            "<:_avisoverde:1507463101354606602>⧽Envie prints, links ou detalhes importantes, se necessário\n"
            "<:_avisovermelho:1507463068974584039>⧽Não floode no ticket\n"
            "<:_avisovermelho:1507463068974584039>⧽Não marque membros da equipe sem necessidade\n"
            "<:_avisoamarelo:1507463130098438386>⧽Não abra vários tickets sobre o mesmo assunto\n"
            "<:_avisoamarelo:1507463130098438386>⧽Mantenha o respeito durante todo o atendimento\n\n"
            "🐉 ⧽Seu chamado foi recebido pelos guardiões do Clã Ondrakos.\n"
            "Aguarde no santuário, em breve sua voz será ouvida.\n\n"
            f"**📝 Motivo**\n{self.descricao.value}\n\n"
            f"{member.mention} | {staff_mention}"
        )

        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _img_path = _os.path.join(_base, "ticket_aberto.png")
        _sep_path = _os.path.join(_base, "sep_anuncio.png")
        tem_img = _os.path.exists(_img_path) and _os.path.getsize(_img_path) < 9_000_000
        tem_sep = _os.path.exists(_sep_path) and _os.path.getsize(_sep_path) < 9_000_000

        view = TicketAbertoLayout(texto=texto_ticket, tem_img=tem_img, tem_sep=tem_sep)
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep_path, filename="sep_anuncio.png"))
        if tem_img:
            arquivos.append(discord.File(_img_path, filename="ticket_aberto.png"))

        await canal.send(
            files=arquivos if arquivos else discord.utils.MISSING,
            view=view
        )
        await interaction.response.send_message("✅ Ticket aberto em " + canal.mention + "!", ephemeral=True)

        try:
            embed_dm = discord.Embed(
                title="🎟️ Ticket Aberto",
                description=f"Seu ticket foi aberto com sucesso!\nCanal: {canal.mention}",
                color=DORORO_COLOR
            )
            await member.send(embed=embed_dm)
        except discord.Forbidden:
            log_canal = guild.get_channel(config.LOGS_CANAL_ID())
            if log_canal:
                embed_log_dm = discord.Embed(
                    title="⚠️ Aviso: DM Fechada",
                    description=f"O ticket {canal.mention} foi aberto por {member.mention}, mas **não foi possível avisá-lo na DM** porque as mensagens diretas estão desativadas.",
                    color=discord.Color.orange()
                )
                await log_canal.send(embed=embed_log_dm)


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
            resto = partes[1].replace("▸", "", 1).replace("fechado-", "", 1)
            novo_nome = canal.name if "fechado-" in canal.name else emoji_atual + "│▸fechado-" + resto
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

        staff_mention = "<@&" + str(config.STAFF_MENTION_ROLE_ID()) + ">"
        membro = f"<@{autor_id}>" if autor_id else "Usuário Desconhecido"
        nome_limpo = canal.name.replace("fechado-", "")
        
        texto_fechado = (
            f"**{nome_limpo}**\n\n"
            "🎟️ |▸**TICKET FECHADO › Clã de Ondrakos**\n\n"
            "*Seu ticket foi encerrado pela equipe do Clã Ondrakos.*\n"
            "Agradecemos por ter entrado em contato e esperamos que sua solicitação tenha sido resolvida da melhor forma possível.\n\n"
            "📌⧽ALGUMAS INFORMAÇÕES IMPORTANTES\n\n"
            "<:_avisovermelho:1507463068974584039>⧽Não reabra ou crie outro ticket sobre o mesmo assunto sem necessidade\n"
            "<:_avisoamarelo:1507463130098438386>⧽Não marque membros da equipe após o fechamento\n"
            "<:_avisovermelho:1507463068974584039>⧽Caso ainda precise de ajuda, abra um novo ticket apenas se o problema não tiver sido resolvido\n"
            "<:_avisoamarelo:1507463130098438386>⧽Respeite o tempo e a organização da equipe\n\n"
            "🐉⧽Seu chamado foi registrado no santuário.\n"
            "Quando necessário, os guardiões voltarão a ouvir sua voz.\n\n"
            f"**📝 Motivo**\n{motivo}\n\n"
            "🔒 **Ticket fechado.**\n\n"
            f"{membro} | {staff_mention}"
        )

        view = TicketFechadoLayout(texto=texto_fechado, tem_img=tem_fechado, tem_sep=tem_sep)
        
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep_fechado, filename="sep_anuncio.png"))
        if tem_fechado:
            arquivos.append(discord.File(_img_fechado, filename="ticket_fechado.png"))

        if arquivos:
            await interaction.message.edit(
                attachments=arquivos,
                view=view
            )
        else:
            await interaction.message.edit(view=view)

        if autor_id:
            try:
                autor = await bot.fetch_user(autor_id)
            except Exception:
                autor = None

            if autor:
                duracao_str = formatar_duracao(agora - int(aberto_em)) if aberto_em else "Não disponível"
                texto_log = (
                    f"# 📁 |▸**Registro de Logs › Clã de Ondrakos**\n\n"
                    f"O ticket {canal.mention} (`{canal.name}`) foi fechado por "
                    f"{interaction.user.mention} (`{interaction.user.id}`).\n\n"
                    f"**Motivo:** {motivo}\n"
                    f"**Autor:** {autor.mention}\n\n"
                )
                if aberto_em:
                    texto_log += f"**Abertura:** <t:{int(aberto_em)}:f>\n"
                    texto_log += f"**Fechamento:** <t:{agora}:f>\n"
                texto_log += f"**Tempo total:** {duracao_str}"

                url_arquivo = f"https://discord.com/channels/{interaction.guild.id}/{canal.id}"
                
                try:
                    layout_dm = TicketFechadoDMLayout(
                        canal_id=canal.id,
                        autor_id=autor_id,
                        texto_log=texto_log,
                        url_arquivo=url_arquivo
                    )
                    await autor.send(view=layout_dm)
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
            base_nome = partes_r[1].replace("▸", "").replace("fechado-", "")
            novo_nome = partes_r[0] + "│▸" + base_nome
        else:
            novo_nome = canal.name.replace("fechado-", "", 1)
        await canal.edit(category=categoria_abertos, name=novo_nome)
        
        # When reopening, we need to restore the open ticket layout
        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _img_path = _os.path.join(_base, "ticket_aberto.png")
        _sep_path = _os.path.join(_base, "sep_anuncio.png")
        tem_img = _os.path.exists(_img_path) and _os.path.getsize(_img_path) < 9_000_000
        tem_sep = _os.path.exists(_sep_path) and _os.path.getsize(_sep_path) < 9_000_000

        motivo = "Desconhecido"
        autor_id = None
        if hasattr(bot, 'db') and bot.db:
            dados = await bot.db.get_ticket(canal.id)
            if dados:
                autor_id = dados["user_id"]
                if dados["descricao"]:
                    motivo = dados["descricao"]

        staff_mention = "<@&" + str(config.STAFF_MENTION_ROLE_ID()) + ">"
        membro = f"<@{autor_id}>" if autor_id else "Usuário Desconhecido"

        texto_reaberto = (
            f"**{novo_nome}**\n\n"
            "🎟️ |▸**TICKET REABERTO › Clã de Ondrakos**\n\n"
            "*Seu ticket foi reaberto pela equipe.*\n"
            "Aguarde o prosseguimento do seu atendimento.\n\n"
            "📌⧽ALGUMAS INFORMAÇÕES IMPORTANTES\n\n"
            "<:_avisoverde:1507463101354606602>⧽Explique seu problema de forma clara e objetiva\n"
            "<:_avisoverde:1507463101354606602>⧽Envie prints, links ou detalhes importantes, se necessário\n"
            "<:_avisovermelho:1507463068974584039>⧽Não floode no ticket\n"
            "<:_avisovermelho:1507463068974584039>⧽Não marque membros da equipe sem necessidade\n"
            "<:_avisoamarelo:1507463130098438386>⧽Não abra vários tickets sobre o mesmo assunto\n"
            "<:_avisoamarelo:1507463130098438386>⧽Mantenha o respeito durante todo o atendimento\n\n"
            f"**📝 Motivo**\n{motivo}\n\n"
            "🔓 **Ticket reaberto.**\n\n"
            f"{membro} | {staff_mention}"
        )

        view = TicketAbertoLayout(texto=texto_reaberto, tem_img=tem_img, tem_sep=tem_sep)
        arquivos = []
        if tem_sep:
            arquivos.append(discord.File(_sep_path, filename="sep_anuncio.png"))
        if tem_img:
            arquivos.append(discord.File(_img_path, filename="ticket_aberto.png"))

        if arquivos:
            await interaction.message.edit(attachments=arquivos, view=view)
        else:
            await interaction.message.edit(view=view)


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