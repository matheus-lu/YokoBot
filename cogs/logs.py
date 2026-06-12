# ============================================================
#  COG: LOGS — Logs de auditoria — Ondrakos (mensagens, voz, cargos)
# ============================================================

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
BRT = timezone(timedelta(hours=-3))
from utils import gerar_imagem_log_delete
import config


class LogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_adm(self, embed, file=None):
        canal = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if canal:
            if file:
                await canal.send(file=file, embed=embed)
            else:
                await canal.send(embed=embed)

    # ── Tópico/Fórum Deletado ──────────────────────────────
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        canal_log = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if not canal_log:
            return

        agora = datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")

        deletado_por = None
        try:
            import asyncio as _asyncio
            await _asyncio.sleep(1.5)
            async def _get_deleter():
                async for entry in thread.guild.audit_logs(limit=10, action=discord.AuditLogAction.thread_delete):
                    if entry.target.id == thread.id:
                        import datetime as _dt
                        agora_utc = _dt.datetime.now(_dt.timezone.utc)
                        diff = (agora_utc - entry.created_at).total_seconds()
                        if diff < 10:
                            return entry.user
                return None
            deletado_por = await _asyncio.wait_for(_get_deleter(), timeout=5.0)
        except Exception:
            pass

        embed = discord.Embed(title="🗑️ Tópico Deletado", color=discord.Color.dark_red())
        embed.add_field(name="📂 Fórum/Categoria", value=f"{thread.parent.mention if thread.parent else 'Desconhecido'} `{thread.parent_id}`", inline=False)
        embed.add_field(name="📢 Nome do Tópico", value=f"**{thread.name}**\n`ID: {thread.id}`", inline=True)
        if deletado_por:
            embed.add_field(name="🗑️ Deletado por", value=f"{deletado_por.mention}\n`ID: {deletado_por.id}`", inline=True)
        embed.add_field(name="🕐 Horário", value=agora, inline=True)
        
        await canal_log.send(embed=embed)

    # ── Mensagem Deletada ──────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        if message.channel.id == config.MUSICA_CANAL_ID():
            return
        canal = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if not canal:
            return

        # ── Deletado pelo bot via comando interno ──────────
        info_bot = getattr(self.bot, 'mensagens_deletadas_pelo_bot', {}).pop(message.id, None)
        if info_bot:
            timestamp = message.created_at.astimezone(BRT).strftime("%d/%m/%Y %H:%M:%S")
            try:
                avatar_bytes = await message.author.display_avatar.read()
            except Exception:
                avatar_bytes = None
            embed = discord.Embed(
                title="🤖 Mensagem Deletada pelo Bot",
                description=f"O bot deletou esta mensagem automaticamente via **{info_bot.get('comando', 'comando interno')}**.",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="👤 Autor", value=f"{message.author.mention} `{message.author.id}`", inline=True)
            embed.add_field(name="📢 Canal", value=f"{message.channel.mention} `{message.channel.id}`", inline=True)
            embed.add_field(name="🔑 ID da Mensagem", value=f"`{message.id}`", inline=True)
            embed.add_field(name="⚙️ Comando", value=info_bot.get("comando", "—"), inline=True)
            if message.content:
                embed.add_field(name="💬 Conteúdo", value=message.content[:500] or "*sem texto*", inline=False)
            if message.attachments:
                nomes = ", ".join(a.filename for a in message.attachments)
                embed.add_field(name="📎 Anexos", value=nomes, inline=False)
            if avatar_bytes:
                buf = gerar_imagem_log_delete(
                    username=message.author.display_name, avatar_bytes=avatar_bytes,
                    conteudo=message.content, user_id=message.author.id,
                    guild_id=message.guild.id, canal_id=message.channel.id,
                    msg_id=message.id, timestamp=timestamp,
                    deletado_por="Bot (automático)",
                )
                arquivo = discord.File(buf, filename="log_delete.png")
                embed.set_image(url="attachment://log_delete.png")
                await canal.send(file=arquivo, embed=embed)
            else:
                await canal.send(embed=embed)
            return

        # ── Ignorar mensagens marcadas para não logar ──────
        if message.id in self.bot.mensagens_ignorar_delete:
            self.bot.mensagens_ignorar_delete.discard(message.id)
            return

        timestamp = message.created_at.astimezone(BRT).strftime("%d/%m/%Y %H:%M:%S")

        # Descobrir quem deletou via audit log
        deletado_por = None
        try:
            import asyncio as _asyncio
            await _asyncio.sleep(1.5)
            async def _get_deleter():
                async for entry in message.guild.audit_logs(limit=10, action=discord.AuditLogAction.message_delete):
                    if entry.target.id == message.author.id:
                        import datetime
                        agora = datetime.datetime.now(datetime.timezone.utc)
                        diff = (agora - entry.created_at).total_seconds()
                        if diff < 10:
                            return entry.user
                return None
            deletado_por = await _asyncio.wait_for(_get_deleter(), timeout=5.0)
        except Exception:
            pass

        try:
            avatar_bytes = await message.author.display_avatar.read()
        except Exception:
            avatar_bytes = None
        if avatar_bytes:
            deletado_por_nome = deletado_por.display_name if deletado_por and deletado_por.id != message.author.id else None
            buf = gerar_imagem_log_delete(
                username=message.author.display_name, avatar_bytes=avatar_bytes,
                conteudo=message.content, user_id=message.author.id,
                guild_id=message.guild.id, canal_id=message.channel.id,
                msg_id=message.id, timestamp=timestamp,
                deletado_por=deletado_por_nome,
            )
            arquivo = discord.File(buf, filename="log_delete.png")
            embed = discord.Embed(title="🗑️ Mensagem Deletada", color=discord.Color.dark_red())
            embed.add_field(name="👤 Autor", value=f"{message.author.mention} `{message.author.id}`", inline=True)
            embed.add_field(name="📢 Canal", value=f"{message.channel.mention} `{message.channel.id}`", inline=True)
            embed.add_field(name="🔑 ID da Mensagem", value=f"`{message.id}`", inline=True)
            if deletado_por and deletado_por.id != message.author.id:
                embed.add_field(name="🗑️ Deletado por", value=deletado_por.mention, inline=True)
            if message.content and len(message.content) > 200:
                embed.add_field(
                    name="💬 Mensagem (completa)",
                    value="```\n" + message.content[:1000] + ("..." if len(message.content) > 1000 else "") + "\n```",
                    inline=False,
                )
            embed.set_image(url="attachment://log_delete.png")
            await canal.send(file=arquivo, embed=embed)
        else:
            embed = discord.Embed(title="🗑️ Mensagem Deletada", color=discord.Color.dark_red())
            embed.add_field(name="👤 Autor", value=f"{message.author.mention}\n`{message.author.id}`", inline=True)
            embed.add_field(name="📢 Canal", value=f"{message.channel.mention}\n`{message.channel.id}`", inline=True)
            embed.add_field(name="Conteudo", value=message.content or "*sem texto*", inline=False)
            await canal.send(embed=embed)


    # ── Mensagem Deletada (Raw - pega mensagens fora do cache) ──
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.cached_message:
            return  # Já foi pego pelo on_message_delete normal

        canal_log = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if not canal_log:
            return

        canal_origem = self.bot.get_channel(payload.channel_id)
        if canal_origem and canal_origem.id == config.MUSICA_CANAL_ID():
            return

        # Tentar descobrir quem deletou via audit log
        deletado_por = None
        guild = self.bot.get_guild(payload.guild_id)
        if guild:
            try:
                import asyncio as _asyncio
                await _asyncio.sleep(1.5)
                async def _get_deleter():
                    async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.message_delete):
                        import datetime
                        agora = datetime.datetime.now(datetime.timezone.utc)
                        diff = (agora - entry.created_at).total_seconds()
                        if diff < 10:
                            return entry.user
                    return None
                deletado_por = await _asyncio.wait_for(_get_deleter(), timeout=5.0)
            except Exception:
                pass

        embed = discord.Embed(
            title="🗑️ Mensagem Deletada (Fora do Cache)",
            description="Uma mensagem antiga ou que não estava na memória do bot foi apagada.",
            color=discord.Color.dark_red()
        )
        if canal_origem:
            embed.add_field(name="📢 Canal", value=f"{canal_origem.mention}\n`{canal_origem.id}`", inline=True)
        else:
            embed.add_field(name="📢 Canal ID", value=f"`{payload.channel_id}`", inline=True)
            
        embed.add_field(name="🔑 ID da Mensagem", value=f"`{payload.message_id}`", inline=True)
        
        if deletado_por:
            embed.add_field(name="🗑️ Deletado por", value=f"{deletado_por.mention}", inline=True)

        await canal_log.send(embed=embed)

    # ── Mensagem Editada ───────────────────────────────────
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content:
            return
        canal = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if not canal:
            return
        timestamp = before.created_at.astimezone(BRT).strftime("%d/%m/%Y %H:%M:%S")
        try:
            avatar_bytes = await before.author.display_avatar.read()
        except Exception:
            avatar_bytes = None
        embed = discord.Embed(title="✏️ Mensagem Editada", color=discord.Color.orange())
        embed.add_field(name="👤 Autor", value=f"{before.author.mention}\n`ID: {before.author.id}`", inline=True)
        embed.add_field(name="📢 Canal", value=f"{before.channel.mention}\n`ID: {before.channel.id}`", inline=True)
        embed.add_field(name="📝 Antes", value="```\n" + (before.content or "*sem texto*") + "\n```", inline=False)
        embed.add_field(name="✅ Depois", value="```\n" + (after.content or "*sem texto*") + "\n```", inline=False)
        if avatar_bytes:
            buf = gerar_imagem_log_delete(
                username=before.author.display_name, avatar_bytes=avatar_bytes,
                conteudo="Antes: " + before.content, user_id=before.author.id,
                guild_id=before.guild.id, canal_id=before.channel.id,
                msg_id=before.id, timestamp=timestamp,
            )
            arquivo = discord.File(buf, filename="log_edit.png")
            embed.set_image(url="attachment://log_edit.png")
            await canal.send(file=arquivo, embed=embed)
        else:
            embed.set_thumbnail(url=before.author.display_avatar.url)
            await canal.send(embed=embed)

    # ── Cargo Adicionado/Removido ──────────────────────────
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        cargos_add = [r for r in after.roles if r not in before.roles]
        cargos_rem = [r for r in before.roles if r not in after.roles]
        if cargos_add:
            embed = discord.Embed(title="🎖️ Cargo Adicionado", color=discord.Color.blue())
            embed.add_field(name="👤 Usuário", value=f"{after.mention}\n`ID: {after.id}`", inline=True)
            embed.add_field(name="🎖️ Cargo adicionado", value=", ".join(r.mention for r in cargos_add), inline=True)
            embed.set_thumbnail(url=after.display_avatar.url)
            await self.log_adm(embed)
        if cargos_rem:
            embed = discord.Embed(title="🎖️ Cargo Removido", color=discord.Color.orange())
            embed.add_field(name="👤 Usuário", value=f"{after.mention}\n`ID: {after.id}`", inline=True)
            embed.add_field(name="🎖️ Cargo removido", value=", ".join(r.mention for r in cargos_rem), inline=True)
            embed.set_thumbnail(url=after.display_avatar.url)
            await self.log_adm(embed)

    # ── Voz: Entrou, Saiu, Trocou ──────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        canal_log = self.bot.get_channel(config.ADM_LOG_CANAL_ID())
        if not canal_log:
            return
        agora = datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")

        if member.id == self.bot.user.id:
            if hasattr(self.bot, 'ignorar_log_voz') and member.guild.id in self.bot.ignorar_log_voz:
                return
            if before.channel is None and after.channel is not None:
                convocado_por = self.bot.dj_convocado_por.pop(member.guild.id, None)
                embed = discord.Embed(
                    title="🎵 DJ Convocado",
                    description="🐉 **DJ Ondrakos** convocado na sala **" + after.channel.name + "**!",
                    color=discord.Color.from_rgb(31, 139, 76)
                )
                embed.add_field(name="🔊 Canal", value="**" + after.channel.name + "**\n`ID: " + str(after.channel.id) + "`", inline=True)
                if convocado_por:
                    embed.add_field(name="👤 Convocado por", value=convocado_por.mention + "\n`ID: " + str(convocado_por.id) + "`", inline=True)
                embed.add_field(name="🕐 Horário", value=agora, inline=True)
                await canal_log.send(embed=embed)
            elif before.channel is not None and after.channel is None:
                import asyncio as _aio
                parado_por = "NAO_REGISTRADO"
                for _ in range(20):
                    val = self.bot.dj_parado_por.get(member.guild.id, "NAO_REGISTRADO")
                    if val != "NAO_REGISTRADO":
                        parado_por = self.bot.dj_parado_por.pop(member.guild.id)
                        break
                    await _aio.sleep(0.1)
                embed = discord.Embed(
                    title="🎵 DJ Dispensado",
                    description="🌙 A festa acabou. O DJ voltou para o santuário.",
                    color=discord.Color.from_rgb(100, 50, 150)
                )
                embed.add_field(name="🔇 Saiu de", value="**" + before.channel.name + "**\n`ID: " + str(before.channel.id) + "`", inline=True)
                if parado_por == "NAO_REGISTRADO":
                    embed.add_field(name="👤 Parado por", value="⏱️ Automático", inline=True)
                elif parado_por is None:
                    embed.add_field(name="👤 Parado por", value="⏱️ Automático (fila/timeout)", inline=True)
                else:
                    embed.add_field(name="👤 Parado por", value=parado_por.mention + "\n`ID: " + str(parado_por.id) + "`", inline=True)
                embed.add_field(name="🕐 Horário", value=agora, inline=True)
                await canal_log.send(embed=embed)
            return

        if before.channel is None and after.channel is not None:
            embed = discord.Embed(title="🎙️ Entrou no Canal de Voz", color=discord.Color.green())
            embed.add_field(name="👤 Membro", value=f"{member.mention}\n`{member.id}`", inline=True)
            embed.add_field(name="🔊 Canal", value=f"**{after.channel.name}**\n`{after.channel.id}`", inline=True)
            embed.add_field(name="🕐 Horario", value=agora, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await canal_log.send(embed=embed)
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(title="🔇 Saiu do Canal de Voz", color=discord.Color.red())
            embed.add_field(name="👤 Membro", value=f"{member.mention}\n`{member.id}`", inline=True)
            embed.add_field(name="🔊 Canal", value=f"**{before.channel.name}**\n`{before.channel.id}`", inline=True)
            embed.add_field(name="🕐 Horario", value=agora, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await canal_log.send(embed=embed)
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            embed = discord.Embed(title="🔄 Trocou de Canal de Voz", color=discord.Color.blue())
            embed.add_field(name="👤 Membro", value=f"{member.mention}\n`ID: {member.id}`", inline=True)
            embed.add_field(name="📤 Saiu de", value=f"**{before.channel.name}**\n`ID: {before.channel.id}`", inline=True)
            embed.add_field(name="📥 Entrou em", value=f"**{after.channel.name}**\n`ID: {after.channel.id}`", inline=True)
            embed.add_field(name="🕐 Horario", value=agora, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await canal_log.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LogsCog(bot))