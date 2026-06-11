# ============================================================
#  COG: CALENDARIO — Lembretes de datas (aniversários, etc.)
#  Ondrakos · Arquivo: cogs/calendario.py  (arquivo NOVO)
# ============================================================
#
#  Comandos:
#    /set-mensagem            — Cadastrar novo lembrete no calendário
#    /buscar-evento           — Listar lembretes (com editar/deletar)
#    /teste-mensagem-evento   — Dispara a mensagem de teste no canal atual
#
#  Task:
#    verificar_calendario_task — Roda a cada hora exata (BRT)
#
#  Dependências extras:
#    Pillow  →  pip install Pillow  (adicione ao requirements.txt)
#
# ============================================================

import discord
from discord.ext import commands, tasks
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

import datetime
import asyncio
import io

DORORO_COLOR   = discord.Color.from_rgb(31, 139, 76)
CANAL_ANUNCIOS = 1486112985427480717
BRT            = datetime.timezone(datetime.timedelta(hours=-3))
LIMITE_IMAGEM  = 2 * 1024 * 1024   # 2 MB


# ════════════════════════════════════════════════════════════
#  Compressão de imagem com Pillow
# ════════════════════════════════════════════════════════════

def comprimir_imagem(dados: bytes, nome_arquivo: str) -> tuple[bytes, str]:
    """
    Comprime a imagem se ultrapassar LIMITE_IMAGEM.
    - JPEG: reduz qualidade progressivamente até caber.
    - PNG:  usa compressão máxima lossless.
    - Outros formatos: converte para JPEG e comprime.

    Retorna (bytes_finais, nome_final).
    """
    from PIL import Image

    if len(dados) <= LIMITE_IMAGEM:
        return dados, nome_arquivo

    img = Image.open(io.BytesIO(dados))

    # Normaliza modo para salvar como JPEG sem erros de modo
    if img.mode in ("RGBA", "P", "LA"):
        fundo = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        fundo.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = fundo
    elif img.mode != "RGB":
        img = img.convert("RGB")

    ext = nome_arquivo.rsplit(".", 1)[-1].lower()

    # PNG lossless
    if ext == "png":
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True, compress_level=9)
        resultado = buf.getvalue()
        if len(resultado) <= LIMITE_IMAGEM:
            print(f"[Calendário] 🖼️  PNG comprimido: {len(dados)//1024}KB → {len(resultado)//1024}KB")
            return resultado, nome_arquivo
        # PNG ainda grande: converte para JPEG e comprime
        ext = "jpg"
        nome_arquivo = nome_arquivo.rsplit(".", 1)[0] + ".jpg"

    # JPEG: reduz qualidade até caber
    qualidade = 90
    while qualidade >= 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=qualidade, optimize=True)
        resultado = buf.getvalue()
        if len(resultado) <= LIMITE_IMAGEM:
            print(
                f"[Calendário] 🖼️  JPEG comprimido (q={qualidade}): "
                f"{len(dados)//1024}KB → {len(resultado)//1024}KB"
            )
            return resultado, nome_arquivo
        qualidade -= 10

    # Último recurso: redimensiona pela metade e tenta de novo
    img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)
    resultado = buf.getvalue()
    print(
        f"[Calendário] ⚠️  Imagem redimensionada (50%): "
        f"{len(dados)//1024}KB → {len(resultado)//1024}KB"
    )
    return resultado, nome_arquivo


# ════════════════════════════════════════════════════════════
#  Helpers de data/hora
# ════════════════════════════════════════════════════════════

def parse_data(data_str: str) -> tuple[str, str] | None:
    """
    Aceita DD/MM/AAAA (pontual) ou DD/MM (anual).
    Retorna (data_iso, mes_dia) ou None se inválido.
    """
    partes = data_str.strip().split("/")
    try:
        if len(partes) == 2:
            dia, mes = int(partes[0]), int(partes[1])
            datetime.date(2000, mes, dia)
            mes_dia = f"{mes:02d}-{dia:02d}"
            return mes_dia, mes_dia
        elif len(partes) == 3:
            dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            datetime.date(ano, mes, dia)
            data_iso = f"{ano:04d}-{mes:02d}-{dia:02d}"
            mes_dia  = f"{mes:02d}-{dia:02d}"
            return data_iso, mes_dia
    except (ValueError, TypeError):
        pass
    return None


def parse_hora(hora_str: str) -> str | None:
    try:
        h, m = hora_str.strip().split(":")
        datetime.time(int(h), int(m))
        return f"{int(h):02d}:{int(m):02d}"
    except Exception:
        return None


def agora_brt() -> datetime.datetime:
    return datetime.datetime.now(BRT)


def formatar_data_display(data_iso: str, anual: bool) -> str:
    MESES = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.",
             "jul.", "ago.", "set.", "out.", "nov.", "dez."]
    try:
        if anual:
            mes, dia = map(int, data_iso.split("-"))
            return f"{dia:02d} de {MESES[mes - 1]} (todo ano)"
        else:
            ano, mes, dia = map(int, data_iso.split("-"))
            return f"{dia:02d} de {MESES[mes - 1]} de {ano}"
    except Exception:
        return data_iso


# ════════════════════════════════════════════════════════════
#  Coletar imagem no chat (reutilizável)
# ════════════════════════════════════════════════════════════

async def _coletar_imagem(
    bot,
    interaction: discord.Interaction,
    user_id: int,
) -> tuple[bytes | None, str | None, bool]:
    """
    Aguarda o usuário enviar uma imagem ou digitar 'pular'/'cancelar'.

    Retorna:
        (bytes, nome_arquivo, cancelado)
        - bytes=None, cancelado=False → usuário pulou (sem imagem)
        - bytes=None, cancelado=True  → usuário cancelou
        - bytes=dados, cancelado=False → imagem recebida e comprimida
    """
    def check(m):
        return m.author.id == user_id and m.channel.id == interaction.channel.id

    try:
        msg = await bot.wait_for("message", check=check, timeout=120)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏳ Tempo esgotado.", ephemeral=True)
        return None, None, True

    # Deletar mensagem do usuário silenciosamente
    try:
        bot.mensagens_deletadas_pelo_bot[msg.id] = {"comando": "/set-mensagem"}
        await msg.delete()
    except Exception:
        pass

    opcao = msg.content.strip().lower()

    if opcao == "cancelar":
        return None, None, True

    if opcao == "pular" or not msg.attachments:
        return None, None, False

    att = msg.attachments[0]
    if not att.content_type or not att.content_type.startswith("image"):
        await interaction.followup.send(
            "⚠️ O arquivo enviado não é uma imagem. O lembrete será salvo sem imagem.",
            ephemeral=True,
        )
        return None, None, False

    try:
        dados = await att.read()
    except Exception as e:
        await interaction.followup.send(
            f"⚠️ Erro ao baixar imagem: {e}. O lembrete será salvo sem imagem.",
            ephemeral=True,
        )
        return None, None, False

    # Comprimir se necessário
    try:
        dados, nome = comprimir_imagem(dados, att.filename)
    except Exception as e:
        print(f"[Calendário] ⚠️  Erro na compressão: {e} — usando imagem original")
        nome = att.filename

    return dados, nome, False


# ════════════════════════════════════════════════════════════
#  Montar embed de disparo (real e teste)
# ════════════════════════════════════════════════════════════

def _montar_embed_disparo(row) -> discord.Embed:
    anual    = bool(row["anual"])
    data_str = formatar_data_display(row["data_iso"], anual)
    embed = discord.Embed(
        title=f"🎉 {row['nome']}",
        description=row["mensagem"],
        color=DORORO_COLOR,
    )
    embed.add_field(name="📆 Data",    value=data_str,          inline=True)
    embed.add_field(name="🕐 Horário", value=f"{row['horario']} BRT", inline=True)
    embed.set_footer(text="© Ondrakos · 水の竜")
    # Imagem é adicionada na hora do envio via discord.File
    return embed


async def _enviar_lembrete(canal: discord.TextChannel, row) -> bool:
    """
    Envia o embed do lembrete no canal, com imagem se houver.
    Retorna True se enviou com sucesso.
    """
    embed = _montar_embed_disparo(row)
    imagem_bytes = bytes(row["imagem"]) if row["imagem"] else None
    imagem_nome  = row["imagem_nome"] or "imagem.jpg"

    try:
        if imagem_bytes:
            embed.set_image(url=f"attachment://{imagem_nome}")
            arquivo = discord.File(io.BytesIO(imagem_bytes), filename=imagem_nome)
            await canal.send(embed=embed, file=arquivo)
        else:
            await canal.send(embed=embed)
        return True
    except Exception as e:
        print(f"[Calendário] ❌ Erro ao enviar lembrete '{row['nome']}': {e}")
        return False


# ════════════════════════════════════════════════════════════
#  Modal — Criar lembrete (coleta dados textuais)
# ════════════════════════════════════════════════════════════

class SetMensagemModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="📅 Novo Lembrete — Calendário Ondrakos")
        self.bot = bot

        self.nome_field = discord.ui.TextInput(
            label="Nome do evento",
            placeholder="Ex: Aniversário do João, Reunião do Clã",
            required=True,
            max_length=100,
        )
        self.data_field = discord.ui.TextInput(
            label="Data (DD/MM = anual  ·  DD/MM/AAAA = pontual)",
            placeholder="Ex: 15/03 → todo ano   |   15/03/2027 → só uma vez",
            required=True,
            max_length=12,
        )
        self.hora_field = discord.ui.TextInput(
            label="Horário BRT (HH:MM)",
            placeholder="Ex: 20:00",
            required=True,
            max_length=5,
        )
        self.mensagem_field = discord.ui.TextInput(
            label="Mensagem personalizada",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: 🎉 Hoje é o aniversário do João! Feliz aniversário! 🎂",
            required=True,
            max_length=1800,
        )
        self.add_item(self.nome_field)
        self.add_item(self.data_field)
        self.add_item(self.hora_field)
        self.add_item(self.mensagem_field)

    async def on_submit(self, interaction: discord.Interaction):
        # Validar data
        resultado_data = parse_data(self.data_field.value)
        if not resultado_data:
            await interaction.response.send_message(
                "❌ Data inválida. Use `DD/MM` para repetição anual ou `DD/MM/AAAA` para pontual.",
                ephemeral=True,
            )
            return

        data_iso, _ = resultado_data
        anual = len(data_iso) == 5   # 'MM-DD' = 5 chars → anual

        horario = parse_hora(self.hora_field.value)
        if not horario:
            await interaction.response.send_message(
                "❌ Horário inválido. Use o formato `HH:MM`.",
                ephemeral=True,
            )
            return

        if not self.bot.db:
            await interaction.response.send_message("❌ Banco de dados indisponível.", ephemeral=True)
            return

        # Pedir imagem no chat
        embed_img = discord.Embed(
            title="🖼️ Imagem do lembrete",
            description=(
                "Envie uma **imagem** para o embed do lembrete neste canal.\n"
                "Recomendado: mínimo **800×320px**.\n\n"
                "Se a imagem passar de **2MB**, ela será comprimida automaticamente.\n\n"
                "Digite **pular** para salvar sem imagem.\n"
                "Digite **cancelar** para cancelar."
            ),
            color=DORORO_COLOR,
        )
        embed_img.set_footer(text="⏳ Você tem 2 minutos para enviar.")
        await interaction.response.send_message(embed=embed_img, ephemeral=True)

        imagem_bytes, imagem_nome, cancelado = await _coletar_imagem(
            self.bot, interaction, interaction.user.id
        )

        if cancelado:
            await interaction.followup.send("❌ Lembrete cancelado.", ephemeral=True)
            return

        # Salvar no banco
        lembrete_id = await self.bot.db.salvar_lembrete(
            guild_id    = interaction.guild.id,
            nome        = self.nome_field.value,
            data_iso    = data_iso,
            horario     = horario,
            mensagem    = self.mensagem_field.value,
            canal_id    = CANAL_ANUNCIOS,
            anual       = anual,
            imagem      = imagem_bytes,
            imagem_nome = imagem_nome,
        )

        canal      = interaction.guild.get_channel(CANAL_ANUNCIOS)
        canal_str  = canal.mention if canal else f"`{CANAL_ANUNCIOS}`"
        data_display = formatar_data_display(data_iso, anual)

        embed_ok = discord.Embed(
            title="✅ Lembrete cadastrado!",
            description=(
                f"📌 **{self.nome_field.value}**\n"
                f"📆 **Data:** {data_display}\n"
                f"🕐 **Horário:** {horario} BRT\n"
                f"📢 **Canal:** {canal_str}\n"
                f"🔁 **Repetição:** {'Anual ♻️' if anual else 'Pontual (uma vez)'}\n"
                f"🖼️ **Imagem:** {'✅ Salva' if imagem_bytes else '— Nenhuma'}\n\n"
                f"**Mensagem:**\n{self.mensagem_field.value[:600]}"
                + ("…" if len(self.mensagem_field.value) > 600 else "")
            ),
            color=DORORO_COLOR,
        )
        embed_ok.set_footer(
            text=f"ID: {lembrete_id} · Use /teste-mensagem-evento para testar · © Ondrakos · 水の竜"
        )
        await interaction.followup.send(embed=embed_ok, ephemeral=True)
        print(f"[Calendário] 💾 Lembrete #{lembrete_id} salvo: '{self.nome_field.value}' em {data_iso} {horario}")


# ════════════════════════════════════════════════════════════
#  Auxiliar — _DictRow (compatibilidade pós-edição em memória)
# ════════════════════════════════════════════════════════════

class _DictRow:
    def __init__(self, d: dict):
        self._d = d
    def __getitem__(self, key):
        return self._d[key]
    def __contains__(self, key):
        return key in self._d


# ════════════════════════════════════════════════════════════
#  Embed de exibição no /buscar-evento
# ════════════════════════════════════════════════════════════

async def _montar_embed_lembrete(row, guild: discord.Guild) -> discord.Embed:
    anual     = bool(row["anual"])
    canal     = guild.get_channel(row["canal_id"])
    canal_str = canal.mention if canal else f"`{row['canal_id']}`"
    data_str  = formatar_data_display(row["data_iso"], anual)
    tem_img   = bool(row["imagem_nome"])   # get_lembretes_guild não carrega o BLOB

    embed = discord.Embed(title=f"📅 {row['nome']}", color=DORORO_COLOR)
    embed.add_field(name="📆 Data",       value=data_str,               inline=True)
    embed.add_field(name="🕐 Horário",    value=f"{row['horario']} BRT", inline=True)
    embed.add_field(name="📢 Canal",      value=canal_str,               inline=True)
    embed.add_field(
        name="🔁 Repetição",
        value="Anual ♻️" if anual else "Pontual (uma vez)",
        inline=True,
    )
    embed.add_field(name="🖼️ Imagem",    value="✅ Salva" if tem_img else "— Nenhuma", inline=True)
    embed.add_field(
        name="📝 Mensagem",
        value=row["mensagem"][:800] + ("…" if len(row["mensagem"]) > 800 else ""),
        inline=False,
    )
    embed.set_footer(text=f"ID: {row['id']} · © Ondrakos · 水の竜")
    return embed


# ════════════════════════════════════════════════════════════
#  View — /buscar-evento (paginação + editar + deletar)
# ════════════════════════════════════════════════════════════

class BuscarEventoView(discord.ui.View):
    def __init__(self, lembretes: list, guild: discord.Guild, pagina: int = 0):
        super().__init__(timeout=120)
        self.lembretes = lembretes
        self.guild     = guild
        self.pagina    = pagina
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self.clear_items()
        total = len(self.lembretes)

        btn_ant = discord.ui.Button(label="◀ Anterior", style=discord.ButtonStyle.secondary,
                                    disabled=(self.pagina == 0))
        btn_ant.callback = self._anterior
        self.add_item(btn_ant)

        btn_prox = discord.ui.Button(label="Próximo ▶", style=discord.ButtonStyle.secondary,
                                     disabled=(self.pagina >= total - 1))
        btn_prox.callback = self._proximo
        self.add_item(btn_prox)

        btn_edit = discord.ui.Button(label="✏️ Editar mensagem", style=discord.ButtonStyle.primary)
        btn_edit.callback = self._editar
        self.add_item(btn_edit)

        btn_del = discord.ui.Button(label="🗑️ Deletar lembrete", style=discord.ButtonStyle.danger)
        btn_del.callback = self._deletar
        self.add_item(btn_del)

    async def _render(self, interaction: discord.Interaction, nota: str = ""):
        row   = self.lembretes[self.pagina]
        embed = await _montar_embed_lembrete(row, self.guild)
        total = len(self.lembretes)
        embed.description = f"Lembrete **{self.pagina + 1}** de **{total}**" + (f" · {nota}" if nota else "")
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _anterior(self, interaction: discord.Interaction):
        self.pagina = max(0, self.pagina - 1)
        await self._render(interaction)

    async def _proximo(self, interaction: discord.Interaction):
        self.pagina = min(len(self.lembretes) - 1, self.pagina + 1)
        await self._render(interaction)

    async def _editar(self, interaction: discord.Interaction):
        row = self.lembretes[self.pagina]
        await interaction.response.send_modal(
            EditarMensagemLembreteModal(row["id"], row["nome"], row["mensagem"], self)
        )

    async def _deletar(self, interaction: discord.Interaction):
        row = self.lembretes[self.pagina]
        embed = discord.Embed(
            title="⚠️ Confirmar exclusão",
            description=f"Tem certeza que deseja deletar o lembrete **{row['nome']}**?\nEsta ação não pode ser desfeita.",
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(
            embed=embed,
            view=ConfirmarDeleteView(row["id"], row["nome"], self),
        )


class EditarMensagemLembreteModal(discord.ui.Modal):
    def __init__(self, lembrete_id: int, nome: str, mensagem_atual: str, view_pai: BuscarEventoView):
        super().__init__(title=f"✏️ Editar: {nome[:40]}")
        self.lembrete_id = lembrete_id
        self.view_pai    = view_pai

        self.mensagem_field = discord.ui.TextInput(
            label="Nova mensagem",
            style=discord.TextStyle.paragraph,
            default=mensagem_atual,
            required=True,
            max_length=1800,
        )
        self.add_item(self.mensagem_field)

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        if not bot.db:
            await interaction.response.send_message("❌ Banco de dados indisponível.", ephemeral=True)
            return

        await bot.db.atualizar_lembrete_mensagem(self.lembrete_id, self.mensagem_field.value)

        for i, row in enumerate(self.view_pai.lembretes):
            if row["id"] == self.lembrete_id:
                novo = dict(row._d) if isinstance(row, _DictRow) else dict(row)
                novo["mensagem"] = self.mensagem_field.value
                self.view_pai.lembretes[i] = _DictRow(novo)
                break

        await self.view_pai._render(interaction, nota="✅ Mensagem atualizada!")
        print(f"[Calendário] ✏️  Mensagem do lembrete #{self.lembrete_id} atualizada.")


class ConfirmarDeleteView(discord.ui.View):
    def __init__(self, lembrete_id: int, nome: str, view_pai: BuscarEventoView):
        super().__init__(timeout=60)
        self.lembrete_id = lembrete_id
        self.nome        = nome
        self.view_pai    = view_pai

    @discord.ui.button(label="✅ Confirmar exclusão", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button):
        bot = interaction.client
        if bot.db:
            await bot.db.deletar_lembrete(self.lembrete_id)

        self.view_pai.lembretes = [
            r for r in self.view_pai.lembretes if r["id"] != self.lembrete_id
        ]

        if not self.view_pai.lembretes:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    description=f"✅ Lembrete **{self.nome}** deletado. Nenhum lembrete cadastrado.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
            return

        self.view_pai.pagina = min(self.view_pai.pagina, len(self.view_pai.lembretes) - 1)
        await self.view_pai._render(interaction, nota=f"🗑️ '{self.nome}' deletado.")
        print(f"[Calendário] 🗑️  Lembrete #{self.lembrete_id} '{self.nome}' deletado.")

    @discord.ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary)
    async def voltar(self, interaction: discord.Interaction, button):
        await self.view_pai._render(interaction)


# ════════════════════════════════════════════════════════════
#  View — /teste-mensagem-evento
# ════════════════════════════════════════════════════════════

class TestarEventoSelectView(discord.ui.View):
    def __init__(self, lembretes: list, canal_destino: discord.TextChannel):
        super().__init__(timeout=60)
        self.canal_destino = canal_destino

        opcoes = []
        for r in lembretes[:25]:
            anual = bool(r["anual"])
            opcoes.append(discord.SelectOption(
                label=r["nome"][:80],
                value=str(r["id"]),
                description=f"{formatar_data_display(r['data_iso'], anual)} às {r['horario']} BRT",
            ))

        sel = discord.ui.Select(placeholder="Escolha o lembrete para testar...", options=opcoes)
        sel.callback = self._selecionado
        self.add_item(sel)

    async def _selecionado(self, interaction: discord.Interaction):
        lembrete_id = int(interaction.data["values"][0])
        bot = interaction.client
        # get_lembrete traz o BLOB completo
        row = await bot.db.get_lembrete(lembrete_id)
        if not row:
            await interaction.response.send_message("❌ Lembrete não encontrado.", ephemeral=True)
            return

        sucesso = await _enviar_lembrete(self.canal_destino, row)
        if sucesso:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    description=f"✅ Mensagem de teste enviada em {self.canal_destino.mention}.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        else:
            await interaction.response.send_message(
                "❌ Erro ao enviar o teste. Verifique o console.", ephemeral=True
            )


# ════════════════════════════════════════════════════════════
#  COG
# ════════════════════════════════════════════════════════════

class CalendarioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verificar_calendario_task.start()

    def cog_unload(self):
        self.verificar_calendario_task.cancel()

    # ── Task: verifica lembretes a cada hora exata (BRT) ────
    @tasks.loop(hours=1)
    async def verificar_calendario_task(self):
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return
        await self._disparar_lembretes()

    @verificar_calendario_task.before_loop
    async def before_verificar(self):
        """Aguarda até o próximo HH:00:00 BRT antes de iniciar o loop."""
        await self.bot.wait_until_ready()
        agora   = agora_brt()
        proxima = (agora + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        espera  = (proxima - agora).total_seconds()
        print(f"[Calendário] ⏳ Task inicia em {espera:.0f}s (próxima hora: {proxima.strftime('%H:%M BRT')})")
        await asyncio.sleep(espera)

    async def _disparar_lembretes(self):
        agora_now  = agora_brt()
        data_hoje  = agora_now.strftime("%Y-%m-%d")
        mes_dia    = agora_now.strftime("%m-%d")
        hora_atual = agora_now.strftime("%H:%M")
        ano_atual  = agora_now.year

        for guild in self.bot.guilds:
            pendentes = await self.bot.db.get_lembretes_pendentes_hoje(
                data_hoje, mes_dia, hora_atual, ano_atual
            )
            for row in pendentes:
                canal = guild.get_channel(row["canal_id"])
                if not canal:
                    canal = guild.get_channel(CANAL_ANUNCIOS)
                if not canal:
                    print(f"[Calendário] ⚠️  Canal {row['canal_id']} não encontrado para lembrete #{row['id']}")
                    continue

                sucesso = await _enviar_lembrete(canal, row)
                if sucesso:
                    await self.bot.db.marcar_lembrete_notificado(
                        row["id"],
                        ano_atual if bool(row["anual"]) else 9999,
                    )
                    print(f"[Calendário] ✅ Lembrete disparado: '{row['nome']}' → #{canal.name}")

    # ── /set-mensagem ────────────────────────────────────────
    @app_commands.command(
        name="set-mensagem",
        description="Cadastrar um lembrete no calendário (aniversários, eventos, etc.)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_mensagem_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetMensagemModal(self.bot))

    # ── /buscar-evento ───────────────────────────────────────
    @app_commands.command(
        name="buscar-evento",
        description="Ver, editar ou deletar lembretes cadastrados no calendário",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def buscar_evento_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.db:
            await interaction.followup.send("❌ Banco de dados indisponível.", ephemeral=True)
            return

        lembretes = list(await self.bot.db.get_lembretes_guild(interaction.guild.id))
        if not lembretes:
            await interaction.followup.send(
                "📭 Nenhum lembrete cadastrado ainda. Use `/set-mensagem` para criar.",
                ephemeral=True,
            )
            return

        lembretes = [_DictRow(dict(r)) for r in lembretes]
        row   = lembretes[0]
        embed = await _montar_embed_lembrete(row, interaction.guild)
        embed.description = f"Lembrete **1** de **{len(lembretes)}**"

        await interaction.followup.send(
            embed=embed,
            view=BuscarEventoView(lembretes, interaction.guild),
            ephemeral=True,
        )

    # ── /teste-mensagem-evento ───────────────────────────────
    @app_commands.command(
        name="teste-mensagem-evento",
        description="Dispara a mensagem de um lembrete aqui neste canal (para teste)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def teste_mensagem_evento_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.db:
            await interaction.followup.send("❌ Banco de dados indisponível.", ephemeral=True)
            return

        # get_lembretes_guild não traz BLOB — só pra listar
        lembretes = list(await self.bot.db.get_lembretes_guild(interaction.guild.id))
        if not lembretes:
            await interaction.followup.send(
                "📭 Nenhum lembrete cadastrado. Use `/set-mensagem` primeiro.",
                ephemeral=True,
            )
            return

        lembretes = [_DictRow(dict(r)) for r in lembretes]
        embed = discord.Embed(
            title="🧪 Teste de Mensagem — Selecione o lembrete",
            description=(
                f"A mensagem será enviada aqui em {interaction.channel.mention}, "
                "sem afetar o canal de anúncios."
            ),
            color=DORORO_COLOR,
        )
        await interaction.followup.send(
            embed=embed,
            view=TestarEventoSelectView(lembretes, interaction.channel),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(CalendarioCog(bot))