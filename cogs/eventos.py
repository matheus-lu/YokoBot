# ============================================================
#  COG: EVENTOS — Criar eventos agendados — Ondrakos
#  Fluxo completo: localização → informações → revisão
# ============================================================

import discord
from discord.ext import commands
from discord.ui import Modal, View
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
        AppCommandError = Exception
        command = staticmethod(_noop_decorator)
    app_commands = _FakeAppCommands()
import datetime
import asyncio
import calendar

DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)

# Mapeamento de frequência para a API do Discord
# RecurrenceRule só existe em versões mais recentes — usamos dict para montar manualmente
FREQ_NENHUMA    = "nenhuma"
FREQ_SEMANAL    = "semanal"
FREQ_QUINZENAL  = "quinzenal"
FREQ_MENSAL     = "mensal"
FREQ_ANUAL      = "anual"
FREQ_DIAS_UTEIS = "dias_uteis"

DIAS_SEMANA_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES_PT = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]

SEMANA_ORDINAL_PT = ["primeiro(a)", "segundo(a)", "terceiro(a)", "quarto(a)", "último(a)"]


def parse_datetime(data_str: str, hora_str: str) -> datetime.datetime | None:
    try:
        dia, mes, ano = data_str.strip().split("/")
        hora, minuto  = hora_str.strip().split(":")
        return datetime.datetime(
            int(ano), int(mes), int(dia), int(hora), int(minuto),
            tzinfo=datetime.timezone(datetime.timedelta(hours=-3)),
        )
    except Exception:
        return None


def semana_do_mes(dt: datetime.datetime) -> int:
    """Retorna qual ocorrência do dia da semana no mês (1-4, ou 5 = último)."""
    dia = dt.day
    ocorrencia = (dia - 1) // 7 + 1
    # Verificar se é o último do mês
    ultimo_dia = calendar.monthrange(dt.year, dt.month)[1]
    if dia + 7 > ultimo_dia:
        return 5  # último
    return ocorrencia


def opcoes_frequencia(dt: datetime.datetime) -> list[tuple[str, str]]:
    """Gera as opções de frequência baseadas na data escolhida."""
    dia_semana = DIAS_SEMANA_PT[dt.weekday()]
    dia        = dt.day
    mes        = MESES_PT[dt.month - 1]
    ordinal    = SEMANA_ORDINAL_PT[min(semana_do_mes(dt) - 1, 4)]
    eh_util    = dt.weekday() < 5

    opcoes = [("Não se repete", FREQ_NENHUMA)]
    opcoes.append((f"Semanalmente a cada {dia_semana}", FREQ_SEMANAL))
    opcoes.append((f"Quinzenalmente a cada {dia_semana}", FREQ_QUINZENAL))
    opcoes.append((f"No(a) {ordinal} {dia_semana} de cada mês", FREQ_MENSAL))
    opcoes.append((f"Anualmente no dia {dia:02d} de {mes}", FREQ_ANUAL))
    if eh_util:
        opcoes.append(("Todos os dias úteis (segunda a sexta-feira)", FREQ_DIAS_UTEIS))

    return opcoes


def montar_recurrence_rule(freq: str, inicio: datetime.datetime) -> dict | None:
    if freq == FREQ_NENHUMA:
        return None

    # start obrigatório pela API — converter para UTC ISO 8601
    inicio_utc = inicio.astimezone(datetime.timezone.utc)
    start_str  = inicio_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # Dias da semana: 0=Mon...6=Sun → API Discord usa 1=Mon...7=Sun
    wd   = inicio.weekday() + 1
    base = {"start": start_str, "interval": 1}

    if freq == FREQ_SEMANAL:
        return {**base, "frequency": 2, "by_weekday": [wd]}
    if freq == FREQ_QUINZENAL:
        return {**base, "frequency": 2, "interval": 2, "by_weekday": [wd]}
    if freq == FREQ_MENSAL:
        nth = semana_do_mes(inicio)
        if nth == 5:
            return {**base, "frequency": 1, "by_n_weekday": [{"day": wd, "n": -1}]}
        return {**base, "frequency": 1, "by_n_weekday": [{"day": wd, "n": nth}]}
    if freq == FREQ_ANUAL:
        return {**base, "frequency": 0}
    if freq == FREQ_DIAS_UTEIS:
        return {**base, "frequency": 2, "by_weekday": [1, 2, 3, 4, 5]}
    return None


# ══════════════════════════════════════════════════════════
#  PASSO 1 — Escolha do tipo de local
# ══════════════════════════════════════════════════════════
class EscolherLocalView(View):
    def __init__(self, bot, user_id: int, canais_palco: list, canais_voz: list):
        super().__init__(timeout=120)
        self.bot          = bot
        self.user_id      = user_id
        self.canais_palco = canais_palco
        self.canais_voz   = canais_voz

    async def _check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu não é seu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Canal palco", emoji="🎙️", style=discord.ButtonStyle.primary, row=0)
    async def palco(self, interaction: discord.Interaction, button):
        if not await self._check(interaction): return
        if not self.canais_palco:
            await interaction.response.send_message("❌ Nenhum canal palco encontrado.", ephemeral=True)
            return
        opcoes = [discord.SelectOption(label=c.name, value=str(c.id)) for c in self.canais_palco[:25]]
        await interaction.response.edit_message(
            embed=discord.Embed(title="🎙️ Selecione o canal palco", color=DORORO_COLOR),
            view=SelecionarCanalView(opcoes, "palco", self.bot, self.user_id),
        )

    @discord.ui.button(label="Canal de voz", emoji="🔊", style=discord.ButtonStyle.primary, row=0)
    async def voz(self, interaction: discord.Interaction, button):
        if not await self._check(interaction): return
        if not self.canais_voz:
            await interaction.response.send_message("❌ Nenhum canal de voz encontrado.", ephemeral=True)
            return
        opcoes = [discord.SelectOption(label=c.name, value=str(c.id)) for c in self.canais_voz[:25]]
        await interaction.response.edit_message(
            embed=discord.Embed(title="🔊 Selecione o canal de voz", color=DORORO_COLOR),
            view=SelecionarCanalView(opcoes, "voz", self.bot, self.user_id),
        )

    @discord.ui.button(label="Em outro lugar", emoji="📍", style=discord.ButtonStyle.secondary, row=0)
    async def externo(self, interaction: discord.Interaction, button):
        if not await self._check(interaction): return
        await interaction.response.send_modal(LocalExternoModal(self.bot, self.user_id))


class SelecionarCanalView(View):
    def __init__(self, opcoes, tipo_canal, bot, user_id):
        super().__init__(timeout=60)
        self.tipo_canal = tipo_canal
        self.bot        = bot
        self.user_id    = user_id
        sel = discord.ui.Select(placeholder="Escolha o canal...", options=opcoes)
        sel.callback = self._selecionado
        self.add_item(sel)

    async def _selecionado(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu não é seu.", ephemeral=True)
            return
        canal = interaction.guild.get_channel(int(interaction.data["values"][0]))
        await interaction.response.send_modal(
            InfoEventoModal(self.bot, self.user_id, tipo_local=self.tipo_canal, canal=canal, local_texto=None)
        )


class LocalExternoModal(Modal):
    def __init__(self, bot, user_id):
        super().__init__(title="📍 Local do Evento")
        self.bot     = bot
        self.user_id = user_id
        self.local   = TextInput(label="Link ou endereço", placeholder="Ex: https://... ou Rua X, 123", required=True, max_length=100)
        self.add_item(self.local)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            InfoEventoModal(self.bot, self.user_id, tipo_local="externo", canal=None, local_texto=self.local.value)
        )


# ══════════════════════════════════════════════════════════
#  PASSO 2 — Informações do evento
# ══════════════════════════════════════════════════════════
class InfoEventoModal(Modal):
    def __init__(self, bot, user_id, tipo_local, canal, local_texto):
        super().__init__(title="📋 Informações do Evento")
        self.bot         = bot
        self.user_id     = user_id
        self.tipo_local  = tipo_local
        self.canal       = canal
        self.local_texto = local_texto

        self.nome = TextInput(label="Assunto do evento", placeholder="Ex: 🐉 Ritual do Clã", required=True, max_length=100)
        self.data = TextInput(label="Data de início (DD/MM/AAAA)", placeholder="Ex: 25/12/2026", required=True, max_length=10)
        self.hora = TextInput(label="Hora de início (HH:MM) — BRT", placeholder="Ex: 20:00", required=True, max_length=5)
        self.descricao = TextInput(
            label="Descrição (opcional)",
            style=discord.TextStyle.paragraph,
            placeholder="Markdown, links e quebras de linha são suportados.",
            required=False, max_length=1000,
        )
        self.add_item(self.nome)
        self.add_item(self.data)
        self.add_item(self.hora)
        self.add_item(self.descricao)

    async def on_submit(self, interaction: discord.Interaction):
        inicio = parse_datetime(self.data.value, self.hora.value)
        if not inicio:
            await interaction.response.send_message("❌ Data ou hora inválida. Use DD/MM/AAAA e HH:MM.", ephemeral=True)
            return

        agora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
        if inicio <= agora:
            await interaction.response.send_message("❌ A data/hora precisa ser no futuro.", ephemeral=True)
            return

        dados = {
            "nome":        self.nome.value,
            "descricao":   self.descricao.value or "",
            "inicio":      inicio,
            "tipo_local":  self.tipo_local,
            "canal":       self.canal,
            "local_texto": self.local_texto,
        }

        # Passo 2b — escolher frequência
        freqs = opcoes_frequencia(inicio)
        opcoes_sel = [discord.SelectOption(label=label, value=value) for label, value in freqs]
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔁 Frequência do evento",
                description="Com que frequência este evento se repete?",
                color=DORORO_COLOR,
            ),
            view=FrequenciaView(opcoes_sel, dados, self.bot, self.user_id),
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════
#  PASSO 2b — Frequência
# ══════════════════════════════════════════════════════════
class FrequenciaView(View):
    def __init__(self, opcoes, dados, bot, user_id):
        super().__init__(timeout=60)
        self.dados   = dados
        self.bot     = bot
        self.user_id = user_id
        sel = discord.ui.Select(placeholder="Escolha a frequência...", options=opcoes)
        sel.callback = self._selecionada
        self.add_item(sel)

    async def _selecionada(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu não é seu.", ephemeral=True)
            return
        self.dados["frequencia"] = interaction.data["values"][0]
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🖼️ Imagem de apresentação",
                description=(
                    "Envie uma imagem para o evento neste canal.\n"
                    "Recomendado: mínimo **800×320px**.\n\n"
                    "Digite **pular** para criar sem imagem.\n"
                    "Digite **cancelar** para cancelar."
                ),
                color=DORORO_COLOR,
            ),
            view=None,
        )
        # Aguardar imagem por mensagem
        def check(m):
            return m.author.id == self.user_id and m.channel.id == interaction.channel.id

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Tempo esgotado.", ephemeral=True)
            return

        if msg.content.strip().lower() == "cancelar":
            try:
                interaction.client.mensagens_deletadas_pelo_bot[msg.id] = {"comando": "/evento"}
                await msg.delete()
            except Exception: pass
            await interaction.followup.send("❌ Cancelado.", ephemeral=True)
            return

        imagem_bytes = None
        if msg.content.strip().lower() != "pular" and msg.attachments:
            att = msg.attachments[0]
            if att.content_type and att.content_type.startswith("image"):
                try:
                    imagem_bytes = await att.read()
                except Exception as e:
                    await interaction.followup.send(f"⚠️ Erro ao baixar imagem: {e}", ephemeral=True)

        try:
            interaction.client.mensagens_deletadas_pelo_bot[msg.id] = {"comando": "/evento"}
            await msg.delete()
        except Exception: pass

        self.dados["imagem"] = imagem_bytes

        # Passo 3 — revisão
        await _mostrar_revisao(interaction, self.dados, self.bot, self.user_id)


# ══════════════════════════════════════════════════════════
#  PASSO 3 — Revisão
# ══════════════════════════════════════════════════════════
async def _mostrar_revisao(interaction, dados, bot, user_id):
    inicio   = dados["inicio"]
    freq_val = dados.get("frequencia", FREQ_NENHUMA)
    freqs    = dict(opcoes_frequencia(inicio))
    freq_label = next((k for k, v in freqs.items() if v == freq_val), "Não se repete")

    if dados["tipo_local"] == "palco":
        local_str = f"🎙️ {dados['canal'].name}" if dados["canal"] else "—"
    elif dados["tipo_local"] == "voz":
        local_str = f"🔊 {dados['canal'].name}" if dados["canal"] else "—"
    else:
        local_str = f"📍 {dados.get('local_texto', '—')}"

    embed = discord.Embed(title="📋 Revisar Evento", color=DORORO_COLOR)
    embed.add_field(name="📌 Nome",        value=dados["nome"],                                       inline=False)
    embed.add_field(name="📍 Local",       value=local_str,                                           inline=True)
    embed.add_field(name="🕐 Início",      value=f"<t:{int(inicio.timestamp())}:F>",                  inline=True)
    embed.add_field(name="🔁 Frequência",  value=freq_label,                                          inline=True)
    if dados["descricao"]:
        embed.add_field(name="📝 Descrição", value=dados["descricao"][:512], inline=False)
    embed.add_field(name="🖼️ Imagem",      value="✅ Incluída" if dados.get("imagem") else "Nenhuma", inline=True)
    embed.set_footer(text="Confirme ou volte para editar.")

    await interaction.followup.send(
        embed=embed,
        view=RevisaoView(dados, bot, user_id),
        ephemeral=True,
    )


class RevisaoView(View):
    def __init__(self, dados, bot, user_id):
        super().__init__(timeout=120)
        self.dados   = dados
        self.bot     = bot
        self.user_id = user_id

    @discord.ui.button(label="✅ Confirmar e Criar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este botão não é seu.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await _criar_evento(interaction, self.dados)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este botão não é seu.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=discord.Embed(description="❌ Criação de evento cancelada.", color=discord.Color.red()),
            view=None,
        )


# ══════════════════════════════════════════════════════════
#  CRIAR EVENTO
# ══════════════════════════════════════════════════════════
async def _criar_evento(interaction, dados):
    inicio   = dados["inicio"]
    freq_val = dados.get("frequencia", FREQ_NENHUMA)

    # end_time obrigatório para external; para voz/palco é opcional — usa +2h como padrão
    fim = inicio + datetime.timedelta(hours=2)

    try:
        kwargs = dict(
            name=dados["nome"],
            description=dados["descricao"] or None,
            start_time=inicio,
            end_time=fim,
            privacy_level=discord.PrivacyLevel.guild_only,
        )

        if dados["tipo_local"] in ("palco", "voz"):
            kwargs["channel"]     = dados["canal"]
            kwargs["entity_type"] = discord.EntityType.stage_instance if dados["tipo_local"] == "palco" else discord.EntityType.voice
        else:
            kwargs["entity_type"] = discord.EntityType.external
            kwargs["location"]    = dados.get("local_texto", "A definir")

        if dados.get("imagem"):
            kwargs["image"] = dados["imagem"]

        evento = await interaction.guild.create_scheduled_event(**kwargs)

        # Aplicar recorrência via HTTP direto (suporte independente de versão)
        rr = montar_recurrence_rule(freq_val, inicio)
        if rr:
            try:
                await interaction.client.http.request(
                    discord.http.Route(
                        "PATCH", "/guilds/{guild_id}/scheduled-events/{event_id}",
                        guild_id=interaction.guild.id, event_id=evento.id,
                    ),
                    json={"recurrence_rule": rr},
                )
            except Exception as e:
                print(f"[Eventos] Aviso: não foi possível aplicar recorrência: {e}")

        freqs = dict(opcoes_frequencia(inicio))
        freq_label = next((k for k, v in freqs.items() if v == freq_val), "Não se repete")

        embed = discord.Embed(title="✅ Evento criado com sucesso!", color=DORORO_COLOR)
        embed.add_field(name="📌 Nome",       value=evento.name,                                  inline=False)
        embed.add_field(name="🕐 Início",     value=f"<t:{int(inicio.timestamp())}:F>",           inline=True)
        embed.add_field(name="🔁 Frequência", value=freq_label,                                   inline=True)
        embed.add_field(
            name="🔗 Link",
            value=f"[Ver evento](https://discord.com/events/{interaction.guild.id}/{evento.id})",
            inline=False,
        )
        embed.set_footer(text="© Ondrakos · 水の竜")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Sem permissão. O bot precisa da permissão **Gerenciar Eventos**.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao criar evento: {e}", ephemeral=True)


# ══════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════
class EventosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="evento", description="Criar um evento agendado no servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def evento_cmd(self, interaction: discord.Interaction):
        canais_palco = [c for c in interaction.guild.channels if isinstance(c, discord.StageChannel)]
        canais_voz   = [c for c in interaction.guild.channels if isinstance(c, discord.VoiceChannel)]

        embed = discord.Embed(
            title="📅 Criar Evento — Ondrakos",
            description=(
                "**Onde é seu evento?**\n\n"
                "🎙️ **Canal palco** — Ótimo para eventos de áudio maiores.\n"
                "🔊 **Canal de voz** — Voz, vídeo e compartilhamento de tela.\n"
                "📍 **Em outro lugar** — Link externo ou endereço."
            ),
            color=DORORO_COLOR,
        )
        await interaction.response.send_message(
            embed=embed,
            view=EscolherLocalView(self.bot, interaction.user.id, canais_palco, canais_voz),
            ephemeral=True,
        )

    @app_commands.command(name="cancelar-evento", description="Cancelar um evento agendado")
    @app_commands.checks.has_permissions(administrator=True)
    async def cancelar_evento_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        eventos = list(interaction.guild.scheduled_events)
        if not eventos:
            await interaction.followup.send("Nenhum evento agendado no momento.", ephemeral=True)
            return
        opcoes = [
            discord.SelectOption(
                label=e.name[:100],
                value=str(e.id),
                description=f"Início: {e.start_time.strftime('%d/%m %H:%M')} BRT" if e.start_time else "",
            )
            for e in eventos[:25]
        ]
        view = CancelarEventoView(opcoes)
        await interaction.followup.send(
            embed=discord.Embed(title="🗑️ Cancelar Evento", description="Selecione o evento:", color=DORORO_COLOR),
            view=view,
            ephemeral=True,
        )


class CancelarEventoView(View):
    def __init__(self, opcoes):
        super().__init__(timeout=60)
        sel = discord.ui.Select(placeholder="Escolha o evento...", options=opcoes)
        sel.callback = self._selecionado
        self.add_item(sel)

    async def _selecionado(self, interaction: discord.Interaction):
        evento_id = int(interaction.data["values"][0])
        evento = interaction.guild.get_scheduled_event(evento_id)
        if not evento:
            await interaction.response.send_message("❌ Evento não encontrado.", ephemeral=True)
            return

        inicio_str = f"<t:{int(evento.start_time.timestamp())}:F>" if evento.start_time else "—"
        embed = discord.Embed(
            title="⚠️ Confirmar cancelamento",
            description=f"Tem certeza que deseja cancelar este evento?",
            color=discord.Color.orange(),
        )
        embed.add_field(name="📌 Nome",    value=evento.name,  inline=True)
        embed.add_field(name="🕐 Início",  value=inicio_str,   inline=True)
        embed.set_footer(text="Esta ação não pode ser desfeita.")

        await interaction.response.edit_message(
            embed=embed,
            view=ConfirmarCancelamentoView(evento_id, evento.name),
        )


class ConfirmarCancelamentoView(View):
    def __init__(self, evento_id: int, nome: str):
        super().__init__(timeout=60)
        self.evento_id = evento_id
        self.nome      = nome

    @discord.ui.button(label="✅ Confirmar cancelamento", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button):
        try:
            evento = interaction.guild.get_scheduled_event(self.evento_id)
            if not evento:
                await interaction.response.edit_message(
                    embed=discord.Embed(description="❌ Evento não encontrado.", color=discord.Color.red()),
                    view=None,
                )
                return
            await evento.delete()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="✅ Evento cancelado",
                    description=f"O evento **{self.nome}** foi cancelado com sucesso.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception as e:
            await interaction.response.edit_message(
                embed=discord.Embed(description=f"❌ Erro: {e}", color=discord.Color.red()),
                view=None,
            )

    @discord.ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary)
    async def voltar(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🗑️ Cancelar Evento",
                description="Selecione o evento que deseja cancelar:",
                color=DORORO_COLOR,
            ),
            view=None,
        )
        # Rebuscar eventos e reexibir o select
        eventos = list(interaction.guild.scheduled_events)
        if not eventos:
            return
        opcoes = [
            discord.SelectOption(
                label=e.name[:100],
                value=str(e.id),
                description=f"Início: {e.start_time.strftime('%d/%m %H:%M')} BRT" if e.start_time else "",
            )
            for e in eventos[:25]
        ]
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="🗑️ Cancelar Evento",
                description="Selecione o evento que deseja cancelar:",
                color=DORORO_COLOR,
            ),
            view=CancelarEventoView(opcoes),
        )


async def setup(bot):
    await bot.add_cog(EventosCog(bot))