# ============================================================
#  COG: IA JORNALISTA — Assistente de redação — Ondrakos
# ============================================================

import discord
from discord.ext import commands
from discord.ui import Button
try:
    from discord import app_commands
except ImportError:
    from types import SimpleNamespace
    def _noop_decorator(*a, **kw):
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

import aiohttp, json, os
import config

DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)
IA_COLOR = discord.Color.from_rgb(31, 139, 76)

# Historico de mensagens por canal: {canal_id: [{"role": ..., "parts": [...]}]}
ia_historico = {}

def carregar_contexto():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ia_contexto.txt')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return "Voce e um jornalista senior do Ondrakos. Ajude os jornalistas a escrever materias."

async def perguntar_ia(historico: list) -> str:
    """Chama a API do Groq com o historico de mensagens."""
    # Converter formato Gemini para formato OpenAI/Groq
    mensagens = []
    for msg in historico:
        role = "user" if msg["role"] == "user" else "assistant"
        text = msg["parts"][0]["text"] if msg.get("parts") else ""
        mensagens.append({"role": role, "content": text})

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + (config.GROQ_API_KEY or ""),
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": mensagens,
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print("Groq erro " + str(resp.status) + ": " + text[:300])
                    return "Desculpe, ocorreu um erro ao consultar a IA. Tente novamente."
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("Groq excecao: " + str(e))
        return "Desculpe, nao consegui me conectar. Tente novamente em instantes."



class IABoasVindasLayout(discord.ui.LayoutView):
    def __init__(self, member_name: str, mencoes: str, tem_img: bool = False):
        super().__init__(timeout=None)
        
        texto = (
            f"{mencoes}\n\n"
            "**🤖 │▸Oráculo do Dragão › RyuIA**\n\n"
            f"Olá, {member_name}!\n"
            "Sou a RyuIA, o espírito auxiliar do santuário.\n\n"
            "Estou aqui para te ajudar a transformar ideias soltas em algo mais bonito, organizado e pronto para usar dentro do servidor.\n\n"
            "🐉 ⧽Posso te ajudar com:\n\n"
            "📰 ⧽Criar textos, anúncios e avisos\n"
            "✍️ ⧽Montar títulos, descrições e embeds\n"
            "📜 ⧽Organizar lore, histórias e personagens\n"
            "💡 ⧽Sugerir ideias para canais, cargos e sistemas\n"
            "🎭 ⧽Ajudar com temas sobrenaturais, Japão, dragões e clãs\n"
            "🛠️ ⧽Dar apoio em pedidos de serviços e projetos\n\n"
            "⛩️ ⧽Como usar:\n"
            "Basta me contar o que você quer criar.\n"
            "Pode mandar sua ideia do seu jeito, mesmo que esteja bagunçada, e eu ajudo a organizar.\n\n"
            "O chat AI não cria tudo sozinha do nada.\n"
            "Ela trabalha melhor quando você traz a base, a ideia ou o objetivo.\n\n"
            "🌙 ⧽Chame pelo oráculo quando precisar dar forma às suas ideias. O dragão responde através da névoa.\n\n"
            "-# Ondrakos · RyuIA · Use com sabedoria"
        )
        
        itens = []
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://chat_ia.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        
        itens.extend([
            discord.ui.TextDisplay(texto),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(IAFecharButton())
        ])
        
        self.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))

class IAPainelLayout(discord.ui.LayoutView):
    def __init__(self, tem_img: bool = False):
        super().__init__(timeout=None)
        
        texto = (
            "**🤖│▸Oráculo do Dragão › IA do Servidor**\n\n"
            "O Oráculo do Dragão é uma IA criada para ajudar os membros a desenvolver ideias, organizar histórias e dar forma aos projetos do servidor.\n\n"
            "Ela pode auxiliar com lore, personagens, narrativas, textos, ideias sobrenaturais, nomes, descrições e detalhes criativos ligados ao clima japonês, místico e fantástico do servidor.\n\n"
            "Use a IA quando quiser transformar uma ideia solta em algo mais bonito, organizado e pronto para usar.\n\n"
            "🐲 ⧽**Papel da IA**\n\n"
            "📜 ⧽**Assistente de Lore** › histórias, mitologias, clãs, reinos, criaturas e regras mágicas\n\n"
            "🎭 ⧽**Criadora de Personagens** › personalidades, aparências, poderes, origens e relações\n\n"
            "🌙 ⧽**Narradora Sobrenatural** › cenas, eventos, missões, rituais e momentos dramáticos\n\n"
            "🖊️ ⧽**Apoio para Textos** › descrições, anúncios, embeds e conteúdos personalizados\n\n"
            "A IA não substitui a criatividade dos membros. Ela serve como guia para organizar e dar vida às ideias.\n\n"
            "✨ ⧽Chame o Oráculo quando precisar de inspiração. O dragão responde aos que atravessam o portal.\n\n"
            "-# Ondrakos · Oráculo do Dragão · Use com sabedoria"
        )
        
        itens = []
        if tem_img:
            itens.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://IaImage.png")))
            itens.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            
        itens.extend([
            discord.ui.TextDisplay(texto),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(IAPedirAjudaButton())
        ])
        
        self.add_item(discord.ui.Container(*itens, accent_color=DORORO_COLOR))


class IAFecharButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Encerrar sessão", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ia_fechar")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Apenas administradores podem encerrar.", ephemeral=True)
            return
        canal = interaction.channel
        ia_historico.pop(canal.id, None)
        await interaction.response.send_message("Encerrando sessão...")
        await canal.delete()


class IAPedirAjudaButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pedir ajuda à IA", style=discord.ButtonStyle.danger, emoji="🤖", custom_id="ia_pedir_ajuda")

    async def callback(self, interaction: discord.Interaction):
        guild    = interaction.guild
        member   = interaction.user
        categoria = guild.get_channel(config.IA_CATEGORIA_ID())

        if not categoria:
            await interaction.response.send_message("Categoria nao encontrada.", ephemeral=True)
            return

        # Verificar se já tem canal aberto para esse usuário
        nome_canal = "🗓️│ia-" + member.display_name.lower().replace(" ", "-")
        canal_existente = discord.utils.get(categoria.channels, name=nome_canal)
        if canal_existente:
            await interaction.response.send_message(
                f"Voce ja tem uma sessao aberta em {canal_existente.mention}!",
                ephemeral=True
            )
            return

        # Permissões do canal
        proprietario_role = guild.get_role(config.IA_PROPRIETARIO_ID())
        dev_role          = guild.get_role(config.IA_DEV_ID())

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member:             discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if proprietario_role:
            overwrites[proprietario_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if dev_role:
            overwrites[dev_role]          = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        canal = await categoria.create_text_channel(name=nome_canal, overwrites=overwrites)

        # Mensagem de boas vindas — evitar mencionar o mesmo cargo 2x
        mencoes_set = [member.mention]
        if proprietario_role:
            mencoes_set.append(proprietario_role.mention)
        if dev_role and dev_role != proprietario_role:
            mencoes_set.append(dev_role.mention)
        mencoes = " ".join(mencoes_set)

        import os as _os
        chat_img = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'chat_ia.png'))
        tem_img = _os.path.exists(chat_img) and _os.path.getsize(chat_img) < 9_000_000
        view = IABoasVindasLayout(member_name=member.display_name, mencoes=mencoes, tem_img=tem_img)
        
        if tem_img:
            await canal.send(view=view, file=discord.File(chat_img, filename="chat_ia.png"))
        else:
            await canal.send(view=view)

        # Inicializar histórico com o contexto
        contexto = carregar_contexto()
        ia_historico[canal.id] = [
            {"role": "user",  "parts": [{"text": contexto}]},
            {"role": "model", "parts": [{"text": "Entendido! Sou a RyuIA, o espírito auxiliar do santuário. Como posso te ajudar hoje?"}]},
        ]

        await interaction.response.send_message(
            f"Sessao criada em {canal.mention}!", ephemeral=True
        )


async def _criar_embed_ia(canal):
    import os
    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'IaImage.png')
    tem_img = os.path.exists(img_path) and os.path.getsize(img_path) < 9_000_000
    
    view = IAPainelLayout(tem_img=tem_img)
    if tem_img:
        await canal.send(view=view, file=discord.File(img_path, filename="IaImage.png"))
    else:
        await canal.send(view=view)


class IAJornalistaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id not in ia_historico:
            return
        # Ignorar canais especificos que nao sao de IA
        IA_CANAIS_IGNORAR = {1507715792198828034}
        if message.channel.id in IA_CANAIS_IGNORAR:
            ia_historico.pop(message.channel.id, None)
            return
        # Só responder em canais com o padrão de IA: 🗓️│ia-nome
        nome_canal = message.channel.name.lower()
        if not ("ia-" in nome_canal or nome_canal.startswith("🗓")):
            ia_historico.pop(message.channel.id, None)
            return

        # Ignorar comandos
        if message.content.startswith('/'):
            return

        async with message.channel.typing():
            historico = ia_historico[message.channel.id]
            historico.append({
                "role": "user",
                "parts": [{"text": message.content}]
            })

            resposta = await perguntar_ia(historico)

            historico.append({
                "role": "model",
                "parts": [{"text": resposta}]
            })

            # Limitar histórico a 40 mensagens (mantém contexto inicial)
            if len(historico) > 7:
                ia_historico[message.channel.id] = historico[:2] + historico[-5:]

            # Dividir resposta se for muito longa
            if len(resposta) <= 2000:
                await message.reply(resposta)
            else:
                partes = [resposta[i:i+1990] for i in range(0, len(resposta), 1990)]
                for parte in partes:
                    await message.channel.send(parte)

    @app_commands.command(name="ia-setup", description="Recriar embed do assistente sobrenatural (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ia_setup(self, interaction: discord.Interaction):
        canal = interaction.guild.get_channel(config.IA_CANAL_ID())
        if not canal:
            await interaction.response.send_message("Canal de IA nao encontrado.", ephemeral=True)
            return
        await _criar_embed_ia(canal)
        await interaction.response.send_message("Embed criado!", ephemeral=True)




async def setup(bot):
    await bot.add_cog(IAJornalistaCog(bot))
    bot.add_view(IAPainelLayout())
    bot.add_view(IABoasVindasLayout(member_name="Usuário", mencoes=""))