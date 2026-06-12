import discord
from discord.ext import commands
from discord.ui import Modal, View, LayoutView, Container, TextDisplay, ActionRow, Button, MediaGallery, MediaGalleryItem, Separator
from discord import app_commands
import datetime

DORORO_COLOR = discord.Color.from_rgb(31, 139, 76)
CARGO_AVISO_CHAT_ID = 123456789012345678  # Substitua pelo ID real do cargo quando tiver

class AvisoChatButton(Button):
    def __init__(self, is_accept: bool):
        custom_id = "aviso_chat_aceitar" if is_accept else "aviso_chat_recusar"
        label = "Aceitar" if is_accept else "Recusar"
        # Usando os emojis padrão do Discord para representar positivo/negativo
        # Se os emojis "positivo" e "negativo" forem customizados, substitua pela string ou id deles.
        emoji = "✅" if is_accept else "❌"
        style = discord.ButtonStyle.success if is_accept else discord.ButtonStyle.danger
        super().__init__(label=label, style=style, emoji=emoji, custom_id=custom_id)
        self.is_accept = is_accept

    async def callback(self, interaction: discord.Interaction):
        # Atrasar para evitar lentidão
        await interaction.response.defer(ephemeral=True)
        
        membro = interaction.guild.get_member(interaction.user.id)
        if not membro:
            return
            
        cargo = interaction.guild.get_role(CARGO_AVISO_CHAT_ID)
        
        if self.is_accept:
            if cargo:
                if cargo not in membro.roles:
                    await membro.add_roles(cargo, reason="Aceitou aviso de chat")
                    await interaction.followup.send("✅ Você aceitou as regras e agora pode falar no chat de voz!", ephemeral=True)
                else:
                    await interaction.followup.send("Você já aceitou e possui o cargo.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ O cargo ainda não foi configurado pelo administrador.", ephemeral=True)
        else:
            if cargo and cargo in membro.roles:
                await membro.remove_roles(cargo, reason="Recusou aviso de chat")
            await interaction.followup.send("❌ Você recusou o aviso e não tem permissão para falar.", ephemeral=True)


class AvisoChatLayout(LayoutView):
    def __init__(self, titulo: str, mensagem: str, footer: str, imagem_bytes: bytes = None, filename: str = None, sep_bytes: bytes = None, sep_filename: str = None):
        super().__init__(timeout=None)
        
        itens = []
        
        # Se tiver imagem principal
        if imagem_bytes and filename:
            itens.append(MediaGallery(MediaGalleryItem(f"attachment://{filename}")))
            itens.append(Separator(spacing=discord.SeparatorSpacing.small))
            
        # Titulo e conteudo
        itens.extend([
            TextDisplay(f"**{titulo}**"),
            Separator(spacing=discord.SeparatorSpacing.small),
            TextDisplay(mensagem),
            Separator(spacing=discord.SeparatorSpacing.small)
        ])
        
        # Imagem separador
        if sep_bytes and sep_filename:
            itens.append(MediaGallery(MediaGalleryItem(f"attachment://{sep_filename}")))
            itens.append(Separator(spacing=discord.SeparatorSpacing.small))
            
        # Footer
        if footer:
            itens.append(TextDisplay(f"-# {footer}"))
            
        # Botoes
        row = ActionRow(AvisoChatButton(is_accept=True), AvisoChatButton(is_accept=False))
        
        # A view v2 permite ActionRows diretamente
        self.add_item(Container(*itens, row, accent_color=DORORO_COLOR.value))


class AvisoChatLayoutVazio(LayoutView):
    """View apenas para registro no start do bot para que os botões voltem a funcionar"""
    def __init__(self):
        super().__init__(timeout=None)
        row = ActionRow(AvisoChatButton(is_accept=True), AvisoChatButton(is_accept=False))
        self.add_item(Container(row, accent_color=DORORO_COLOR.value))


class AvisoChatModal(Modal):
    def __init__(self, canal: discord.TextChannel):
        super().__init__(title="💬 Criar Aviso de Chat")
        self.canal = canal

        self.titulo = discord.ui.TextInput(
            label="Título",
            placeholder="Ex: 📜 Regras do Chat de Voz",
            required=True, max_length=256
        )
        self.mensagem = discord.ui.TextInput(
            label="Conteúdo da Mensagem",
            style=discord.TextStyle.paragraph,
            placeholder="Digite o conteúdo do aviso...",
            required=True, max_length=4000
        )
        self.footer = discord.ui.TextInput(
            label="Rodapé (Footer)",
            placeholder="Ex: Leia com atenção.",
            required=False, max_length=200
        )
        
        self.add_item(self.titulo)
        self.add_item(self.mensagem)
        self.add_item(self.footer)

    async def on_submit(self, interaction: discord.Interaction):
        # Passo 1: Informações de texto prontas. Agora pedir as imagens no canal do admin
        await interaction.response.send_message(
            "⏳ Preparando envio... Agora, **envie a imagem principal** neste canal. "
            "(Envie 'pular' para não usar imagem ou 'cancelar' para abortar)",
            ephemeral=True
        )
        
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        # Imagem principal
        try:
            msg_img = await interaction.client.wait_for("message", check=check, timeout=120)
        except Exception:
            await interaction.followup.send("Tempo esgotado para a imagem.", ephemeral=True)
            return

        if msg_img.content.strip().lower() == "cancelar":
            try: await msg_img.delete()
            except: pass
            await interaction.followup.send("Cancelado.", ephemeral=True)
            return

        imagem_bytes = None
        imagem_filename = None
        if msg_img.attachments:
            att = msg_img.attachments[0]
            if att.content_type and att.content_type.startswith("image"):
                imagem_bytes = await att.read()
                imagem_filename = att.filename
                
        try: await msg_img.delete()
        except: pass

        # Separador (podemos apenas carregar localmente do servidor se quisermos igual os anuncios)
        import os
        sep_path = os.path.join(os.path.dirname(__file__), "..", "sep_anuncio.png")
        sep_bytes = None
        sep_filename = "sep_anuncio.png"
        if os.path.exists(sep_path):
            with open(sep_path, "rb") as f:
                sep_bytes = f.read()

        # Criar a view
        view = AvisoChatLayout(
            titulo=self.titulo.value,
            mensagem=self.mensagem.value,
            footer=self.footer.value or "Aviso de Chat",
            imagem_bytes=imagem_bytes,
            filename=imagem_filename,
            sep_bytes=sep_bytes,
            sep_filename=sep_filename
        )

        arquivos = []
        if imagem_bytes:
            import io
            arquivos.append(discord.File(io.BytesIO(imagem_bytes), filename=imagem_filename))
        if sep_bytes:
            import io
            arquivos.append(discord.File(io.BytesIO(sep_bytes), filename=sep_filename))

        # Enviar no canal destino
        try:
            if arquivos:
                await self.canal.send(files=arquivos, view=view)
            else:
                await self.canal.send(view=view)
            
            await interaction.followup.send(f"✅ Aviso enviado com sucesso no canal {self.canal.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao enviar aviso: {e}", ephemeral=True)


class AvisoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Registrando a view genérica persistente
        self.bot.add_view(AvisoChatLayoutVazio())

    @app_commands.command(name="aviso-chat", description="Enviar um layout V2 de aviso num canal com botões de Aceitar/Recusar")
    @app_commands.checks.has_permissions(administrator=True)
    async def aviso_chat_cmd(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        canal_destino = canal or interaction.channel
        modal = AvisoChatModal(canal=canal_destino)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(AvisoChatCog(bot))
