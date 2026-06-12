# ============================================================
#  MAIN — Arquivo principal do Ondrakos Bot  水の竜
#  Carrega o banco de dados, cogs e inicia o bot.
# ============================================================
#
#  ESTRUTURA DO PROJETO:
#  ├── main.py          ← VOCÊ ESTÁ AQUI (anúncios + inicialização)
#  ├── config.py        ← IDs, tokens, caminhos
#  ├── database.py      ← Banco SQLite
#  ├── utils.py         ← Funções de imagem compartilhadas
#  └── cogs/
#      ├── tickets.py   ✅ Migrado
#      ├── musica.py    ✅ Migrado
#      ├── logs.py      ✅ Migrado
#      ├── boasvindas.py ✅ Migrado
#      ├── punicoes.py  ✅ Migrado
#      └── xp.py        ✅ Sistema de XP e Ranking
#
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discord
from discord.ext import commands
try:
    from discord import app_commands
except ImportError:
    # discord.py < 2.0 nao tem app_commands, cria um stub compativel
    from types import SimpleNamespace
    app_commands = SimpleNamespace(
        checks=SimpleNamespace(
            has_permissions=lambda **kw: (lambda f: f)
        ),
        AppCommandError=Exception,
        errors=SimpleNamespace(
            MissingPermissions=Exception,
            CommandOnCooldown=Exception
        )
    )
from discord.ui import View, Button, Modal, TextInput, Select
try:
    _TextStyle = discord.TextStyle
except AttributeError:
    try:
        _TextStyle = discord.InputTextStyle
    except AttributeError:
        from discord.enums import InputTextStyle as _TextStyle
import config
from database import Database
from utils import baixar_fonte


# ── Intents ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents, enable_debug_events=True)

# ── Check global: só verificados usam slash commands ──────
CARGO_VERIFICADO_ID = 1511225573655973958

@bot.tree.interaction_check
async def verificacao_global(interaction: discord.Interaction) -> bool:
    # Admins sempre passam
    if interaction.user.guild_permissions.administrator:
        return True
    cargo = interaction.guild.get_role(CARGO_VERIFICADO_ID)
    if cargo and cargo in interaction.user.roles:
        return True
    await interaction.response.send_message(
        "🔒 Você precisa ser verificado para usar comandos!\n"
        "Vá ao canal de regras e clique em **Iniciar Verificação**.",
        ephemeral=True,
    )
    return False

# Adicionar CommandTree se não existir (discord.py < 2.0 não tem bot.tree)
if not hasattr(bot, 'tree'):
    from discord.ext.commands import Bot as _Bot
    try:
        from discord import app_commands as _apc
        bot.tree = _apc.CommandTree(bot)
    except Exception:
        # Stub mínimo pra não quebrar os decorators
        class _FakeTree:
            def command(self, **kw):
                return lambda f: f
            def error(self, f):
                return f
            async def sync(self):
                pass
            def __call__(self, **kw):
                return lambda f: f
        bot.tree = _FakeTree()

# Referência global do banco — acessível via bot.db em qualquer cog
bot.db = None


# ── Lista de Cogs para carregar ────────────────────────────
COGS_INICIAIS = [
    "cogs.tickets",
    "cogs.musica",
    "cogs.logs",
    "cogs.boasvindas",
    "cogs.punicoes",
    "cogs.xp",
    "cogs.ia_jornalista",
    "cogs.setup",
    "cogs.signos",
    "cogs.verificacao",
    "cogs.eventos",
    "cogs.calendario",
    "cogs.historias",
]


# ── Handler Global de Erros ────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.", ephemeral=True
        )
    elif isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ Aguarde {error.retry_after:.1f}s antes de usar este comando novamente.",
            ephemeral=True,
        )
    else:
        try:
            await interaction.response.send_message(
                f"❌ Erro inesperado: {str(error)}", ephemeral=True
            )
        except discord.InteractionResponded:
            pass
        raise error


# ================================================================== #
#  CÓDIGO TEMPORÁRIO — Funcionalidades ainda não migradas para Cogs
# ================================================================== #

import io, asyncio, re

# IDs de mensagens deletadas intencionalmente pelo bot (não devem gerar log)
bot.mensagens_ignorar_delete = set()
bot.mensagens_deletadas_pelo_bot = {}  # {msg_id: {"comando": "/nome"}} — log especial
bot.ignorar_log_voz = set()  # guild_ids onde o bot entrou via /som (ignorar log)
bot.dj_parado_por = {}  # {guild_id: user | None}
bot.dj_convocado_por = {}  # {guild_id: user}
bot.ignorar_voz_bot = False  # True quando /som está tocando


# ── Cor padrão do tema Ondrakos ─────────────────────────
DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)


CANAL_DIVULGACAO_ID = 1484792878579581009

TITULO_SITE = "**🐉 │▸Clã do Dragão Ondrakos**"
DESCRICAO_SITE = (
    "⛩️ ⧽ Bem-vindo ao Santuário do Dragão\n\n"
    "O Clã do Dragão é o espaço oficial do nosso servidor › um lugar inspirado no Japão, "
    "no sobrenatural e na energia ancestral dos dragões.\n\n"
    "Aqui, amizades, histórias, ideias e projetos ganham forma entre portais, mistérios, "
    "espíritos e lendas. O servidor reúne membros que querem conversar, criar, participar "
    "de eventos, usar serviços, interagir com a RyuIA e fazer parte de uma comunidade com identidade própria.\n\n"
    "Neste santuário, você encontra canais para bate-papo, música, tickets, serviços, IA, "
    "cargos, signos japoneses, avisos e tudo que mantém o clã vivo e organizado.\n\n"
    "Mais do que um servidor, este é um ponto de encontro para quem deseja fazer parte de "
    "algo místico, criativo e acolhedor.\n\n"
    "🐉 ⧽ Respeito, união e presença guiam o nosso clã.\n"
    "⛩️ ⧽ Mas todo portal tem regras… e cada escolha molda o caminho de quem permanece.\n\n"
    "🌙 ⧽ Se você chegou até aqui, o dragão permitiu sua entrada.\n"
    "Explore, participe, respeite o santuário… e escreva sua própria jornada entre nós."
)
FOOTER_SITE = "-# © Ondrakos · 水の竜"


class BotaoSite(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="⛩️ Visitar Site",
            url=config.SITE_URL,
            style=discord.ButtonStyle.link,
        )


class SiteLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container = discord.ui.Container(
        discord.ui.MediaGallery(
            discord.MediaGalleryItem("attachment://site.png"),
        ),
        discord.ui.TextDisplay(TITULO_SITE),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(DESCRICAO_SITE),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.Section(
            discord.ui.TextDisplay(FOOTER_SITE),
            accessory=BotaoSite(),
        ),
        accent_color=DORORO_COLOR,
    )


class SiteLayoutSemImagem(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container = discord.ui.Container(
        discord.ui.TextDisplay(TITULO_SITE),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(DESCRICAO_SITE),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.Section(
            discord.ui.TextDisplay(FOOTER_SITE),
            accessory=BotaoSite(),
        ),
        accent_color=DORORO_COLOR,
    )


REGRAS_TITULO = "**🐉 │▸Os 10 Mandamentos do clã Ondrakos**"
REGRAS_FOOTER = "-# © Ondrakos · 水の竜"

REGRAS_BODY = """\
›1. Respeite todos os membros
🫡⧽Trate todos com respeito. Brincadeiras são bem-vindas, mas ofensas, humilhações, preconceito ou ataques pessoais não serão aceitos.

›2. Não perturbe a paz do clã
👾⧽Evite spam, flood, mensagens repetidas, gritos exagerados em caps lock ou qualquer atitude que atrapalhe a conversa dos outros.

›3. Use os canais corretamente
⚖️⧽Cada canal tem sua função. Poste mensagens, mídias, comandos, divulgações e pedidos nos lugares certos para manter o servidor organizado.

›4. Proibido conteúdo pesado ou inadequado
🔞⧽Nada de conteúdo explícito, chocante, ilegal, gore, NSFW fora de local permitido, apologia ao crime ou qualquer coisa que coloque o servidor em risco.

›5. Não cause brigas desnecessárias
🗯️⧽Discussões acontecem, mas provocar, debochar, perseguir ou alimentar confusão não será tolerado. Resolva com maturidade ou chame a equipe.

›6. Respeite a equipe
👑⧽Moderadores e administradores estão aqui para manter o equilíbrio do santuário. Se discordar de algo, converse com calma pelo canal correto.

›7. Não divulgue sem permissão
🛜⧽Links, servidores, redes sociais, vendas ou divulgações só podem ser enviados se forem permitidos pela equipe ou no canal apropriado.

›8. Proteja sua conta e sua privacidade
👤⧽Não compartilhe dados pessoais seus ou de outras pessoas. Cuidado com golpes, links suspeitos e mensagens privadas estranhas.

›9. Use os tickets com responsabilidade
🎟️⧽Abra ticket apenas quando realmente precisar de ajuda, serviço ou atendimento. Explique o motivo com clareza e aguarde a resposta da equipe.

›10. Honre o espírito do dragão
👥⧽Entre para somar, conversar, criar amizades e manter a energia do servidor boa. Quem desrespeitar o clã poderá receber aviso, mute, kick ou ban."""

class RegrasLayout(discord.ui.LayoutView):
    def __init__(self, tem_img=False, tem_sep=False):
        super().__init__(timeout=None)

        itens = []
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay(REGRAS_TITULO))
        itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay(REGRAS_BODY))
        itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        if tem_sep:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://mandamentos.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        itens.append(discord.ui.TextDisplay(REGRAS_FOOTER))

        self.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))

async def setup_regras_embed(bot):
    CANAL_REGRAS_ID = 1480660903363084318
    canal = bot.get_channel(CANAL_REGRAS_ID)
    if not canal:
        return
        
    async for msg in canal.history(limit=10):
        if msg.author == bot.user:
            try:
                raw_data = await bot.http.get_message(canal.id, msg.id)
                if "Os 10 Mandamentos" in str(raw_data):
                    print("✅ Embed de regras já existe, mantendo.")
                    return
            except Exception:
                pass

    _base = os.path.dirname(os.path.abspath(__file__))
    _img_path = os.path.join(_base, "mandamentos.png")
    _sep_path = os.path.join(_base, "sep_anuncio.png")
    tem_img = os.path.exists(_img_path) and os.path.getsize(_img_path) < 9_000_000
    tem_sep = os.path.exists(_sep_path) and os.path.getsize(_sep_path) < 9_000_000

    view = RegrasLayout(tem_img=tem_img, tem_sep=tem_sep)
    arquivos = []
    if tem_img:
        arquivos.append(discord.File(_img_path, filename="mandamentos.png"))
    if tem_sep:
        arquivos.append(discord.File(_sep_path, filename="sep_anuncio.png"))

    if arquivos:
        await canal.send(files=arquivos, view=view)
    else:
        await canal.send(view=view)
    print("✅ Embed de regras criado!")


async def setup_site_embed(bot):
    """Cria o embed do site no canal de divulgação se não existir."""
    canal = bot.get_channel(CANAL_DIVULGACAO_ID)
    if not canal:
        print("⚠️ Canal de divulgação não encontrado!")
        return

    async for msg in canal.history(limit=20):
        if msg.author == bot.user:
            try:
                raw_data = await bot.http.get_message(canal.id, msg.id)
                if "Visitar Site" in str(raw_data) or "Clã do Dragão Ondrakos" in str(raw_data):
                    print("✅ Embed do site já existe, mantendo.")
                    return
            except Exception:
                pass

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site.png")
    if os.path.exists(img_path):
        arquivo = discord.File(img_path, filename="site.png")
        await canal.send(view=SiteLayout(), files=[arquivo])
    else:
        await canal.send(view=SiteLayoutSemImagem())
    print("✅ Embed do site criado!")


@bot.tree.command(name="site", description="Reenviar embed do site do Ondrakos")
@app_commands.checks.has_permissions(administrator=True)
async def site(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    canal = bot.get_channel(CANAL_DIVULGACAO_ID)
    if canal is None:
        await interaction.followup.send("Canal de divulgação não encontrado.", ephemeral=True)
        return
    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site.png")
    if os.path.exists(img_path):
        arquivo = discord.File(img_path, filename="site.png")
        await canal.send(view=SiteLayout(), files=[arquivo])
    else:
        await canal.send(view=SiteLayoutSemImagem())
    await interaction.followup.send("✅ Embed do site enviado!", ephemeral=True)


# ── Sistema de Anúncio com Confirmação de Presença ────────

# Guarda temporariamente os dados do anúncio enquanto espera a imagem
anuncio_pendente = {}
editar_pendente = {}  # user_id -> target_msg
remandar_pendente = {}

# Guarda as confirmações de presença por mensagem_id
anuncio_presencas = {}


def resolver_mencoes(texto, guild):
    """Converte @nome, @cargo e IDs puros em menções reais do Discord."""
    if not texto:
        return texto

    def substituir_id(match):
        id_str = match.group(0)
        uid = int(id_str)
        member = guild.get_member(uid)
        if member:
            return member.mention
        role = guild.get_role(uid)
        if role:
            return role.mention
        return id_str

    texto = re.sub(r"\b(\d{17,20})\b", substituir_id, texto)

    for role in guild.roles:
        if role.name == "@everyone":
            continue
        padrao = re.compile(re.escape("@" + role.name), re.IGNORECASE)
        texto = padrao.sub(role.mention, texto)

    for member in guild.members:
        for nome in [member.display_name, member.name]:
            padrao = re.compile(re.escape("@" + nome), re.IGNORECASE)
            texto = padrao.sub(member.mention, texto)

    return texto


def montar_texto_mencao(texto_mencoes, guild, frase_custom=""):
    """Converte o campo de menções em texto formatado + content pra ping."""
    if not texto_mencoes or not texto_mencoes.strip():
        return None, None

    convertido = resolver_mencoes(texto_mencoes.strip(), guild)
    mencoes = re.findall(r"<@[!&]?\d+>", convertido)

    tem_everyone = "@everyone" in texto_mencoes
    tem_here = "@here" in texto_mencoes

    if tem_everyone:
        mencoes.insert(0, "@everyone")
    if tem_here:
        mencoes.insert(0, "@here")

    if not mencoes:
        return None, None

    if frase_custom:
        if len(mencoes) == 1:
            texto_formatado = mencoes[0] + " " + frase_custom
        else:
            texto_formatado = " | ".join(mencoes) + " " + frase_custom
    else:
        if len(mencoes) == 1:
            texto_formatado = mencoes[0] + " você foi convocado(a)"
        else:
            texto_formatado = " | ".join(mencoes) + " vocês foram convocados(as)"

    content = " ".join(mencoes)
    return texto_formatado, content


class AnuncioPresencaView(View):
    """Botões de confirmação de presença — persistentes com banco de dados."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirmar Presença", style=discord.ButtonStyle.success, emoji="✅", row=0, custom_id="anuncio_confirmar")
    async def confirmar(self, interaction: discord.Interaction, button: Button):
        msg_id = interaction.message.id
        uid = interaction.user.id
        nome = interaction.user.display_name

        try:
            if hasattr(interaction.client, 'db') and interaction.client.db:
                await interaction.client.db.registrar_presenca(msg_id, uid, nome, "confirmado")
        except Exception as e:
            print("Erro ao salvar presença: " + str(e))

        if msg_id not in anuncio_presencas:
            anuncio_presencas[msg_id] = {"confirmados": {}, "ausentes": {}}
        anuncio_presencas[msg_id]["ausentes"].pop(uid, None)
        anuncio_presencas[msg_id]["confirmados"][uid] = nome

        await interaction.response.send_message("✅ Presença confirmada!", ephemeral=True)

    @discord.ui.button(label="Não comparecerei", style=discord.ButtonStyle.danger, emoji="❌", row=0, custom_id="anuncio_ausente")
    async def ausente(self, interaction: discord.Interaction, button: Button):
        msg_id = interaction.message.id
        uid = interaction.user.id
        nome = interaction.user.display_name

        try:
            if hasattr(interaction.client, 'db') and interaction.client.db:
                await interaction.client.db.registrar_presenca(msg_id, uid, nome, "ausente")
        except Exception as e:
            print("Erro ao salvar presença: " + str(e))

        if msg_id not in anuncio_presencas:
            anuncio_presencas[msg_id] = {"confirmados": {}, "ausentes": {}}
        anuncio_presencas[msg_id]["confirmados"].pop(uid, None)
        anuncio_presencas[msg_id]["ausentes"][uid] = nome

        await interaction.response.send_message("❌ Ausência registrada!", ephemeral=True)

    @discord.ui.button(label="Ver Lista", style=discord.ButtonStyle.primary, emoji="📋", row=0, custom_id="anuncio_ver_lista")
    async def ver_lista(self, interaction: discord.Interaction, button: Button):
        msg_id = interaction.message.id

        dados = {"confirmados": {}, "ausentes": {}}
        try:
            if hasattr(interaction.client, 'db') and interaction.client.db:
                dados = await interaction.client.db.get_presencas(msg_id)
        except Exception:
            dados = anuncio_presencas.get(msg_id, {"confirmados": {}, "ausentes": {}})

        confirmados = list(dados["confirmados"].values())
        ausentes = list(dados["ausentes"].values())

        if confirmados:
            lista_conf = "\n".join(["✅ " + n for n in confirmados])
        else:
            lista_conf = "Ninguém confirmou ainda"
        
        if ausentes:
            lista_aus = "\n".join(["❌ " + n for n in ausentes])
        else:
            lista_aus = "Ninguém informou ausência"

        texto = (
            "📋 **Lista de Presença**\n\n"
            f"**Confirmados ({len(confirmados)})**\n{lista_conf}\n\n"
            f"**Ausentes ({len(ausentes)})**\n{lista_aus}\n\n"
            "-# © Ondrakos · 水の竜"
        )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(texto), accent_color=DORORO_COLOR))
        await interaction.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(label="Avisar Confirmados", style=discord.ButtonStyle.secondary, emoji="🔔", row=1, custom_id="anuncio_avisar")
    async def avisar(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este botão.", ephemeral=True)
            return

        msg_id = interaction.message.id

        dados = {"confirmados": {}, "ausentes": {}}
        try:
            if hasattr(interaction.client, 'db') and interaction.client.db:
                dados = await interaction.client.db.get_presencas(msg_id)
        except Exception:
            dados = anuncio_presencas.get(msg_id, {"confirmados": {}, "ausentes": {}})

        confirmados = dados["confirmados"]

        if not confirmados:
            await interaction.response.send_message("⚠️ Ninguém confirmou presença ainda.", ephemeral=True)
            return

        mencoes = " ".join(["<@" + str(uid) + ">" for uid in confirmados.keys()])
        texto = "🔔 " + mencoes + " — este é um lembrete do anúncio acima!"

        await interaction.response.send_message(
            content=texto,
            allowed_mentions=discord.AllowedMentions(users=True),
        )


class AnuncioModal(Modal):
    def __init__(self, canal_id: int):
        super().__init__(title="🐉 Criar Anúncio — Ondrakos")
        self.canal_id = canal_id
        self.titulo = TextInput(
            label="Título",
            placeholder="Ex: 🐉 Evento Especial — Ritual do Clã",
            required=True, max_length=256,
        )
        self.mensagem = TextInput(
            label="Mensagem",
            style=_TextStyle.paragraph,
            placeholder="Digite o conteúdo do anúncio...",
            required=True, max_length=4000,
        )
        self.mencoes = TextInput(
            label="Menções (quem será convocado)",
            placeholder="@Nome, ID ou @Cargo. Ex: @Fulano 123456789012345678 @Staff",
            required=False, max_length=500,
        )
        self.frase_convocacao = TextInput(
            label="Frase de convocação (opcional)",
            placeholder="Ex: o clã convoca vocês para o ritual (padrão: você foi convocado)",
            required=False, max_length=200,
        )
        self.evento = TextInput(
            label="É um evento? (sim = botões de presença)",
            placeholder="sim ou não",
            required=False, max_length=10, default="não",
        )
        self.divisores = TextInput(
            label="Usar divisores? (sim/não)",
            placeholder="sim ou não",
            required=False, max_length=10, default="sim",
        )
        self.add_item(self.titulo)
        self.add_item(self.mensagem)
        self.add_item(self.mencoes)
        self.add_item(self.frase_convocacao)
        self.add_item(self.divisores)

    async def on_submit(self, interaction: discord.Interaction):
        eh_evento = self.evento.value.strip().lower() in ["sim", "s", "yes"]
        usar_divisores = self.divisores.value.strip().lower() not in ["não", "nao", "n", "no"]

        anuncio_pendente[interaction.user.id] = {
            "canal_id": self.canal_id,
            "titulo": self.titulo.value,
            "mensagem": self.mensagem.value,
            "mencoes": self.mencoes.value,
            "frase_convocacao": self.frase_convocacao.value.strip() if self.frase_convocacao.value else "",
            "evento": eh_evento,
            "divisores": usar_divisores,
            "guild_id": interaction.guild.id,
        }

        texto = (
            "📎 **Envie os arquivos do anúncio**\n\n"
            "Envie **uma ou mais imagens/arquivos** que vão aparecer no anúncio.\n"
            "Você pode anexar até **10 arquivos** de uma vez (qualquer tipo).\n\n"
            "Ou digite **pular** para enviar sem arquivos.\n"
            "Digite **cancelar** para cancelar o anúncio.\n\n"
            "-# ⏳ Você tem 2 minutos para enviar."
        )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(texto), accent_color=DORORO_COLOR))
        await interaction.response.send_message(view=view, ephemeral=True)

        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=120)

            dados = anuncio_pendente.pop(interaction.user.id, None)
            if not dados:
                return

            if msg.content.strip().lower() == "cancelar":
                await msg.reply("❌ Anúncio cancelado.", delete_after=5)
                try:
                    bot.mensagens_ignorar_delete.add(msg.id)
                    await msg.delete()
                except Exception:
                    pass
                return

            guild = interaction.guild
            canal_destino = guild.get_channel(dados["canal_id"]) or await guild.fetch_channel(dados["canal_id"])
            if not canal_destino:
                await msg.reply("❌ Canal não encontrado!", delete_after=5)
                return

            # Montar layout V2
            itens_anuncio = []
            
            # 1. Imagem principal sera adicionada no inicio depois de baixada
            
            # 2. Conteudo de texto
            texto_principal = f"**{dados['titulo']}**\n\n{dados['mensagem']}"
            itens_anuncio.append(discord.ui.TextDisplay(texto_principal))
            
            # 3. Separador e Footer serao adicionados antes de renderizar

            # Montar menções
            texto_mencao, content_ping = montar_texto_mencao(dados["mencoes"], guild, dados.get("frase_convocacao", ""))

            content = texto_mencao if texto_mencao else None

            tem_everyone = dados["mencoes"] and ("@everyone" in dados["mencoes"] or "@here" in dados["mencoes"])
            allowed = discord.AllowedMentions(
                everyone=tem_everyone,
                users=True,
                roles=True,
            )

            # Coletar todos os arquivos anexados (qualquer tipo, até 10 por vez)
            arquivos = []
            primeira_imagem = None
            msg_atual = msg

            async def coletar_arquivos(msg_ref):
                nonlocal primeira_imagem
                _arquivos = []
                if msg_ref.content.strip().lower() == "pular" or not msg_ref.attachments:
                    return _arquivos
                for att in msg_ref.attachments:
                    # Verificar tamanho antes de baixar
                    if att.size > 9_000_000:
                        await interaction.followup.send(
                            f"⚠️ O arquivo **{att.filename}** é muito grande ({att.size // 1024 // 1024}MB). "
                            "Envie uma versão menor (máx 9MB) ou digite **pular**.",
                            ephemeral=True
                        )
                        return None  # sinaliza que precisa de nova tentativa
                    try:
                        dados_bytes = await att.read()
                        _arquivos.append(discord.File(io.BytesIO(dados_bytes), filename=att.filename))
                        if primeira_imagem is None and att.content_type and att.content_type.startswith("image"):
                            primeira_imagem = att.filename
                    except Exception:
                        await interaction.followup.send(f"⚠️ Erro ao baixar `{att.filename}`. Pulando.", ephemeral=True)
                return _arquivos

            # Tentar coletar — se arquivo grande, pedir nova mensagem
            for _tentativa in range(3):
                resultado = await coletar_arquivos(msg_atual)
                if resultado is None:
                    # Arquivo grande — esperar nova mensagem
                    try:
                        msg_atual = await bot.wait_for("message", check=check, timeout=120)
                        if msg_atual.content.strip().lower() == "cancelar":
                            try:
                                bot.mensagens_ignorar_delete.add(msg_atual.id)
                                await msg_atual.delete()
                            except Exception:
                                pass
                            await interaction.followup.send("❌ Anúncio cancelado.", ephemeral=True)
                            return
                        primeira_imagem = None  # resetar para nova tentativa
                        continue
                    except asyncio.TimeoutError:
                        await interaction.followup.send("⏳ Tempo esgotado.", ephemeral=True)
                        return
                else:
                    arquivos = resultado
                    break

            if primeira_imagem:
                itens_anuncio.insert(0, discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
                itens_anuncio.insert(0, discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://" + primeira_imagem)))
                
            # 3. Separador (sep_anuncio)
            import os
            if dados.get("divisores", True) and os.path.exists("sep_anuncio.png"):
                arquivos.append(discord.File("sep_anuncio.png", filename="sep_anuncio_bot.png"))
                itens_anuncio.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
                itens_anuncio.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio_bot.png")))
                
            # 4. Footer
            itens_anuncio.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            itens_anuncio.append(discord.ui.TextDisplay("-# © Ondrakos · 水の竜"))

            # Dividir em lotes de 10 (limite do Discord)
            def lotes(lista, n=10):
                for i in range(0, len(lista), n):
                    yield lista[i:i+n]

            # Enviar o anúncio
            eh_evento = dados.get("evento", False)
            view_presenca = AnuncioPresencaView() if eh_evento else None
            
            view_final = discord.ui.LayoutView()
            view_final.add_item(discord.ui.Container(*itens_anuncio, accent_color=DORORO_COLOR))
            if view_presenca:
                from discord.ui import ActionRow
                row = ActionRow()
                for item in view_presenca.children:
                    row.add_item(item)
                view_final.add_item(row)

            # ── Canal de Fórum ──────────────────────────────────
            if isinstance(canal_destino, discord.ForumChannel):
                primeiro_arquivo = arquivos[0] if arquivos else discord.utils.MISSING
                resto = arquivos[1:]
                try:
                    thread_with_msg = await canal_destino.create_thread(
                        name=dados["titulo"][:100],
                        content=content or "",
                        view=view_final,
                        file=primeiro_arquivo,
                        allowed_mentions=allowed,
                    )
                except discord.HTTPException as e:
                    if e.code == 40005:
                        await msg.reply(
                            "❌ Arquivo muito grande para o Discord (limite: 10MB). "
                            "Comprima o arquivo ou envie via link externo.",
                            delete_after=15
                        )
                    else:
                        await msg.reply(f"❌ Erro ao criar tópico: {e.text or str(e)}", delete_after=10)
                    return
                for i in range(0, len(resto), 10):
                    lote = resto[i:i+10]
                    try:
                        await thread_with_msg.thread.send(files=lote)
                    except discord.HTTPException as e:
                        if e.code == 40005:
                            await thread_with_msg.thread.send(
                                "⚠️ Arquivo(s) muito grande(s) para o Discord (limite: 10MB). "
                                "Considere comprimir ou enviar via link externo."
                            )
                        else:
                            await thread_with_msg.thread.send(f"⚠️ Erro ao enviar arquivo(s): {e.text or str(e)}")
                msg_anuncio = thread_with_msg.message

            # ── Canal de Texto Normal ───────────────────────────
            else:
                primeiro_lote = arquivos[:10] if arquivos else []
                resto_txt = arquivos[10:]
                
                try:
                    msg_anuncio = await canal_destino.send(
                        content=content,
                        files=primeiro_lote if primeiro_lote else discord.utils.MISSING,
                        view=view_final,
                        allowed_mentions=allowed,
                    )
                except discord.HTTPException as e:
                    if e.code == 40005:
                        msg_anuncio = await canal_destino.send(
                            content=content,
                            view=view_final, allowed_mentions=allowed,
                        )
                        await interaction.followup.send("⚠️ Arquivo(s) muito grande(s). Tente comprimir.", ephemeral=True)
                    else:
                        await msg.reply(f"❌ Erro ao enviar: {e.text or str(e)}", delete_after=10)
                        return
                
                for lote in [resto_txt[i:i+10] for i in range(0, len(resto_txt), 10)]:
                    try:
                        await canal_destino.send(files=lote)
                    except discord.HTTPException:
                        pass

            if eh_evento:
                anuncio_presencas[msg_anuncio.id] = {"confirmados": {}, "ausentes": {}}

            await msg.reply("✅ Anúncio enviado!", delete_after=10)
            try:
                bot.mensagens_ignorar_delete.add(msg.id)
                await msg.delete()
            except Exception:
                pass

        except asyncio.TimeoutError:
            anuncio_pendente.pop(interaction.user.id, None)
            try:
                await interaction.followup.send("⏳ Tempo esgotado. Anúncio cancelado.", ephemeral=True)
            except Exception:
                pass




# ── /postagem — Cria tópico no fórum e posta anúncio ──────

# Guarda dados do /postagem enquanto espera a imagem
postagem_pendente = {}


class PostagemModal(Modal):
    def __init__(self, forum_id: int):
        super().__init__(title="🐉 Nova Postagem — Ondrakos")
        self.forum_id = forum_id
        self.titulo = TextInput(
            label="Título da postagem (nome do tópico)",
            placeholder="Ex: 🐉 Ritual do Clã · Evento Sobrenatural",
            required=True, max_length=100,
        )
        self.mensagem = TextInput(
            label="Conteúdo",
            style=_TextStyle.paragraph,
            placeholder="Texto que vai aparecer na postagem...",
            required=True, max_length=4000,
        )
        self.tags = TextInput(
            label="Tags (nomes separados por vírgula, opcional)",
            placeholder="Ex: ritual, evento, ondrakos",
            required=False, max_length=200,
        )
        self.mencoes = TextInput(
            label="Menções (opcional)",
            placeholder="@Nome, ID ou @Cargo",
            required=False, max_length=500,
        )
        
        self.add_item(self.titulo)
        self.add_item(self.mensagem)
        self.add_item(self.tags)
        self.add_item(self.mencoes)

    async def on_submit(self, interaction: discord.Interaction):
        # Validar ID do fórum
        try:
            forum_id = self.forum_id
        except ValueError:
            await interaction.response.send_message("❌ ID do canal inválido.", ephemeral=True)
            return

        canal_forum = interaction.guild.get_channel(forum_id)
        if not canal_forum:
            try:
                canal_forum = await interaction.guild.fetch_channel(forum_id)
            except Exception:
                canal_forum = None

        if not canal_forum or not isinstance(canal_forum, discord.ForumChannel):
            await interaction.response.send_message(
                "❌ Canal não encontrado ou não é um canal de fórum. "
                "Certifique-se de copiar o ID do **canal de fórum**, não de um tópico.",
                ephemeral=True
            )
            return

        postagem_pendente[interaction.user.id] = {
            "forum_id": forum_id,
            "titulo": self.titulo.value,
            "mensagem": self.mensagem.value,
            "tags_texto": self.tags.value,
            "mencoes": self.mencoes.value,
            "guild_id": interaction.guild.id,
        }

        texto = (
            "📎 **Envie os arquivos da postagem**\n\n"
            "Envie **uma ou mais imagens/arquivos** que vão aparecer na postagem.\n"
            "Você pode anexar até **10 arquivos** de uma vez (qualquer tipo).\n\n"
            "Ou digite **pular** para postar sem arquivos.\n"
            "Digite **cancelar** para cancelar.\n\n"
            "-# ⏳ Você tem 2 minutos para enviar."
        )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(texto), accent_color=DORORO_COLOR))
        await interaction.response.send_message(view=view, ephemeral=True)

        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=120)

            dados = postagem_pendente.pop(interaction.user.id, None)
            if not dados:
                return

            if msg.content.strip().lower() == "cancelar":
                await msg.reply("❌ Postagem cancelada.", delete_after=5)
                try:
                    bot.mensagens_ignorar_delete.add(msg.id)
                    await msg.delete()
                except Exception:
                    pass
                return

            guild = interaction.guild

            # Resolver fórum
            canal_forum = guild.get_channel(dados["forum_id"])
            if not canal_forum:
                try:
                    canal_forum = await guild.fetch_channel(dados["forum_id"])
                except Exception:
                    canal_forum = None

            if not canal_forum:
                await msg.reply("❌ Canal de fórum não encontrado!", delete_after=5)
                return

            # Montar layout V2
            texto_post = f"**{dados['titulo']}**\n\n{dados['mensagem']}\n\n-# © Ondrakos · 水の竜"
            itens_post = [discord.ui.TextDisplay(texto_post)]

            # Menções
            texto_mencao, _ = montar_texto_mencao(dados["mencoes"], guild)
            content = texto_mencao if texto_mencao else None
            tem_everyone = dados["mencoes"] and ("@everyone" in dados["mencoes"] or "@here" in dados["mencoes"])
            allowed = discord.AllowedMentions(everyone=tem_everyone, users=True, roles=True)

            # Coletar todos os arquivos (qualquer tipo, até 10 por vez)
            arquivos = []
            primeira_imagem = None
            if msg.content.strip().lower() != "pular" and msg.attachments:
                for att in msg.attachments:
                    try:
                        dados_bytes = await att.read()
                        arquivos.append(discord.File(io.BytesIO(dados_bytes), filename=att.filename))
                        if primeira_imagem is None and att.content_type and att.content_type.startswith("image"):
                            primeira_imagem = att.filename
                    except Exception:
                        await msg.reply(f"⚠️ Erro ao baixar `{att.filename}`. Pulando este arquivo.", delete_after=5)

            if primeira_imagem:
                itens_post.insert(0, discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://" + primeira_imagem)))

            # Resolver tags do fórum pelo nome
            tags_aplicar = []
            if dados["tags_texto"] and canal_forum.available_tags:
                nomes_tags = [t.strip().lower() for t in dados["tags_texto"].split(",") if t.strip()]
                for tag in canal_forum.available_tags:
                    if tag.name.lower() in nomes_tags:
                        tags_aplicar.append(tag)

            # Se o fórum exige tag mas nenhuma foi encontrada, usa a primeira disponível
            if not tags_aplicar and canal_forum.available_tags:
                req = getattr(canal_forum, 'require_tag', False)
                if req:
                    tags_aplicar.append(canal_forum.available_tags[0])

            # Criar tópico no fórum com primeiro arquivo embutido
            view_post = discord.ui.LayoutView()
            view_post.add_item(discord.ui.Container(*itens_post, accent_color=DORORO_COLOR))

            primeiro_arquivo = arquivos[0] if arquivos else discord.utils.MISSING
            resto = arquivos[1:]
            try:
                thread_with_msg = await canal_forum.create_thread(
                    name=dados["titulo"][:100],
                    content=content or "",
                    view=view_post,
                    file=primeiro_arquivo,
                    applied_tags=tags_aplicar if tags_aplicar else discord.utils.MISSING,
                    allowed_mentions=allowed,
                )
            except discord.HTTPException as e:
                if e.code == 40005:
                    await msg.reply(
                        "❌ Arquivo muito grande para o Discord (limite: 10MB). "
                        "Comprima o arquivo ou envie via link externo.",
                        delete_after=15
                    )
                else:
                    await msg.reply(f"❌ Erro ao criar tópico: {e.text or str(e)}", delete_after=10)
                return

            # Enviar arquivos restantes em lotes de 10
            for i in range(0, len(resto), 10):
                lote = resto[i:i+10]
                try:
                    await thread_with_msg.thread.send(files=lote)
                except discord.HTTPException as e:
                    if e.code == 40005:
                        await thread_with_msg.thread.send(
                            "⚠️ Arquivo(s) muito grande(s) para o Discord (limite: 10MB). "
                            "Considere comprimir ou enviar via link externo."
                        )
                    else:
                        await thread_with_msg.thread.send(f"⚠️ Erro ao enviar arquivo(s): {e.text or str(e)}")

            await msg.reply(
                "✅ Postagem criada! " + thread_with_msg.thread.jump_url,
                delete_after=15
            )
            try:
                bot.mensagens_ignorar_delete.add(msg.id)
                await msg.delete()
            except Exception:
                pass

        except asyncio.TimeoutError:
            postagem_pendente.pop(interaction.user.id, None)
            try:
                await interaction.followup.send("⏳ Tempo esgotado. Postagem cancelada.", ephemeral=True)
            except Exception:
                pass


class PostagemDestinoView(discord.ui.LayoutView):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        categorias = [c for c in interaction.guild.categories if any(isinstance(ch, discord.ForumChannel) for ch in c.channels)]
        categorias = categorias[:25]
        
        if not categorias:
            self.add_item(discord.ui.TextDisplay("Nenhuma categoria com fórum encontrada."))
            return
            
        opcoes = [discord.SelectOption(label=c.name, value=str(c.id)) for c in categorias]
        self.select_cat = discord.ui.Select(placeholder="1. Selecione a Categoria", options=opcoes)
        self.select_cat.callback = self.categoria_selecionada
        
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("🐉 **Nova Postagem › Selecione o Fórum**\nNavegue pelas categorias para encontrar o fórum."),
            discord.ui.ActionRow(self.select_cat),
            accent_color=DORORO_COLOR
        ))

    async def categoria_selecionada(self, interaction: discord.Interaction):
        cat_id = int(self.select_cat.values[0])
        self.select_cat.disabled = True
        for opt in self.select_cat.options:
            if opt.value == str(cat_id): opt.default = True
        categoria = interaction.guild.get_channel(cat_id)
        
        foruns = [c for c in categoria.channels if isinstance(c, discord.ForumChannel)][:25]
        if not foruns:
            await interaction.response.send_message("❌ Nenhum fórum ativo nesta categoria.", ephemeral=True)
            return
            
        opcoes_foruns = [discord.SelectOption(label=f.name, value=str(f.id)) for f in foruns]
        self.select_forum = discord.ui.Select(placeholder="2. Selecione o Fórum", options=opcoes_foruns)
        self.select_forum.callback = self.forum_selecionado
        
        self.clear_items()
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("🐉 **Nova Postagem › Selecione o Fórum**\nCategoria selecionada. Agora escolha o fórum."),
            discord.ui.ActionRow(self.select_cat),
            discord.ui.ActionRow(self.select_forum),
            accent_color=DORORO_COLOR
        ))
        await interaction.response.edit_message(view=self)

    async def forum_selecionado(self, interaction: discord.Interaction):
        forum_id = int(self.select_forum.values[0])
        await interaction.response.send_modal(PostagemModal(forum_id=forum_id))

@bot.tree.command(name="postagem", description="Criar uma postagem num canal de fórum — Ondrakos")
@app_commands.checks.has_permissions(administrator=True)
async def postagem_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(view=PostagemDestinoView(interaction), ephemeral=True)


def _sep_file():
    """Retorna discord.File com o separador se existir na pasta do bot."""
    import os
    sep_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sep_anuncio.png")
    if os.path.exists(sep_path):
        return discord.File(sep_path, filename="sep_anuncio.png")
    return None

async def _ultimo_eh_sep(canal) -> bool:
    """Verifica se a última mensagem do canal já é o separador (evita duplicar).
    Checa as últimas 3 mensagens pra evitar race condition."""
    try:
        msgs = [m async for m in canal.history(limit=3)]
        if msgs:
            m = msgs[0]  # só a mais recente importa
            if m.author.id == bot.user.id and m.attachments and not m.embeds:
                if any("sep_anuncio" in a.filename.lower() for a in m.attachments):
                    return True
    except Exception:
        pass
    return False

class AnuncioDestinoView(discord.ui.LayoutView):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        categorias = [c for c in interaction.guild.categories if len(c.channels) > 0]
        categorias = categorias[:25]
        
        if not categorias:
            self.add_item(discord.ui.TextDisplay("Nenhuma categoria encontrada."))
            return
            
        opcoes = [discord.SelectOption(label=c.name, value=str(c.id)) for c in categorias]
        self.select_cat = discord.ui.Select(placeholder="1. Selecione a Categoria", options=opcoes)
        self.select_cat.callback = self.categoria_selecionada
        
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("🐉 **Novo Anúncio › Selecione o Destino**\nNavegue pelas categorias para encontrar o canal."),
            discord.ui.ActionRow(self.select_cat),
            accent_color=DORORO_COLOR
        ))

    async def categoria_selecionada(self, interaction: discord.Interaction):
        cat_id = int(self.select_cat.values[0])
        self.select_cat.disabled = True
        for opt in self.select_cat.options:
            if opt.value == str(cat_id): opt.default = True
        categoria = interaction.guild.get_channel(cat_id)
        
        # Filtra canais de texto ou fórum
        canais = [c for c in categoria.channels if isinstance(c, (discord.TextChannel, discord.ForumChannel))][:25]
        if not canais:
            await interaction.response.send_message("❌ Nenhum canal de texto ou fórum ativo nesta categoria.", ephemeral=True)
            return
            
        opcoes_canais = [discord.SelectOption(
            label=c.name, 
            value=str(c.id), 
            description="Fórum" if isinstance(c, discord.ForumChannel) else "Canal de Texto"
        ) for c in canais]
        
        self.select_canal = discord.ui.Select(placeholder="2. Selecione o Canal", options=opcoes_canais)
        self.select_canal.callback = self.canal_selecionado
        
        self.clear_items()
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("🐉 **Novo Anúncio › Selecione o Destino**\nCategoria selecionada. Agora escolha o canal."),
            discord.ui.ActionRow(self.select_cat),
            discord.ui.ActionRow(self.select_canal),
            accent_color=DORORO_COLOR
        ))
        await interaction.response.edit_message(view=self)

    async def canal_selecionado(self, interaction: discord.Interaction):
        canal_id = int(self.select_canal.values[0])
        self.select_canal.disabled = True
        for opt in self.select_canal.options:
            if opt.value == str(canal_id): opt.default = True
        canal = interaction.guild.get_channel(canal_id)
        
        if isinstance(canal, discord.ForumChannel):
            topicos = canal.threads[:25]
            if not topicos:
                await interaction.response.send_message("❌ Nenhum tópico ativo neste fórum.", ephemeral=True)
                return
                
            opcoes_topicos = [discord.SelectOption(label=t.name[:100], value=str(t.id)) for t in topicos]
            self.select_topico = discord.ui.Select(placeholder="3. Selecione o Tópico", options=opcoes_topicos)
            self.select_topico.callback = self.topico_selecionado
            
            self.clear_items()
            self.add_item(discord.ui.Container(
                discord.ui.TextDisplay("🐉 **Novo Anúncio › Selecione o Destino**\nFórum selecionado. Agora escolha o tópico."),
                discord.ui.ActionRow(self.select_cat),
                discord.ui.ActionRow(self.select_canal),
                discord.ui.ActionRow(self.select_topico),
                accent_color=DORORO_COLOR
            ))
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_modal(AnuncioModal(canal_id=canal_id))

    async def topico_selecionado(self, interaction: discord.Interaction):
        topico_id = int(self.select_topico.values[0])
        await interaction.response.send_modal(AnuncioModal(canal_id=topico_id))

@bot.tree.command(name="anuncio", description="Criar um anúncio do Ondrakos")
@app_commands.checks.has_permissions(administrator=True)
async def anuncio_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(view=AnuncioDestinoView(interaction), ephemeral=True)


# ── on_ready ───────────────────────────────────────────────
@bot.event
async def on_ready():
    baixar_fonte()
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(
            name="Se os humanos temem minhas chamas, é porque nunca entenderam que até o fogo nasceu para proteger algo."
        ),
    )
    print("Bot online como Ondrakos: " + str(bot.user))

    # Conectar banco de dados
    db = Database()
    await db.connect()
    bot.db = db

    # Registrar views persistentes de anúncios
    bot.add_view(AnuncioPresencaView())

    # Carregar cogs
    import inspect
    for cog in COGS_INICIAIS:
        try:
            result = bot.load_extension(cog)
            if inspect.iscoroutine(result):
                await result
            print(f"OK Cog carregado: {cog}")
        except Exception as e:
            print(f"ERRO ao carregar {cog}: {e}")

    # Sincronizar slash commands
    try:
        await bot.tree.sync()
        print("Commands Sincronizados!")
    except Exception as e:
        print(f"Aviso: nao foi possivel sincronizar commands: {e}")

    # Registrar todos os membros existentes no banco de XP + limpar quem saiu
    for guild in bot.guilds:
        membros_humanos = [m.id for m in guild.members if not m.bot]
        await bot.db.registrar_membros_em_massa(membros_humanos, guild.id)
        removidos = await bot.db.limpar_membros_saiu(membros_humanos, guild.id)
        print(f"✅ {len(membros_humanos)} membros no XP para Ondrakos" +
              (f" ({removidos} removidos)" if removidos else ""))

    # Atualizar contador de membros
    from cogs.boasvindas import BoasVindasCog
    bv_cog = bot.get_cog("BoasVindasCog")
    if bv_cog:
        for guild in bot.guilds:
            await bv_cog.atualizar_contador(guild)
        print("✅ Contador de membros atualizado!")

    # Setup embed fixo dos tickets (V2 LayoutView)
    from cogs.tickets import TicketLayout
    canal_tickets = bot.get_channel(config.TICKET_CANAL_ID())
    if canal_tickets:
        tem_v2 = False
        async for msg in canal_tickets.history(limit=10):
            if msg.author == bot.user:
                try:
                    raw_data = await bot.http.get_message(canal_tickets.id, msg.id)
                    if "ticket_dropdown" in str(raw_data):
                        tem_v2 = True
                        break
                except Exception:
                    pass
        if not tem_v2:
            import os as _os
            _base = _os.path.dirname(_os.path.abspath(__file__))
            _ticket_img = _os.path.join(_base, "tickets.png")
            _sep_img    = _os.path.join(_base, "sep_anuncio.png")
            tem_img = _os.path.exists(_ticket_img) and _os.path.getsize(_ticket_img) < 9_000_000
            tem_sep = _os.path.exists(_sep_img) and _os.path.getsize(_sep_img) < 9_000_000
            view = TicketLayout(tem_img=tem_img, tem_sep=tem_sep)
            arquivos = []
            if tem_sep:
                arquivos.append(discord.File(_sep_img, filename="sep_anuncio.png"))
            if tem_img:
                arquivos.append(discord.File(_ticket_img, filename="tickets.png"))
            if arquivos:
                await canal_tickets.send(files=arquivos, view=view)
            else:
                await canal_tickets.send(view=view)
            print("\u2705 Embed de tickets criado em V2!")
        else:
            print("\u2705 Embed de tickets j\u00e1 existe, mantendo.")

    # Setup embed fixo do cargo de historias
    from cogs.historias import setup_historias_embed
    await setup_historias_embed(bot)
  
    # Setup embed fixo do player de música
    from cogs.musica import setup_player_embed
    await setup_player_embed(bot)

    # Repovoar historico da IA para canais ja existentes
    from cogs.ia_jornalista import _criar_embed_ia, ia_historico, carregar_contexto
    contexto = carregar_contexto()
    IA_CANAIS_IGNORAR = {1507715792198828034}
    for guild in bot.guilds:
        from cogs.ia_jornalista import ia_historico
        categoria_ia = guild.get_channel(config.IA_CATEGORIA_ID())
        if categoria_ia:
            for canal in categoria_ia.channels:
                if canal.id in IA_CANAIS_IGNORAR:
                    continue
                nome = canal.name.lower()
                if not ("ia-" in nome or nome.startswith("🗓")):
                    continue
                if isinstance(canal, discord.TextChannel) and canal.id not in ia_historico:
                    ia_historico[canal.id] = [
                        {"role": "user",  "parts": [{"text": contexto}]},
                        {"role": "model", "parts": [{"text": "Entendido! Estou pronto para ajudar os membros do Ondrakos. Pode começar!"}]},
                    ]
    print("IA: historico repovoado para " + str(len(ia_historico)) + " canais.")
    # Setup embed de signos
    from cogs.signos import setup_signos_embed
    await setup_signos_embed(bot)

    # Setup embed da IA
    from cogs.ia_jornalista import _criar_embed_ia
    for guild in bot.guilds:
        canal_ia = guild.get_channel(config.IA_CANAL_ID())
        if not canal_ia:
            continue
        tem_embed_ia = False
        try:
            async for msg in canal_ia.history(limit=10):
                if msg.author == bot.user:
                    tem_embed_ia = True
                    break
        except Exception as e:
            print(f"[Aviso] Erro ao buscar historico do canal IA: {e}")
            tem_embed_ia = True # Assume que existe para nao duplicar
            
        if not tem_embed_ia:
            try:
                await _criar_embed_ia(canal_ia)
                print("✅ Painel de IA criado (V2)!")
            except Exception as e:
                print(f"[Erro] Falha ao criar painel IA: {e}")
        else:
            print("✅ Painel de IA ja existe em V2, mantendo.")

    # Setup embed do site (primeiro no canal de divulgação)
    await setup_site_embed(bot)
  
    # Setup embed de verificação — delega para o cog
    from cogs.verificacao import setup_verificacao_embed
    await setup_verificacao_embed(bot)
    
    # Setup embed de regras
    await setup_regras_embed(bot)


class EditarMensagemModal(Modal):
    def __init__(self, canal_id: int, msg_id: int):
        super().__init__(title="Editar Mensagem do Bot")
        self.canal_id = canal_id
        self.msg_id = msg_id
        self.titulo_field = TextInput(
            label="Titulo (deixe vazio para manter)",
            required=False,
            max_length=256,
        )
        self.descricao_field = TextInput(
            label="Descricao / Conteudo",
            style=_TextStyle.paragraph,
            required=False,
            max_length=4000,
        )
        self.footer_field = TextInput(
            label="Footer (deixe vazio para manter)",
            required=False,
            max_length=2048,
        )
        self.add_item(self.titulo_field)
        self.add_item(self.descricao_field)
        self.add_item(self.footer_field)

    async def on_submit(self, interaction: discord.Interaction):
        editar_pendente[interaction.user.id] = {
            "canal_id": self.canal_id,
            "msg_id": self.msg_id,
            "titulo": self.titulo_field.value,
            "descricao": self.descricao_field.value,
            "footer": self.footer_field.value,
        }

        texto = (
            "🖼️ **Imagem da mensagem**\n\n"
            "Envie uma **nova imagem** para substituir.\n"
            "Digite **pular** para manter a imagem atual.\n"
            "Digite **remover** para tirar a imagem.\n"
            "Digite **cancelar** para cancelar.\n\n"
            "-# ⏳ Você tem 2 minutos para responder."
        )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(texto), accent_color=DORORO_COLOR))
        await interaction.response.send_message(view=view, ephemeral=True)

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot.wait_for("message", check=check, timeout=120)

            dados = editar_pendente.pop(interaction.user.id, None)
            if not dados:
                return

            if msg.content.strip().lower() == "cancelar":
                try:
                    bot.mensagens_ignorar_delete.add(msg.id)
                    await msg.delete()
                except Exception:
                    pass
                await interaction.followup.send("Cancelado.", ephemeral=True)
                return

            # Buscar canal/thread (threads de fórum não aparecem em get_channel)
            canal = interaction.guild.get_channel(dados["canal_id"])
            if not canal:
                try:
                    canal = await interaction.guild.fetch_channel(dados["canal_id"])
                except Exception:
                    canal = None
            if not canal:
                await interaction.followup.send("Canal nao encontrado.", ephemeral=True)
                return
            try:
                target_msg = await canal.fetch_message(dados["msg_id"])
            except Exception:
                await interaction.followup.send("Mensagem nao encontrada.", ephemeral=True)
                return

            # Montar novo embed ou texto
            if target_msg.embeds:
                novo_embed = target_msg.embeds[0].copy()
                if dados["titulo"].strip():
                    novo_embed.title = dados["titulo"].strip()
                if dados["descricao"].strip():
                    novo_embed.description = dados["descricao"].strip()
                if dados["footer"].strip():
                    novo_embed.set_footer(text=dados["footer"].strip())
            else:
                novo_embed = None

            # Processar imagem
            nova_imagem = None
            opcao_img = msg.content.strip().lower()

            if opcao_img == "remover":
                if novo_embed:
                    novo_embed.set_image(url=None)
            elif opcao_img == "pular":
                # Se a imagem já está no embed como URL, não precisa reenviar como arquivo
                # Se estava como attachment, tenta manter via URL do CDN
                if novo_embed and novo_embed.image and novo_embed.image.url:
                    # Imagem já está no embed como URL — não precisa fazer nada
                    pass
                elif novo_embed and target_msg.attachments:
                    # Era attachment solto — manter a URL do CDN enquanto ainda válida
                    att_url = target_msg.attachments[0].url
                    novo_embed.set_image(url=att_url)
            elif msg.attachments:
                att = msg.attachments[0]
                try:
                    dados_bytes = await asyncio.wait_for(att.read(), timeout=30.0)
                    nova_imagem = discord.File(io.BytesIO(dados_bytes), filename=att.filename)
                    if novo_embed:
                        novo_embed.set_image(url="attachment://" + att.filename)
                except Exception as e:
                    await msg.reply("Erro ao baixar imagem: " + str(e), delete_after=5)

            try:
                bot.mensagens_ignorar_delete.add(msg.id)
                await msg.delete()
            except Exception:
                pass

            # Salvar
            for _tentativa_edit in range(3):
                try:
                    if novo_embed:
                        if nova_imagem:
                            await target_msg.edit(embed=novo_embed, attachments=[nova_imagem])
                        else:
                            await target_msg.edit(embed=novo_embed)
                    else:
                        await target_msg.edit(content=dados["descricao"].strip())
                    await interaction.followup.send("Mensagem editada com sucesso!", ephemeral=True)
                    break
                except discord.HTTPException as e:
                    if e.code == 40005 and _tentativa_edit < 2:
                        await interaction.followup.send(
                            "⚠️ Arquivo muito grande. Envie uma imagem menor ou digite **pular**.",
                            ephemeral=True
                        )
                        try:
                            msg2 = await bot.wait_for("message",
                                check=lambda m: m.author.id == interaction.user.id and m.channel.id == interaction.channel.id,
                                timeout=120)
                            if msg2.content.strip().lower() in ["pular", "cancelar"]:
                                nova_imagem = None
                                if novo_embed:
                                    novo_embed.set_image(url=None)
                                await msg2.delete()
                                continue
                            if msg2.attachments:
                                att2 = msg2.attachments[0]
                                dados2 = await asyncio.wait_for(att2.read(), timeout=30.0)
                                nova_imagem = discord.File(io.BytesIO(dados2), filename=att2.filename)
                                if novo_embed:
                                    novo_embed.set_image(url="attachment://" + att2.filename)
                            await msg2.delete()
                        except Exception:
                            break
                    else:
                        await interaction.followup.send("Erro ao editar: " + str(e), ephemeral=True)
                        break

        except asyncio.TimeoutError:
            editar_pendente.pop(interaction.user.id, None)
            await interaction.followup.send("Tempo esgotado.", ephemeral=True)


@bot.tree.command(name="editar", description="Editar uma mensagem que o bot ja enviou")
@app_commands.checks.has_permissions(administrator=True)
async def editar_cmd(interaction: discord.Interaction, id: str):
    try:
        msg_id = int(id.strip())
    except ValueError:
        await interaction.response.send_message("ID invalido. Use apenas numeros.", ephemeral=True)
        return

    # Tentar buscar no canal atual primeiro — sem defer pra poder abrir modal
    target_msg = None
    try:
        target_msg = await interaction.channel.fetch_message(msg_id)
    except Exception:
        pass

    if not target_msg:
        # Nao achou no canal atual — defer e busca nos outros
        await interaction.response.defer(ephemeral=True, thinking=True)
        for channel in interaction.guild.text_channels:
            try:
                target_msg = await channel.fetch_message(msg_id)
                break
            except Exception:
                continue
        if not target_msg:
            await interaction.followup.send("Mensagem nao encontrada.", ephemeral=True)
            return
        if target_msg.author.id != bot.user.id:
            await interaction.followup.send("Essa mensagem nao foi enviada pelo bot.", ephemeral=True)
            return
        # Apos defer nao da pra abrir modal — orienta o usuario
        await interaction.followup.send(
            "Mensagem encontrada em " + target_msg.channel.mention +
            ". Va ate esse canal e use /editar " + id + " de la para abrir o editor.",
            ephemeral=True
        )
        return

    if target_msg.author.id != bot.user.id:
        await interaction.response.send_message("Essa mensagem nao foi enviada pelo bot.", ephemeral=True)
        return

    # Encontrou no canal atual — abrir modal direto via response
    embed = target_msg.embeds[0] if target_msg.embeds else None
    modal = EditarMensagemModal(canal_id=target_msg.channel.id, msg_id=target_msg.id)
    if embed:
        modal.titulo_field.default = embed.title or ""
        modal.descricao_field.default = embed.description or ""
        modal.footer_field.default = embed.footer.text if embed.footer else ""
    else:
        modal.descricao_field.default = target_msg.content or ""

    await interaction.response.send_modal(modal)


class RemandarMensagemModal(Modal):
    def __init__(self, canal_id: int, msg_id: int):
        super().__init__(title="Remandar Mensagem")
        self.canal_id = canal_id
        self.msg_id   = msg_id
        self.titulo_field = TextInput(
            label="Titulo (deixe vazio para manter)",
            required=False, max_length=256,
        )
        self.descricao_field = TextInput(
            label="Descricao / Conteudo",
            style=_TextStyle.paragraph,
            required=False, max_length=4000,
        )
        self.footer_field = TextInput(
            label="Footer (deixe vazio para manter)",
            required=False, max_length=2048,
        )
        self.add_item(self.titulo_field)
        self.add_item(self.descricao_field)
        self.add_item(self.footer_field)

    async def on_submit(self, interaction: discord.Interaction):
        remandar_pendente[interaction.user.id] = {
            "canal_id": self.canal_id,
            "msg_id":   self.msg_id,
            "titulo":   self.titulo_field.value,
            "descricao":self.descricao_field.value,
            "footer":   self.footer_field.value,
        }

        texto = (
            "🖼️ **Imagem da mensagem**\n\n"
            "Envie uma **nova imagem** para substituir.\n"
            "Digite **pular** para manter a imagem atual.\n"
            "Digite **remover** para tirar a imagem.\n"
            "Digite **cancelar** para cancelar.\n\n"
            "-# ⏳ Você tem 2 minutos para responder."
        )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(texto), accent_color=DORORO_COLOR))
        await interaction.response.send_message(view=view, ephemeral=True)

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            remandar_pendente.pop(interaction.user.id, None)
            await interaction.followup.send("Tempo esgotado.", ephemeral=True)
            return

        dados = remandar_pendente.pop(interaction.user.id, None)
        if not dados:
            return

        if msg.content.strip().lower() == "cancelar":
            try:
                bot.mensagens_ignorar_delete.add(msg.id)
                await msg.delete()
            except Exception:
                pass
            await interaction.followup.send("Cancelado.", ephemeral=True)
            return

        # Buscar mensagem original
        canal = interaction.guild.get_channel(dados["canal_id"])
        if not canal:
            await interaction.followup.send("Canal nao encontrado.", ephemeral=True)
            return
        try:
            target_msg = await canal.fetch_message(dados["msg_id"])
        except Exception:
            await interaction.followup.send("Mensagem nao encontrada.", ephemeral=True)
            return

        # Montar texto V2
        texto_v2 = target_msg.content or ""
        url_img_v2 = None
        
        titulo_final = dados["titulo"].strip()
        desc_final = dados["descricao"].strip()
        footer_final = dados["footer"].strip()

        if target_msg.embeds:
            emb = target_msg.embeds[0]
            if not titulo_final and emb.title:
                titulo_final = emb.title
            if not desc_final and emb.description:
                desc_final = emb.description
            if not footer_final and emb.footer and emb.footer.text:
                footer_final = emb.footer.text
            if emb.image and emb.image.url:
                url_img_v2 = emb.image.url

        if titulo_final:
            texto_v2 += f"**{titulo_final}**\n\n"
        if desc_final:
            texto_v2 += f"{desc_final}\n\n"
            
        if target_msg.embeds:
            for field in target_msg.embeds[0].fields:
                texto_v2 += f"**{field.name}**\n{field.value}\n\n"
                
        if footer_final:
            texto_v2 += f"-# {footer_final}"
            
        texto_v2 = texto_v2.strip()

        # Processar imagem
        nova_imagem = None
        nome_img = None
        opcao_img = msg.content.strip().lower()
        
        import io
        import aiohttp
        import os
        import urllib.parse
        async def fetch_bytes(url):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
            return None

        if opcao_img == "remover":
            url_img_v2 = None
        elif opcao_img == "pular":
            att_img_valido = None
            if target_msg.attachments:
                for a in target_msg.attachments:
                    if not "sep_anuncio" in a.filename.lower() and not "sep_antes" in a.filename.lower() and not "sep_depois" in a.filename.lower():
                        att_img_valido = a
                        break
            
            if att_img_valido:
                try:
                    dados_orig = await asyncio.wait_for(att_img_valido.read(), timeout=30.0)
                    nova_imagem = discord.File(io.BytesIO(dados_orig), filename=att_img_valido.filename)
                    nome_img = att_img_valido.filename
                except Exception:
                    pass
            elif url_img_v2:
                img_bytes = await fetch_bytes(url_img_v2)
                if img_bytes:
                    url_path = urllib.parse.urlparse(url_img_v2).path
                    ext = os.path.splitext(url_path)[1]
                    if not ext: ext = ".png"
                    nome_img = f"img_v2{ext}"
                    nova_imagem = discord.File(io.BytesIO(img_bytes), filename=nome_img)
        elif msg.attachments:
            att = msg.attachments[0]
            try:
                dados_bytes = await asyncio.wait_for(att.read(), timeout=30.0)
                nova_imagem = discord.File(io.BytesIO(dados_bytes), filename=att.filename)
                nome_img = att.filename
            except Exception as e:
                await interaction.followup.send("Erro ao baixar imagem: " + str(e), ephemeral=True)

        try:
            bot.mensagens_ignorar_delete.add(msg.id)
            await msg.delete()
        except Exception:
            pass

        # Detectar qual view recriar baseado nos custom_ids dos botoes da mensagem original
        view_recriar = None
        if target_msg.components:
            ids = []
            for row in target_msg.components:
                for comp in (row.children if hasattr(row, 'children') else [row]):
                    if hasattr(comp, 'custom_id') and comp.custom_id:
                        ids.append(comp.custom_id)
                    elif hasattr(comp, 'url') and comp.url:
                        ids.append('link_button')

            if any('musica' in i for i in ids):
                from cogs.musica import PlayerViewSemMusica
                view_recriar = PlayerViewSemMusica()
            elif any('ticket' in i for i in ids):
                from cogs.tickets import TicketView
                view_recriar = TicketView()
            elif any('ia_pedir' in i for i in ids):
                from cogs.ia_jornalista import IAPainelLayout
                view_recriar = IAPainelLayout(tem_img=False)
            elif any('ia_fechar' in i for i in ids):
                from cogs.ia_jornalista import IABoasVindasLayout
                view_recriar = IABoasVindasLayout("Usuário", "", tem_img=False)
            elif any('link_button' in i for i in ids):
                # Recriar botoes de link (ex: /site)
                view_recriar = View()
                for row in target_msg.components:
                    for comp in (row.children if hasattr(row, 'children') else [row]):
                        if hasattr(comp, 'url') and comp.url:
                            view_recriar.add_item(Button(
                                label=comp.label or "Link",
                                url=comp.url,
                                style=discord.ButtonStyle.link,
                                emoji=comp.emoji,
                            ))
            elif any('anuncio' in i for i in ids):
                from __main__ import AnuncioPresencaView
                view_recriar = AnuncioPresencaView()

        # Verificar se é um anuncio com separadores
        sep_antes_msg = None
        sep_depois_msg = None
        try:
            msgs_antes = [m async for m in canal.history(limit=3, before=target_msg)]
            for m in msgs_antes:
                if m.author.id == bot.user.id and m.attachments and not m.embeds:
                    if any("sep" in a.filename.lower() for a in m.attachments):
                        sep_antes_msg = m
                        break
            msgs_depois = [m async for m in canal.history(limit=3, after=target_msg)]
            for m in msgs_depois:
                if m.author.id == bot.user.id and m.attachments and not m.embeds:
                    if any("sep" in a.filename.lower() for a in m.attachments):
                        sep_depois_msg = m
                        break
        except Exception:
            pass

        itens_v2 = []
        arquivos_enviar = []
        import os
        
        if sep_antes_msg and os.path.exists("sep_anuncio.png"):
            arquivos_enviar.append(discord.File("sep_anuncio.png", filename="sep_antes.png"))
            itens_v2.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_antes.png")))
            itens_v2.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        if nova_imagem and nome_img:
            arquivos_enviar.append(nova_imagem)
            itens_v2.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://" + nome_img)))
            itens_v2.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        if texto_v2:
            itens_v2.append(discord.ui.TextDisplay(texto_v2))
            
        if sep_depois_msg and os.path.exists("sep_anuncio.png"):
            itens_v2.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            arquivos_enviar.append(discord.File("sep_anuncio.png", filename="sep_depois.png"))
            itens_v2.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_depois.png")))

        view_final = discord.ui.LayoutView()
        
        if view_recriar:
            if isinstance(view_recriar, discord.ui.LayoutView):
                for child in view_recriar.children:
                    itens_v2.append(child)
            else:
                for child in view_recriar.children:
                    if isinstance(child, discord.ui.Button):
                        itens_v2.append(discord.ui.ActionRow(child))

        if itens_v2:
            view_final.add_item(discord.ui.Container(*itens_v2, accent_color=DORORO_COLOR))

        try:
            kwargs = {'content': ''}
            if arquivos_enviar:
                kwargs['files'] = arquivos_enviar
            if itens_v2 or view_recriar:
                kwargs['view'] = view_final

            nova_msg = await canal.send(**kwargs)

            # --- Confirmação ---
            class ConfirmacaoRemandarView(discord.ui.View):
                def __init__(self, inter_original, msg_nova, msg_antigas):
                    super().__init__(timeout=120)
                    self.inter_original = inter_original
                    self.msg_nova = msg_nova
                    self.msg_antigas = msg_antigas

                @discord.ui.button(label="Confirmar e Apagar Antiga", style=discord.ButtonStyle.success, emoji="✅")
                async def confirmar(self, inter: discord.Interaction):
                    for m in self.msg_antigas:
                        if m:
                            try:
                                bot.mensagens_ignorar_delete.add(m.id)
                                await m.delete()
                            except Exception:
                                pass
                    for child in self.children: child.disabled = True
                    await inter.response.edit_message(content="✅ **Nova postagem confirmada e postagem antiga apagada!**", view=self)

                @discord.ui.button(label="Cancelar e Apagar Nova", style=discord.ButtonStyle.danger, emoji="🗑️")
                async def cancelar(self, inter: discord.Interaction):
                    try:
                        bot.mensagens_ignorar_delete.add(self.msg_nova.id)
                        await self.msg_nova.delete()
                    except Exception:
                        pass
                    for child in self.children: child.disabled = True
                    await inter.response.edit_message(content="❌ **Operação cancelada! A nova mensagem foi apagada e a antiga mantida.**", view=self)

            msgs_para_apagar = [sep_antes_msg, target_msg, sep_depois_msg]
            view_confirma = ConfirmacaoRemandarView(interaction, nova_msg, msgs_para_apagar)
            await interaction.followup.send("👁️ **Nova mensagem enviada no canal!** Verifique se ficou boa. Confirma a substituição?", view=view_confirma, ephemeral=True)

        except discord.HTTPException as e:
            await interaction.followup.send("Erro ao remandar: " + str(e), ephemeral=True)


@bot.tree.command(name="remandar", description="Reenviar uma mensagem do bot com edicoes (apaga a original)")
@app_commands.checks.has_permissions(administrator=True)
async def remandar_cmd(interaction: discord.Interaction, id: str):
    try:
        msg_id = int(id.strip())
    except ValueError:
        await interaction.response.send_message("ID invalido. Use apenas numeros.", ephemeral=True)
        return

    # Buscar no canal atual primeiro
    target_msg = None
    try:
        target_msg = await interaction.channel.fetch_message(msg_id)
    except Exception:
        pass

    if not target_msg:
        await interaction.response.defer(ephemeral=True, thinking=True)
        for channel in interaction.guild.text_channels:
            try:
                target_msg = await channel.fetch_message(msg_id)
                break
            except Exception:
                continue
        if not target_msg:
            await interaction.followup.send("Mensagem nao encontrada.", ephemeral=True)
            return
        if target_msg.author.id != bot.user.id:
            await interaction.followup.send("Essa mensagem nao foi enviada pelo bot.", ephemeral=True)
            return
        await interaction.followup.send(
            "Mensagem encontrada em " + target_msg.channel.mention +
            ". Use o comando nesse canal para abrir o editor.",
            ephemeral=True
        )
        return

    if target_msg.author.id != bot.user.id:
        await interaction.response.send_message("Essa mensagem nao foi enviada pelo bot.", ephemeral=True)
        return

    embed = target_msg.embeds[0] if target_msg.embeds else None
    modal = RemandarMensagemModal(canal_id=target_msg.channel.id, msg_id=target_msg.id)
    
    # Extrair texto (suporta V1 embeds e V2 LayoutView)
    v2_text = ""
    try:
        raw_data = await bot.http.get_message(target_msg.channel.id, target_msg.id)
        
        def extrair_v2(obj):
            t = ""
            if isinstance(obj, dict):
                # O TextDisplay V2 usa type 14 ou similar, e guarda em 'text'
                if 'text' in obj and isinstance(obj['text'], str) and obj.get('type') not in [2, 3]: # ignora botoes/selects
                    t += obj['text'] + "\n"
                for k, v in obj.items():
                    t += extrair_v2(v)
            elif isinstance(obj, list):
                for i in obj:
                    t += extrair_v2(i)
            return t
        
        v2_text = extrair_v2(raw_data.get('components', [])).strip()
    except Exception:
        pass

    if embed:
        modal.titulo_field.default    = embed.title or ""
        modal.descricao_field.default = embed.description or ""
        modal.footer_field.default    = embed.footer.text if embed.footer else ""
    elif v2_text:
        titulo = ""
        footer = ""
        linhas = [L.strip() for L in v2_text.split('\n') if L.strip()]
        
        if linhas and linhas[0].startswith("**") and linhas[0].endswith("**"):
            titulo = linhas[0].strip("*")
            linhas = linhas[1:]
        elif linhas and linhas[0].startswith("**"):
            titulo = linhas[0].replace("**", "")
            linhas = linhas[1:]
            
        if linhas and linhas[-1].startswith("-# "):
            footer = linhas[-1].replace("-# ", "").strip()
            linhas = linhas[:-1]
            
        modal.titulo_field.default = titulo[:256]
        modal.descricao_field.default = "\n".join(linhas)[:4000]
        modal.footer_field.default = footer[:2048]
    else:
        modal.descricao_field.default = target_msg.content or ""

    await interaction.response.send_modal(modal)


@bot.tree.command(name="arquivo", description="Enviar um arquivo no chat como o bot")
@app_commands.checks.has_permissions(administrator=True)
async def arquivo_cmd(interaction: discord.Interaction):
    # Avisa em ephemeral e manda instrucao no canal pra receber o arquivo
    await interaction.response.send_message(
        "Envie o arquivo neste canal. Sua mensagem sera deletada automaticamente.",
        ephemeral=True
    )

    def check(m):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

    try:
        msg = await bot.wait_for("message", check=check, timeout=120)
    except asyncio.TimeoutError:
        await interaction.followup.send("Tempo esgotado.", ephemeral=True)
        return

    if msg.content.strip().lower() == "cancelar":
        await msg.delete()
        await interaction.followup.send("Cancelado.", ephemeral=True)
        return

    if not msg.attachments:
        await msg.delete()
        await interaction.followup.send("Nenhum arquivo enviado.", ephemeral=True)
        return

    # Baixar ANTES de deletar a mensagem (URL expira após delete)
    arquivos = []
    for att in msg.attachments:
        try:
            dados = await asyncio.wait_for(att.read(), timeout=60.0)
            arquivos.append(discord.File(io.BytesIO(dados), filename=att.filename))
        except asyncio.TimeoutError:
            await interaction.followup.send(f"Tempo esgotado ao baixar {att.filename}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Erro ao baixar {att.filename}: {str(e)}", ephemeral=True)

    # Deletar mensagem do usuario depois de baixar
    try:
        await msg.delete()
    except Exception:
        pass

    if not arquivos:
        await interaction.followup.send("Nenhum arquivo valido.", ephemeral=True)
        return

    # Enviar em lotes de 10
    try:
        for i in range(0, len(arquivos), 10):
            await interaction.channel.send(files=arquivos[i:i+10])
        await interaction.followup.send("Arquivo(s) enviado(s)!", ephemeral=True)
    except discord.HTTPException as e:
        if e.code == 40005:
            await interaction.followup.send(
                "Arquivo muito grande (limite: 10MB). Comprima ou envie via link.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(f"Erro: {e.text or str(e)}", ephemeral=True)



# ── Comandos de teste ─────────────────────────────────────
@bot.tree.command(name="testar-entrada", description="Simula a mensagem de entrada de membro em V2")
@app_commands.checks.has_permissions(administrator=True)
async def testar_entrada(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    member = interaction.user
    try:
        from utils import gerar_imagem_boas_vindas
        from cogs.boasvindas import EntradaLayout
        avatar_bytes = await member.display_avatar.read()
        buf = gerar_imagem_boas_vindas(member.display_name, avatar_bytes, entrou=True)
        arquivo = discord.File(buf, filename="boasvindas.png")
        await interaction.channel.send(file=arquivo, view=EntradaLayout(member))
        await interaction.followup.send("✅ Preview de entrada enviado!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ Erro: " + str(e), ephemeral=True)


@bot.tree.command(name="testar-saida", description="Simula a mensagem de saída de membro em V2")
@app_commands.checks.has_permissions(administrator=True)
async def testar_saida(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    member = interaction.user
    try:
        from utils import gerar_imagem_boas_vindas
        from cogs.boasvindas import SaidaLayout
        avatar_bytes = await member.display_avatar.read()
        buf = gerar_imagem_boas_vindas(member.display_name, avatar_bytes, entrou=False)
        arquivo = discord.File(buf, filename="saida.png")
        await interaction.channel.send(file=arquivo, view=SaidaLayout(member))
        await interaction.followup.send("✅ Preview de saída enviado!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ Erro: " + str(e), ephemeral=True)


# ── /som — Tocar um áudio da pasta /audio/ ────────────────
class SomSelectView(View):
    def __init__(self, arquivos: list, canal_voz):
        super().__init__(timeout=60)
        self.canal_voz = canal_voz
        opcoes = [
            discord.SelectOption(label=f, value=f)
            for f in arquivos[:25]  # Discord limita 25 opções
        ]
        select = Select(placeholder="Escolha um áudio...", options=opcoes)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        arquivo = interaction.data["values"][0]
        audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio", arquivo)
        if not os.path.exists(audio_path):
            await interaction.response.send_message("❌ Arquivo não encontrado.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        vc = guild.voice_client
        conectou = False
        try:
            bot.ignorar_log_voz.add(guild.id)
            if vc is None:
                vc = await asyncio.wait_for(self.canal_voz.connect(), timeout=15.0)
                conectou = True
            elif vc.channel != self.canal_voz:
                await vc.move_to(self.canal_voz)
            if vc.is_playing():
                vc.stop()
            source = discord.FFmpegPCMAudio(audio_path)
            vc.play(source)
            await interaction.followup.send("🔊 Tocando **" + arquivo + "**!", ephemeral=True)
            while vc.is_playing():
                await asyncio.sleep(0.3)
            if conectou:
                await vc.disconnect()
            await asyncio.sleep(1.5)  # Aguardar evento de voz ser processado
        except Exception as e:
            await interaction.followup.send("❌ Erro: " + str(e), ephemeral=True)
            if conectou and guild.voice_client:
                await guild.voice_client.disconnect()
            await asyncio.sleep(1.5)
        finally:
            bot.ignorar_log_voz.discard(guild.id)

@bot.tree.command(name="som", description="Tocar um áudio do bot no canal de voz")
@app_commands.checks.has_permissions(administrator=True)
async def som_cmd(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ Você precisa estar em um canal de voz.", ephemeral=True)
        return
    # Bloquear se o bot estiver tocando música
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message("❌ O bot está tocando música no momento. Pare a música antes de usar este comando.", ephemeral=True)
        return
    audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
    if not os.path.exists(audio_dir):
        await interaction.response.send_message("❌ Pasta `/audio` não encontrada.", ephemeral=True)
        return
    arquivos = sorted([f for f in os.listdir(audio_dir) if f.endswith(".mp3")])
    if not arquivos:
        await interaction.response.send_message("❌ Nenhum arquivo MP3 na pasta `/audio`.", ephemeral=True)
        return
    view = SomSelectView(arquivos, interaction.user.voice.channel)
    embed = discord.Embed(
        title="🔊 Selecionar Áudio",
        description="**" + str(len(arquivos)) + "** arquivo(s) disponível(eis). Escolha o que deseja tocar:",
        color=DORORO_COLOR,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ── Iniciar o Bot ──────────────────────────────────────────


@bot.tree.command(name="repostar-topico", description="[Admin] Clona o tópico atual para V2")
@app_commands.checks.has_permissions(administrator=True)
async def repostar_topico(interaction: discord.Interaction):
    canal = interaction.channel
    if not isinstance(canal, discord.Thread) or not isinstance(canal.parent, discord.ForumChannel):
        await interaction.response.send_message("❌ Este comando só pode ser usado dentro de um tópico de fórum.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        mensagens = [m async for m in canal.history(limit=50, oldest_first=True)]
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao ler mensagens: {e}")
        return

    if not mensagens:
        await interaction.followup.send("❌ Tópico vazio.")
        return

    import io
    import aiohttp
    import os

    async def fetch_bytes(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
        return None

    mensagens_processadas = []

    for m in mensagens:
        if m.author.id == interaction.user.id and m.content.startswith("/repostar-topico"):
            continue 

        eh_separador = False
        if not m.content and not m.embeds and len(m.attachments) == 1:
            att = m.attachments[0]
            if att.content_type and att.content_type.startswith("image"):
                eh_separador = True

        # Ignora separadores antigos (eles serao recriados automaticamente)
        if not eh_separador:
            mensagens_processadas.append(m)

    if not mensagens_processadas:
        await interaction.followup.send("❌ Não encontrei nenhuma mensagem útil para clonar.")
        return

    # Processar a primeira mensagem (que vai criar o tópico)
    m1 = mensagens_processadas[0]
    
    texto_final = m1.content or ""
    url_img_1 = None
    if m1.embeds:
        emb = m1.embeds[0]
        if emb.title:
            texto_final += f"**{emb.title}**\n\n"
        if emb.description:
            texto_final += f"{emb.description}\n\n"
        for field in emb.fields:
            texto_final += f"**{field.name}**\n{field.value}\n\n"
        if emb.footer and emb.footer.text:
            texto_final += f"-# {emb.footer.text}"
        if emb.image and emb.image.url:
            url_img_1 = emb.image.url

    itens = []
    if texto_final.strip():
        itens.append(discord.ui.TextDisplay(texto_final))

    arquivos = []
    primeira_imagem = None
    
    for att in m1.attachments:
        try:
            dados = await att.read()
            arquivos.append(discord.File(io.BytesIO(dados), filename=att.filename))
            if primeira_imagem is None and att.content_type and att.content_type.startswith("image"):
                primeira_imagem = att.filename
        except:
            pass

    if not primeira_imagem and url_img_1:
        img_bytes = await fetch_bytes(url_img_1)
        if img_bytes:
            import urllib.parse
            url_path = urllib.parse.urlparse(url_img_1).path
            ext = os.path.splitext(url_path)[1]
            if not ext:
                ext = ".png"
            nome_arq = f"img_embed{ext}"
            arquivos.insert(0, discord.File(io.BytesIO(img_bytes), filename=nome_arq))
            primeira_imagem = nome_arq

    if primeira_imagem:
        itens.insert(0, discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://" + primeira_imagem)))

    view_post = discord.ui.LayoutView()
    if itens:
        view_post.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))

    primeiro_arquivo = arquivos[0] if arquivos else discord.utils.MISSING
    resto_arquivos = arquivos[1:]

    forum = canal.parent
    try:
        novo_topico = await forum.create_thread(
            name=canal.name,
            content="",
            view=view_post if itens else discord.utils.MISSING,
            file=primeiro_arquivo,
            applied_tags=canal.applied_tags
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao criar novo tópico: {e}")
        return

    if resto_arquivos:
        for i in range(0, len(resto_arquivos), 10):
            try:
                await novo_topico.thread.send(files=resto_arquivos[i:i+10])
            except:
                pass

    # Processar o resto das mensagens
    for m in mensagens_processadas[1:]:
        texto_m = m.content or ""
        url_img_m = None
        if m.embeds:
            emb = m.embeds[0]
            if emb.title:
                texto_m += f"**{emb.title}**\n\n"
            if emb.description:
                texto_m += f"{emb.description}\n\n"
            for field in emb.fields:
                texto_m += f"**{field.name}**\n{field.value}\n\n"
            if emb.footer and emb.footer.text:
                texto_m += f"-# {emb.footer.text}"
            if emb.image and emb.image.url:
                url_img_m = emb.image.url

        itens_m = []
        if texto_m.strip():
            itens_m.append(discord.ui.TextDisplay(texto_m))
            
        arquivos_m = []
        primeira_img_m = None
        for att in m.attachments:
            try:
                dados = await att.read()
                arquivos_m.append(discord.File(io.BytesIO(dados), filename=att.filename))
                if primeira_img_m is None and att.content_type and att.content_type.startswith("image"):
                    primeira_img_m = att.filename
            except:
                pass

        if not primeira_img_m and url_img_m:
            img_bytes = await fetch_bytes(url_img_m)
            if img_bytes:
                import urllib.parse
                url_path = urllib.parse.urlparse(url_img_m).path
                ext = os.path.splitext(url_path)[1]
                if not ext:
                    ext = ".png"
                nome_arq = f"img_embed{ext}"
                arquivos_m.insert(0, discord.File(io.BytesIO(img_bytes), filename=nome_arq))
                primeira_img_m = nome_arq

        # Reordenando a montagem do itens_m
        novos_itens = []
        
        # 1. Separador no topo (em sua própria MediaGallery isolada)
        if os.path.exists("sep_anuncio.png"):
            arquivos_m.insert(0, discord.File("sep_anuncio.png", filename="sep_anuncio.png"))
            novos_itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://sep_anuncio.png")))
            
        # 2. Imagem Principal / Brasão (em outra MediaGallery para não fazer grid)
        if primeira_img_m:
            # Adiciona um espacamento entre o separador e o brasao se ambos existirem
            if os.path.exists("sep_anuncio.png"):
                novos_itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            novos_itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://" + primeira_img_m)))
            novos_itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            
        # 3. Textos (já estavam em itens_m)
        novos_itens.extend(itens_m)
        
        itens_m = novos_itens

        view_m = discord.ui.LayoutView()
        if itens_m:
            view_m.add_item(discord.ui.Container(*itens_m, accent_color=DORORO_COLOR))

        lote_principal = arquivos_m[:10]
        resto_m = arquivos_m[10:]

        try:
            if itens_m or lote_principal:
                await novo_topico.thread.send(
                    content="",
                    view=view_m if itens_m else discord.utils.MISSING,
                    files=lote_principal if lote_principal else discord.utils.MISSING
                )
            if resto_m:
                for i in range(0, len(resto_m), 10):
                    await novo_topico.thread.send(files=resto_m[i:i+10])
        except:
            pass

    await interaction.followup.send(f"✅ Tópico clonado para V2 com sucesso! [Ver novo tópico]({novo_topico.message.jump_url})")


bot.run(config.TOKEN)
