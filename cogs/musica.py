# ============================================================
#  COG: MÚSICA — Player de música — Ondrakos
#  Components V2 + Views persistentes + Spotify + YouTube
# ============================================================

import discord
from discord.ext import commands
from discord.ui import View, Button
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
import asyncio, yt_dlp, urllib.parse, aiohttp, base64, time
import config

# ── Spotify helpers ────────────────────────────────────────
_spotify_token = None
_spotify_token_expiry = 0

async def _get_spotify_token():
    global _spotify_token, _spotify_token_expiry
    if _spotify_token and time.time() < _spotify_token_expiry - 60:
        return _spotify_token
    creds = base64.b64encode(
        (config.SPOTIFY_CLIENT_ID + ":" + config.SPOTIFY_CLIENT_SECRET).encode()
    ).decode()
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": "Basic " + creds, "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
        ) as resp:
            data = await resp.json()
            _spotify_token = data["access_token"]
            _spotify_token_expiry = time.time() + data["expires_in"]
    return _spotify_token

async def resolver_spotify(url):
    token = await _get_spotify_token()
    headers = {"Authorization": "Bearer " + token}
    faixas = []
    async with aiohttp.ClientSession() as session:
        if "/playlist/" in url:
            playlist_id = url.split("/playlist/")[1].split("?")[0]
            offset = 0
            while True:
                async with session.get(
                    "https://api.spotify.com/v1/playlists/" + playlist_id + "/tracks?limit=50&offset=" + str(offset),
                    headers=headers,
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    track = item.get("track")
                    if not track:
                        continue
                    artistas = ", ".join(a["name"] for a in track.get("artists", []))
                    faixas.append(track["name"] + " " + artistas)
                if len(items) < 50:
                    break
                offset += 50
        elif "/album/" in url:
            album_id = url.split("/album/")[1].split("?")[0]
            async with session.get(
                "https://api.spotify.com/v1/albums/" + album_id + "/tracks?limit=50",
                headers=headers,
            ) as resp:
                data = await resp.json()
            for track in data.get("items", []):
                artistas = ", ".join(a["name"] for a in track.get("artists", []))
                faixas.append(track["name"] + " " + artistas)
        elif "/track/" in url:
            track_id = url.split("/track/")[1].split("?")[0]
            async with session.get(
                "https://api.spotify.com/v1/tracks/" + track_id,
                headers=headers,
            ) as resp:
                data = await resp.json()
            artistas = ", ".join(a["name"] for a in data.get("artists", []))
            faixas.append(data["name"] + " " + artistas)
    return faixas


# ── Constantes yt-dlp ──────────────────────────────────────
YDL_OPTIONS_SINGLE = {
    "format": "bestaudio/best",
    "quiet": False,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "ignoreerrors": False,
    "cookiefile": config.COOKIES_PATH,
    "js_runtimes": {"node": {"path": "/usr/bin/node"}},
    "extractor_args": {
        "youtube": {"player_client": ["web"]},
        "youtubepot-bgutilscript": {"server_home": ["/application/bgutil-ytdlp-pot-provider/server"]},
    },
}

_ydl_instance = None

def get_ydl():
    global _ydl_instance
    if _ydl_instance is None:
        _ydl_instance = yt_dlp.YoutubeDL(YDL_OPTIONS_SINGLE)
    return _ydl_instance

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-probesize 200M -analyzeduration 0"
    ),
    "options": "-vn -ss 0",
}

filas = {}
tocando_agora = {}
mensagem_player = {}
player_image_url = None  # URL CDN do player.png — definida quando a mensagem é criada
repetindo = {}
historico = {}
status_canal_original = {}
status_canal_cache = {}

DONO_ID = 673107593991815179
FRASES_DONO = [
    '🐉 ⧽"O dragão chama."', '🔥 ⧽"A chama nunca morre."', '🌙 ⧽"Sob a lua, despertamos."',
    '🐲 ⧽"O rugido ecoa."', '⚔️ ⧽"Entre no covil."', '🔥 ⧽"Queime seu destino."',
    '🌊 ⧽"As marés obedecem."', '🍃 ⧽"A floresta sussurra."', '🩸 ⧽"O caos observa."',
    '🐉 ⧽"A lenda respira."', '🏯 ⧽"O clã desperta."', '✨ ⧽"Carregue sua marca."',
    '🔥 ⧽"Honre a chama."', '🐲 ⧽"Desperte o dragão."', '🌙 ⧽"A lua nos guia."',
    '⚔️ ⧽"O destino ruge."', '🐉 ⧽"Aqui nasce a lenda."', '🔥 ⧽"Chamas contam histórias."',
    '🌊 ⧽"Siga as marés."', '🩸 ⧽"Nada controla o caos."', '🐉 ⧽"O dragão desperta"',
    '🔥 ⧽"Reino dos dragões"', '🐲 ⧽"Sob o olhar do dragão"', '🌙 ⧽"Covil do dragão"',
    '⚔️ ⧽"Chamado do dragão"', '🏯 ⧽"Salão dos dragões"', '🌊 ⧽"Entre marés e chamas"',
    '🍃 ⧽"Guiado pelo dragão"', '🩸 ⧽"O caos observa"', '✨ ⧽"Lendas despertam"',
]
_status_dono_tasks = {}
_status_dono_fila = {}

PLAYER_COLOR = discord.Color.from_rgb(31, 139, 76)

# ── URL da playlist especial (preencher aqui) ──────────────
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLXvc_iXcGX16gITfKfby5zfTTwppfnOII"  # Ex: "https://www.youtube.com/playlist?list=..."
                   # ou link do Spotify


def get_fila(guild_id):
    if guild_id not in filas:
        filas[guild_id] = []
    return filas[guild_id]


def _proxima_frase_dono(channel_id, atual):
    import random
    fila = _status_dono_fila.get(channel_id, [])
    fila = [f for f in fila if f != atual]
    if not fila:
        fila = [f for f in FRASES_DONO if f != atual]
        random.shuffle(fila)
    proximo = fila.pop(0)
    _status_dono_fila[channel_id] = fila
    return proximo


async def _rodar_status_dono(channel_id, bot, frase_inicial):
    atual = frase_inicial
    try:
        while True:
            await asyncio.sleep(30 * 60)
            proximo = _proxima_frase_dono(channel_id, atual)
            atual = proximo
            try:
                await bot.http.request(
                    discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=channel_id),
                    json={"status": atual},
                )
            except Exception as e:
                print(f"[Status Canal] Erro ao trocar frase: {e}")
    except asyncio.CancelledError:
        pass


def _parar_status_dono(channel_id):
    task = _status_dono_tasks.pop(channel_id, None)
    if task and not task.done():
        task.cancel()
    _status_dono_fila.pop(channel_id, None)


def _iniciar_status_dono(channel_id, bot, frase):
    import random
    _parar_status_dono(channel_id)
    fila = [f for f in FRASES_DONO if f != frase]
    random.shuffle(fila)
    _status_dono_fila[channel_id] = fila
    task = asyncio.create_task(_rodar_status_dono(channel_id, bot, frase))
    _status_dono_tasks[channel_id] = task


async def resolver_url(entry):
    loop = asyncio.get_event_loop()
    target = entry.get("pagina") or entry.get("webpage_url") or entry.get("url", "")
    
    if entry.get("needs_fallback") and entry.get("titulo"):
        target = "ytsearch1:" + entry["titulo"] + (" " + entry["canal"] if entry.get("canal") and entry["canal"] != "Desconhecido" else "")
    elif not target and entry.get("titulo"):
        target = "ytsearch:" + entry["titulo"]

    if not target:
        return None

    for tentativa in range(2):
        try:
            ydl = get_ydl()
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(target, download=False))
            if info and "entries" in info and info["entries"]:
                info = info["entries"][0]
            
            if info and "url" in info:
                novo_titulo = info.get("title")
                if novo_titulo == "videoplayback" or not novo_titulo:
                    novo_titulo = entry.get("titulo") or entry.get("title", "Desconhecido")
                else:
                    novo_titulo = entry.get("titulo") or novo_titulo
                    
                return {
                    "url": info["url"],
                    "titulo": novo_titulo,
                    "duracao": entry.get("duracao") or info.get("duration", 0),
                    "thumbnail": entry.get("thumbnail") or info.get("thumbnail", None),
                    "pagina": info.get("webpage_url") or entry.get("pagina") or target,
                    "canal": entry.get("canal") or info.get("uploader", "Desconhecido"),
                    "titulo_embed": entry.get("titulo_embed"),
                    "needs_resolve": False,
                    "falhas": entry.get("falhas", 0),
                    "http_headers": info.get("http_headers", {})
                }
        except Exception as e:
            print("MUSICA ERRO resolver_url: " + type(e).__name__ + ": " + str(e))
            global _ydl_instance
            _ydl_instance = None
            
        if tentativa == 0 and entry.get("titulo"):
            target = "ytsearch1:" + entry["titulo"] + (" " + entry["canal"] if entry.get("canal") and entry["canal"] != "Desconhecido" else "")
        else:
            break

    return None


async def buscar_info(query):
    loop = asyncio.get_event_loop()
    eh_link = query.startswith("http://") or query.startswith("https://") or query.startswith("www.")
    if eh_link and "spotify.com" in query:
        try:
            faixas = await resolver_spotify(query)
            if not faixas:
                return None
            if len(faixas) == 1:
                return await buscar_info(faixas[0])
            return {
                "tipo": "playlist",
                "musicas": [{"titulo": f, "url": None, "duracao": 0, "thumbnail": None,
                             "pagina": "", "canal": "Spotify", "needs_resolve": True} for f in faixas]
            }
        except Exception as e:
            print("SPOTIFY ERRO: " + type(e).__name__ + ": " + str(e))
            return None
    if not eh_link:
        query = "ytsearch:" + query
    eh_playlist = eh_link and "list=" in query and ("youtube.com" in query or "youtu.be" in query)
    if eh_playlist and "v=" in query:
        try:
            parsed = urllib.parse.urlparse(query)
            params = urllib.parse.parse_qs(parsed.query)
            list_id = params.get("list", [None])[0]
            index = params.get("index", [None])[0]
            if list_id:
                playlist_url = "https://www.youtube.com/playlist?list=" + list_id
                if index:
                    playlist_url += "&index=" + index
                query = playlist_url
        except Exception:
            pass
    if eh_playlist:
        start_index = 1
        try:
            parsed = urllib.parse.urlparse(query)
            params = urllib.parse.parse_qs(parsed.query)
            start_index = int(params.get("index", [1])[0])
        except Exception:
            pass
        opts_playlist = {
            "quiet": True, "extract_flat": True, "ignoreerrors": True,
            "playliststart": start_index, "playlistend": start_index + 49,
            "cookiefile": config.COOKIES_PATH,
        }
        try:
            with yt_dlp.YoutubeDL(opts_playlist) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        except Exception:
            info = None
        if not info or "entries" not in info or not [e for e in info["entries"] if e]:
            eh_playlist = False
    if not eh_playlist:
        ydl = get_ydl()
        info2 = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        if not info2:
            return None
        if "entries" in info2:
            info2 = info2["entries"][0]
        return {
            "tipo": "musica", "url": info2["url"],
            "titulo": info2.get("title", "Desconhecido"),
            "duracao": info2.get("duration", 0),
            "thumbnail": info2.get("thumbnail", None),
            "pagina": info2.get("webpage_url", ""),
            "canal": info2.get("uploader", "Desconhecido"),
            "needs_resolve": False,
        }
    if eh_playlist:
        entries = [e for e in info["entries"] if e]
        if not entries:
            return None
        musicas = []
        for e in entries:
            vid_id = e.get("id", "")
            webpage = e.get("webpage_url") or (
                "https://www.youtube.com/watch?v=" + vid_id if vid_id else ""
            )
            musicas.append({
                "url": webpage,
                "titulo": e.get("title", "Desconhecido"),
                "duracao": e.get("duration", 0),
                "thumbnail": e.get("thumbnail") or (
                    "https://img.youtube.com/vi/" + vid_id + "/maxresdefault.jpg" if vid_id else None
                ),
                "pagina": webpage,
                "canal": e.get("uploader") or e.get("channel") or "Desconhecido",
                "needs_resolve": True,
            })
        nome_playlist = info.get("title", "Playlist")
        return {"tipo": "playlist", "titulo": nome_playlist, "musicas": musicas}

def formatar_duracao(segundos):
    if not segundos:
        return "?"
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    if h:
        return str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
    return str(m) + ":" + str(s).zfill(2)


# ── Layouts V2 do Player (com callbacks diretos) ──────────

def _bye_audio_path():
    import os as _os
    return _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'audio', 'ei_ei_oooo.mp3'))

def _dragon_audio_path():
    import os as _os
    return _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'audio', 'dragon.mp3'))


class PlayerLayoutTocando(discord.ui.LayoutView):
    """Layout V2 quando está tocando."""

    def __init__(self, musica: dict, fila: list, canal_voz: str = None, guild_id: int = None, pausado: bool = False):
        super().__init__(timeout=None)
        self._guild_id = guild_id

        duracao = formatar_duracao(musica["duracao"])
        canal_nome = musica["canal"]
        if musica.get("titulo_embed"):
            info_text = "### " + musica["titulo_embed"] + "\n⏱️ **" + duracao + "**  ·  🎙️ " + canal_nome
        else:
            info_text = "### 🎵 " + musica["titulo"] + "\n⏱️ **" + duracao + "**  ·  🎙️ " + canal_nome
        if canal_voz:
            info_text += "  ·  🔊 **" + canal_voz + "**"

        if fila:
            proximas = "\n".join(["**" + str(i+1) + ".** " + m["titulo"] for i, m in enumerate(fila[:4])])
            if len(fila) > 4:
                proximas += "\n*... e mais " + str(len(fila) - 4) + " músicas*"
            fila_text = "**📋 Fila — " + str(len(fila)) + " música(s):**\n" + proximas
        else:
            fila_text = "**📋 Fila:** vazia"

        thumbnail_url = None
        if musica.get("thumbnail"):
            sep = "&" if "?" in musica["thumbnail"] else "?"
            thumbnail_url = musica["thumbnail"] + sep + "_t=" + str(int(time.time()))

        rep_ativo = repetindo.get(guild_id, False) if guild_id else False

        # Botão Pausar/Retomar muda com base no estado
        if pausado:
            btn_pausar = discord.ui.Button(label="Retomar", emoji=discord.PartialEmoji(name="_play", id=1507462784332468234), style=discord.ButtonStyle.success, custom_id="musica_pausar")
        else:
            btn_pausar = discord.ui.Button(label="Pausar", emoji=discord.PartialEmoji(name="_pause", id=1507462817450688743), style=discord.ButtonStyle.secondary, custom_id="musica_pausar")

        row1 = discord.ui.ActionRow(
            discord.ui.Button(label="Play", emoji=discord.PartialEmoji(name="_play", id=1507462784332468234), style=discord.ButtonStyle.secondary, custom_id="musica_play_disabled", disabled=True),
            btn_pausar,
            discord.ui.Button(label="Pular", emoji=discord.PartialEmoji(name="_pular", id=1507462917606346753), style=discord.ButtonStyle.secondary, custom_id="musica_pular"),
            discord.ui.Button(label="Parar", emoji=discord.PartialEmoji(name="_stop", id=1507462858244493473), style=discord.ButtonStyle.danger, custom_id="musica_parar"),
            discord.ui.Button(label="Voltar", emoji=discord.PartialEmoji(name="_voltar", id=1507462967933931520), style=discord.ButtonStyle.secondary, custom_id="musica_voltar"),
        )
        row2 = discord.ui.ActionRow(
            discord.ui.Button(label="Repetir", emoji=discord.PartialEmoji(name="_repetir", id=1507462942185095340), style=discord.ButtonStyle.success if rep_ativo else discord.ButtonStyle.secondary, custom_id="musica_repetir"),
            discord.ui.Button(label="Adicionar", emoji=discord.PartialEmoji(name="_mais", id=1514529996998443129), style=discord.ButtonStyle.success, custom_id="musica_adicionar"),
            discord.ui.Button(label="Playlist", emoji=discord.PartialEmoji(name="_playlist", id=1514529877770899546), style=discord.ButtonStyle.primary, custom_id="musica_playlist"),
            discord.ui.Button(label="Ver Fila", emoji=discord.PartialEmoji(name="_saibamais", id=1514529946444365884), style=discord.ButtonStyle.primary, custom_id="musica_ver_fila"),
        )

        filhos = [
            discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://player.png")),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        ]
        if thumbnail_url:
            filhos.append(discord.ui.MediaGallery(discord.MediaGalleryItem(thumbnail_url)))
            filhos.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        filhos += [
            discord.ui.TextDisplay(info_text),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(fila_text),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# Frequência Mística · Ondrakos · Use os botões abaixo"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            row1, row2,
        ]
        self.add_item(discord.ui.Container(*filhos, accent_color=PLAYER_COLOR))

    async def _callback_pausar(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        bot = interaction.client
        if vc and vc.is_playing():
            vc.pause()
            if tocando_agora.get(interaction.guild.id):
                await atualizar_status_canal_voz(interaction.guild, "⏸️ " + tocando_agora[interaction.guild.id]["titulo"], bot=bot)
        elif vc and vc.is_paused():
            vc.resume()
            if tocando_agora.get(interaction.guild.id):
                await atualizar_status_canal_voz(interaction.guild, tocando_agora[interaction.guild.id]["titulo"], bot=bot)
        else:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)
            return
        await interaction.response.defer()
        await atualizar_embed_player(interaction.guild, guild_id=interaction.guild.id)

    async def _callback_pular(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            if tocando_agora.get(interaction.guild.id):
                tocando_agora[interaction.guild.id]["skip_fallback"] = True
            vc.stop()
            await interaction.response.send_message("Pulando...", ephemeral=True)
        else:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)

    async def _callback_parar(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        if vc:
            await interaction.response.defer(ephemeral=True)
            if tocando_agora.get(interaction.guild.id):
                tocando_agora[interaction.guild.id]["skip_fallback"] = True
            filas.pop(interaction.guild.id, None)
            tocando_agora.pop(interaction.guild.id, None)
            bot = interaction.client
            bot.dj_parado_por[interaction.guild.id] = interaction.user
            bye = _bye_audio_path()
            import os as _os
            if _os.path.exists(bye):
                try:
                    vc.stop()
                    await asyncio.sleep(0.3)
                    vc.play(discord.FFmpegPCMAudio(bye))
                    while vc.is_playing(): await asyncio.sleep(0.1)
                except Exception: pass
            else:
                vc.stop()
            await asyncio.sleep(0.2)
            await vc.disconnect()
            await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"))
            await atualizar_embed_player(interaction.guild)
            await interaction.followup.send("Parado e saí do canal!", ephemeral=True)
        else:
            await interaction.response.send_message("Não estou em nenhum canal.", ephemeral=True)

    async def _callback_ver_fila(self, interaction: discord.Interaction, button):
        fila = get_fila(interaction.guild.id)
        atual = tocando_agora.get(interaction.guild.id)
        if not atual:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)
            return
        emb = discord.Embed(title="📋 Fila de músicas", color=PLAYER_COLOR)
        emb.add_field(name="🎵 Tocando agora", value=atual["titulo"][:200], inline=False)
        if fila:
            linhas, total = [], 0
            for i, m in enumerate(fila):
                linha = "**" + str(i+1) + ".** " + m["titulo"]
                if total + len(linha) + 1 > 900:
                    linhas.append("... e mais " + str(len(fila) - i) + " músicas")
                    break
                linhas.append(linha)
                total += len(linha) + 1
            lista = chr(10).join(linhas)
        else:
            lista = "Fila vazia"
        emb.add_field(name="A seguir (" + str(len(fila)) + " músicas)", value=lista, inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    async def _callback_voltar(self, interaction: discord.Interaction, button):
        guild = interaction.guild
        hist = historico.get(guild.id, [])
        if len(hist) < 2:
            await interaction.response.send_message("Sem música anterior no histórico.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        vc = guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            atual = tocando_agora.get(guild.id)
            if atual: get_fila(guild.id).insert(0, dict(atual))
            anterior = dict(hist[-2])
            anterior["needs_resolve"] = True
            get_fila(guild.id).insert(0, anterior)
            historico[guild.id] = hist[:-1]
            vc.stop()
        await interaction.followup.send("Voltando para música anterior!", ephemeral=True)

    async def _callback_repetir(self, interaction: discord.Interaction, button):
        guild_id = interaction.guild.id
        repetindo[guild_id] = not repetindo.get(guild_id, False)
        estado = "ativada" if repetindo[guild_id] else "desativada"
        await interaction.response.defer(ephemeral=True)
        await atualizar_embed_player(interaction.guild, guild_id=guild_id)
        await interaction.followup.send("Repetição " + estado + "!", ephemeral=True)

    async def _callback_adicionar(self, interaction: discord.Interaction, button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("O bot não está em nenhum canal de voz!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMusicaModal())

    async def _callback_playlist(self, interaction: discord.Interaction, button):
        if not PLAYLIST_URL:
            await interaction.response.send_message("❌ Nenhuma playlist configurada ainda.", ephemeral=True)
            return
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message("❌ O bot não está em nenhum canal. Pressione Play primeiro!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            resultado = await buscar_info(PLAYLIST_URL)
        except Exception as e:
            await interaction.followup.send("❌ Erro ao carregar playlist: " + str(e)[:200], ephemeral=True)
            return
        if resultado is None:
            await interaction.followup.send("❌ Não foi possível carregar a playlist.", ephemeral=True)
            return
        guild = interaction.guild
        bot = interaction.client
        fila = get_fila(guild.id)
        cancelar_timeout(guild.id)
        musicas = resultado["musicas"] if resultado["tipo"] == "playlist" else [resultado]
        nome_playlist = resultado.get("titulo") if resultado["tipo"] == "playlist" else ""
        for m in musicas:
            if nome_playlist:
                m["titulo_embed"] = f"<:_playlist:1514529877770899546> {nome_playlist} | {m['titulo']}"
            fila.append(m)
        if not vc.is_playing() and not vc.is_paused():
            await tocar_proxima(guild, bot)
        else:
            await atualizar_embed_player(guild, guild_id=guild.id)
        await interaction.followup.send(
            "🎶 Playlist adicionada! **" + str(len(musicas)) + " músicas** na fila.", ephemeral=True
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        cb = {
            "musica_pausar": self._callback_pausar,
            "musica_pular": self._callback_pular,
            "musica_parar": self._callback_parar,
            "musica_ver_fila": self._callback_ver_fila,
            "musica_voltar": self._callback_voltar,
            "musica_repetir": self._callback_repetir,
            "musica_adicionar": self._callback_adicionar,
            "musica_playlist": self._callback_playlist,
        }
        if cid in cb:
            await cb[cid](interaction, None)
            return False
        return True


class PlayerLayoutVazio(discord.ui.LayoutView):
    """Layout V2 quando não está tocando."""

    def __init__(self):
        super().__init__(timeout=None)
        row = discord.ui.ActionRow(
            discord.ui.Button(label="Play", emoji=discord.PartialEmoji(name="_play", id=1507462784332468234), style=discord.ButtonStyle.success, custom_id="musica_play"),
            discord.ui.Button(label="Pausar", emoji=discord.PartialEmoji(name="_pause", id=1507462817450688743), style=discord.ButtonStyle.secondary, custom_id="musica_pausar_disabled", disabled=True),
            discord.ui.Button(label="Pular", emoji=discord.PartialEmoji(name="_pular", id=1507462917606346753), style=discord.ButtonStyle.secondary, custom_id="musica_pular_disabled", disabled=True),
            discord.ui.Button(label="Parar", emoji=discord.PartialEmoji(name="_stop", id=1507462858244493473), style=discord.ButtonStyle.danger, custom_id="musica_parar_disabled", disabled=True),
            discord.ui.Button(label="Voltar", emoji=discord.PartialEmoji(name="_voltar", id=1507462967933931520), style=discord.ButtonStyle.secondary, custom_id="musica_voltar_disabled", disabled=True),
        )
        row2 = discord.ui.ActionRow(
            discord.ui.Button(label="Repetir", emoji=discord.PartialEmoji(name="_repetir", id=1507462942185095340), style=discord.ButtonStyle.secondary, custom_id="musica_repetir_disabled", disabled=True),
            discord.ui.Button(label="Adicionar", emoji=discord.PartialEmoji(name="_mais", id=1514529996998443129), style=discord.ButtonStyle.secondary, custom_id="musica_adicionar_disabled", disabled=True),
            discord.ui.Button(label="Playlist", emoji=discord.PartialEmoji(name="_playlist", id=1514529877770899546), style=discord.ButtonStyle.secondary, custom_id="musica_playlist_disabled", disabled=True),
            discord.ui.Button(label="Ver Fila", emoji=discord.PartialEmoji(name="_saibamais", id=1514529946444365884), style=discord.ButtonStyle.secondary, custom_id="musica_ver_fila_disabled", disabled=True),
        )
        self.add_item(discord.ui.Container(
            discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://player.png")),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("### 🎵 Frequência Mística\nPressione <:_play:1507462784332468234> **Play** para começar!\nVocê precisa estar em um canal de voz."),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("**📋 Fila:** vazia"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# Frequência Mística · Ondrakos"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            row, row2,
            accent_color=PLAYER_COLOR,
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid == "musica_play":
            await self._callback_play(interaction)
            return False
        return True

    async def _callback_play(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Você precisa estar em um canal de voz!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if vc is None:
            try:
                bot = interaction.client
                bot.dj_convocado_por[interaction.guild.id] = interaction.user
                vc = await asyncio.wait_for(interaction.user.voice.channel.connect(), timeout=30.0)
                dragon = _dragon_audio_path()
                import os as _os
                if _os.path.exists(dragon):
                    try:
                        vc.play(discord.FFmpegPCMAudio(dragon))
                        while vc.is_playing(): await asyncio.sleep(0.1)
                    except Exception: pass
            except asyncio.TimeoutError:
                await interaction.followup.send("Timeout ao conectar. Tente novamente.", ephemeral=True)
                return
            except Exception as e:
                await interaction.followup.send("Erro ao conectar: " + str(e), ephemeral=True)
                return
        await atualizar_embed_player(interaction.guild, estado="sem_musica")
        await interaction.followup.send("✅ Bot entrou em **" + interaction.user.voice.channel.name + "**! Use + Adicionar.", ephemeral=True)


class PlayerLayoutSemMusica(discord.ui.LayoutView):
    """Layout V2 quando bot está no canal mas sem música."""

    def __init__(self):
        super().__init__(timeout=None)
        row = discord.ui.ActionRow(
            discord.ui.Button(label="Play", emoji=discord.PartialEmoji(name="_play", id=1507462784332468234), style=discord.ButtonStyle.secondary, custom_id="musica_play_disabled2", disabled=True),
            discord.ui.Button(label="Pausar", emoji=discord.PartialEmoji(name="_pause", id=1507462817450688743), style=discord.ButtonStyle.secondary, custom_id="musica_sem_pausar", disabled=True),
            discord.ui.Button(label="Pular", emoji=discord.PartialEmoji(name="_pular", id=1507462917606346753), style=discord.ButtonStyle.secondary, custom_id="musica_sem_pular", disabled=True),
            discord.ui.Button(label="Parar", emoji=discord.PartialEmoji(name="_stop", id=1507462858244493473), style=discord.ButtonStyle.danger, custom_id="musica_sem_parar"),
            discord.ui.Button(label="Voltar", emoji=discord.PartialEmoji(name="_voltar", id=1507462967933931520), style=discord.ButtonStyle.secondary, custom_id="musica_sem_voltar", disabled=True),
        )
        row2 = discord.ui.ActionRow(
            discord.ui.Button(label="Repetir", emoji=discord.PartialEmoji(name="_repetir", id=1507462942185095340), style=discord.ButtonStyle.secondary, custom_id="musica_sem_repetir", disabled=True),
            discord.ui.Button(label="Adicionar", emoji=discord.PartialEmoji(name="_mais", id=1514529996998443129), style=discord.ButtonStyle.success, custom_id="musica_sem_adicionar"),
            discord.ui.Button(label="Playlist", emoji=discord.PartialEmoji(name="_playlist", id=1514529877770899546), style=discord.ButtonStyle.primary, custom_id="musica_sem_playlist"),
            discord.ui.Button(label="Ver Fila", emoji=discord.PartialEmoji(name="_saibamais", id=1514529946444365884), style=discord.ButtonStyle.primary, custom_id="musica_sem_ver_fila", disabled=True),
        )
        self.add_item(discord.ui.Container(
            discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://player.png")),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("### 🎵 Frequência Mística\nBot conectado. Adicione uma música!"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("**📋 Fila:** vazia"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# Frequência Mística · Ondrakos"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            row, row2,
            accent_color=PLAYER_COLOR,
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid == "musica_sem_parar":
            await self._callback_parar(interaction)
            return False
        if cid == "musica_sem_adicionar":
            await self._callback_adicionar(interaction)
            return False
        if cid == "musica_sem_playlist":
            await self._callback_playlist(interaction)
            return False
        return True

    async def _callback_parar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if vc:
            if tocando_agora.get(interaction.guild.id):
                tocando_agora[interaction.guild.id]["skip_fallback"] = True
            filas.pop(interaction.guild.id, None)
            tocando_agora.pop(interaction.guild.id, None)
            interaction.client.dj_parado_por[interaction.guild.id] = interaction.user
            bye = _bye_audio_path()
            import os as _os
            if _os.path.exists(bye):
                try:
                    vc.stop()
                    await asyncio.sleep(0.3)
                    vc.play(discord.FFmpegPCMAudio(bye))
                    while vc.is_playing(): await asyncio.sleep(0.1)
                except Exception: pass
            else:
                vc.stop()
            await asyncio.sleep(0.2)
            await vc.disconnect()
            await interaction.client.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"))
        await atualizar_embed_player(interaction.guild)
        await interaction.followup.send("Saí do canal!", ephemeral=True)

    async def _callback_adicionar(self, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("O bot não está em nenhum canal!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMusicaModal())

    async def _callback_playlist(self, interaction: discord.Interaction):
        if not PLAYLIST_URL:
            await interaction.response.send_message("❌ Nenhuma playlist configurada ainda.", ephemeral=True)
            return
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message("❌ O bot não está em nenhum canal. Pressione Play primeiro!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            resultado = await buscar_info(PLAYLIST_URL)
        except Exception as e:
            await interaction.followup.send("❌ Erro ao carregar playlist: " + str(e)[:200], ephemeral=True)
            return
        if resultado is None:
            await interaction.followup.send("❌ Não foi possível carregar a playlist.", ephemeral=True)
            return
        guild = interaction.guild
        bot = interaction.client
        fila = get_fila(guild.id)
        cancelar_timeout(guild.id)
        musicas = resultado["musicas"] if resultado["tipo"] == "playlist" else [resultado]
        nome_playlist = resultado.get("titulo") if resultado["tipo"] == "playlist" else ""
        for m in musicas:
            if nome_playlist:
                m["titulo_embed"] = f"<:_playlist:1514529877770899546> {nome_playlist} | {m['titulo']}"
            fila.append(m)
        if not vc.is_playing() and not vc.is_paused():
            await tocar_proxima(guild, bot)
        else:
            await atualizar_embed_player(guild, guild_id=guild.id)
        await interaction.followup.send(
            "🎶 Playlist adicionada! **" + str(len(musicas)) + " músicas** na fila.", ephemeral=True
        )


# ── Modal de adicionar música ──────────────────────────────
from discord.ui import Modal, TextInput

class AdicionarMusicaModal(Modal):
    def __init__(self):
        super().__init__(title="Adicionar Música")
        self.query = TextInput(
            label="Link ou nome da música",
            placeholder="YouTube, Spotify ou nome da música...",
            required=True,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        bot = interaction.client
        vc = guild.voice_client
        if vc is None:
            await interaction.followup.send("❌ O bot não está em nenhum canal. Pressione Play primeiro!", ephemeral=True)
            return
        try:
            resultado = await buscar_info(self.query.value)
        except Exception as e:
            await interaction.followup.send("❌ Erro ao buscar: " + str(e)[:200], ephemeral=True)
            return
        if resultado is None:
            await interaction.followup.send("❌ Nenhuma música encontrada.", ephemeral=True)
            return
        fila = get_fila(guild.id)
        cancelar_timeout(guild.id)
        if resultado["tipo"] == "playlist":
            musicas = resultado["musicas"]
            nome_playlist = resultado.get("titulo", "")
            for m in musicas:
                if nome_playlist:
                    m["titulo_embed"] = f"<:_playlist:1514529877770899546> {nome_playlist} | {m['titulo']}"
                fila.append(m)
            if not vc.is_playing() and not vc.is_paused():
                await tocar_proxima(guild, bot)
            else:
                await atualizar_embed_player(guild, guild_id=guild.id)
            await interaction.followup.send(
                "✅ Playlist adicionada! **" + str(len(musicas)) + " músicas** na fila.", ephemeral=True
            )
        else:
            if vc.is_playing() or vc.is_paused():
                fila.append(resultado)
                await atualizar_embed_player(guild, guild_id=guild.id)
                await interaction.followup.send(
                    "✅ **" + resultado["titulo"] + "** adicionada! (posição " + str(len(fila)) + ")",
                    ephemeral=True,
                )
            else:
                fila.insert(0, resultado)
                await tocar_proxima(guild, bot)
                await interaction.followup.send("▶️ Tocando **" + resultado["titulo"] + "**!", ephemeral=True)


# ── Funções de update do embed ─────────────────────────────

async def atualizar_embed_player(guild, estado: str = None, guild_id: int = None):
    """Recria o LayoutView com o estado atual e edita a mensagem do player."""
    if guild.id not in mensagem_player:
        return

    gid = guild_id or guild.id
    musica = tocando_agora.get(guild.id)
    fila = get_fila(guild.id)
    canal_voz = guild.voice_client.channel.name if guild.voice_client else None

    if estado == "sem_musica" or (not musica and guild.voice_client):
        layout = PlayerLayoutSemMusica()
    elif musica:
        pausado = guild.voice_client.is_paused() if guild.voice_client else False
        layout = PlayerLayoutTocando(musica, fila, canal_voz, guild_id=gid, pausado=pausado)
    else:
        layout = PlayerLayoutVazio()

    try:
        arquivo = discord.File(config.PLAYER_IMAGE_PATH, filename="player.png")
        await mensagem_player[guild.id].edit(embed=None, view=layout, attachments=[arquivo])
    except Exception:
        try:
            await mensagem_player[guild.id].edit(embed=None, view=layout)
        except Exception as e:
            print("Erro ao atualizar embed:", e)


timeout_tasks = {}


async def timeout_desconectar(guild, bot):
    try:
        await asyncio.sleep(300)
        if guild.voice_client and not guild.voice_client.is_playing() and not guild.voice_client.is_paused():
            filas.pop(guild.id, None)
            tocando_agora.pop(guild.id, None)
            if bot.dj_parado_por.get(guild.id, "VAZIO") == "VAZIO":
                bot.dj_parado_por[guild.id] = None
            await atualizar_status_canal_voz(guild, "", bot=bot)
            await guild.voice_client.disconnect()
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"),
            )
            await atualizar_embed_player(guild)
    except asyncio.CancelledError:
        pass
    finally:
        timeout_tasks.pop(guild.id, None)


def cancelar_timeout(guild_id):
    task = timeout_tasks.pop(guild_id, None)
    if task and not task.done():
        task.cancel()


def iniciar_timeout(guild, bot):
    cancelar_timeout(guild.id)
    task = asyncio.create_task(timeout_desconectar(guild, bot))
    timeout_tasks[guild.id] = task


async def _set_status_canal_voz(channel_id: int, bot, status: str):
    await bot.http.request(
        discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=channel_id),
        json={"status": status},
    )


async def atualizar_status_canal_voz(guild, titulo: str = "", bot=None):
    vc = guild.voice_client
    if not vc or not vc.channel or not bot:
        return
    channel_id = vc.channel.id
    try:
        if titulo:
            if guild.id not in status_canal_original:
                status_atual = ""
                try:
                    resp = await bot.http.request(discord.http.Route("GET", "/channels/{channel_id}/voice-status", channel_id=channel_id))
                    status_atual = resp.get("status", "") if resp else ""
                except Exception:
                    pass
                status_canal_original[guild.id] = status_atual
            await _set_status_canal_voz(channel_id, bot, "🎵 " + titulo)
        else:
            original = status_canal_original.pop(guild.id, "")
            await _set_status_canal_voz(channel_id, bot, original)
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"[Música] Erro ao atualizar status do canal de voz: {e}")


async def tocar_proxima(guild, bot):
    fila = get_fila(guild.id)
    if not fila:
        tocando_agora.pop(guild.id, None)
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"),
        )
        await atualizar_embed_player(guild, estado="sem_musica")
        await atualizar_status_canal_voz(guild, "", bot=bot)
        iniciar_timeout(guild, bot)
        return
    if repetindo.get(guild.id, False) and tocando_agora.get(guild.id):
        musica = dict(tocando_agora[guild.id])
        musica['needs_resolve'] = True
    else:
        musica = fila.pop(0)
    if musica.get("needs_resolve"):
        try:
            resolvida = await resolver_url(musica)
            if resolvida:
                musica = resolvida
            else:
                return await tocar_proxima(guild, bot)
        except Exception:
            return await tocar_proxima(guild, bot)
    tocando_agora[guild.id] = musica
    if not guild.voice_client or not guild.voice_client.is_connected():
        filas.pop(guild.id, None)
        tocando_agora.pop(guild.id, None)
        return
        
    ffmpeg_opts = dict(FFMPEG_OPTIONS)
    headers = musica.get("http_headers", {})
    if headers:
        headers_str = ""
        for k, v in headers.items():
            if k.lower() == "user-agent":
                ffmpeg_opts["before_options"] += f' -user_agent "{v}"'
            else:
                headers_str += f"{k}: {v}\r\n"
        if headers_str:
            ffmpeg_opts["before_options"] += f' -headers "{headers_str}"'
            
    source = discord.FFmpegPCMAudio(musica["url"], executable=config.FFMPEG_PATH, **ffmpeg_opts)

    start_time = time.time()
    def after(error):
        duracao = time.time() - start_time
        if duracao < 3 and not musica.get("skip_fallback") and musica.get("falhas", 0) < 1:
            print(f"MUSICA FAIL {musica['titulo']} falhou em {duracao:.2f}s. Tentando fallback...")
            musica["falhas"] = musica.get("falhas", 0) + 1
            musica["needs_resolve"] = True
            musica["needs_fallback"] = True
            get_fila(guild.id).insert(0, musica)
        asyncio.run_coroutine_threadsafe(tocar_proxima(guild, bot), bot.loop)

    guild.voice_client.play(source, after=after)
    if guild.id not in historico:
        historico[guild.id] = []
    historico[guild.id].append(dict(musica))
    if len(historico[guild.id]) > 10:
        historico[guild.id].pop(0)
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.listening, name=musica["titulo"]),
    )
    await atualizar_status_canal_voz(guild, musica["titulo"], bot=bot)
    await atualizar_embed_player(guild, guild_id=guild.id)


# ── View persistente para capturar botões órfãos após restart ─
# LayoutView não registra custom_ids via bot.add_view() de forma confiável,
# então usamos um View padrão (V1) apenas para registrar os custom_ids.
# Os callbacks reais ficam no interaction_check dos LayoutViews.
class _PersistentMusicaHandler(discord.ui.View):
    """View V1 invisível — só registra custom_ids para persistência."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="play", custom_id="musica_play", row=0)
    async def _play(self, interaction: discord.Interaction, button: Button):
        # Delegar para o callback real do PlayerLayoutVazio
        view = PlayerLayoutVazio()
        await view._callback_play(interaction)

    @discord.ui.button(label="pausar", custom_id="musica_pausar", row=0)
    async def _pausar(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        bot = interaction.client
        if vc and vc.is_playing():
            vc.pause()
            if tocando_agora.get(interaction.guild.id):
                await atualizar_status_canal_voz(interaction.guild, "⏸️ " + tocando_agora[interaction.guild.id]["titulo"], bot=bot)
        elif vc and vc.is_paused():
            vc.resume()
            if tocando_agora.get(interaction.guild.id):
                await atualizar_status_canal_voz(interaction.guild, tocando_agora[interaction.guild.id]["titulo"], bot=bot)
        else:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)
            return
        await interaction.response.defer()
        await atualizar_embed_player(interaction.guild, guild_id=interaction.guild.id)

    @discord.ui.button(label="pular", custom_id="musica_pular", row=0)
    async def _pular(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            if tocando_agora.get(interaction.guild.id):
                tocando_agora[interaction.guild.id]["skip_fallback"] = True
            vc.stop()
            await interaction.response.send_message("Pulando...", ephemeral=True)
        else:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)

    @discord.ui.button(label="parar", custom_id="musica_parar", row=0)
    async def _parar(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc:
            await interaction.response.defer(ephemeral=True)
            if tocando_agora.get(interaction.guild.id):
                tocando_agora[interaction.guild.id]["skip_fallback"] = True
            filas.pop(interaction.guild.id, None)
            tocando_agora.pop(interaction.guild.id, None)
            bot = interaction.client
            bot.dj_parado_por[interaction.guild.id] = interaction.user
            bye = _bye_audio_path()
            import os as _os
            if _os.path.exists(bye):
                try:
                    vc.stop()
                    await asyncio.sleep(0.3)
                    vc.play(discord.FFmpegPCMAudio(bye))
                    while vc.is_playing(): await asyncio.sleep(0.1)
                except Exception: pass
            else:
                vc.stop()
            await asyncio.sleep(0.2)
            await vc.disconnect()
            await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"))
            await atualizar_embed_player(interaction.guild)
            await interaction.followup.send("Parado e saí do canal!", ephemeral=True)
        else:
            await interaction.response.send_message("Não estou em nenhum canal.", ephemeral=True)

    @discord.ui.button(label="ver_fila", custom_id="musica_ver_fila", row=0)
    async def _ver_fila(self, interaction: discord.Interaction, button: Button):
        fila = get_fila(interaction.guild.id)
        atual = tocando_agora.get(interaction.guild.id)
        if not atual:
            await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)
            return
        emb = discord.Embed(title="📋 Fila de músicas", color=PLAYER_COLOR)
        emb.add_field(name="🎵 Tocando agora", value=atual["titulo"][:200], inline=False)
        if fila:
            linhas, total = [], 0
            for i, m in enumerate(fila):
                linha = "**" + str(i+1) + ".** " + m["titulo"]
                if total + len(linha) + 1 > 900:
                    linhas.append("... e mais " + str(len(fila) - i) + " músicas")
                    break
                linhas.append(linha)
                total += len(linha) + 1
            lista = chr(10).join(linhas)
        else:
            lista = "Fila vazia"
        emb.add_field(name="A seguir (" + str(len(fila)) + " músicas)", value=lista, inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="voltar", custom_id="musica_voltar", row=1)
    async def _voltar(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        hist = historico.get(guild.id, [])
        if len(hist) < 2:
            await interaction.response.send_message("Sem música anterior no histórico.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        vc = guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            atual = tocando_agora.get(guild.id)
            if atual: get_fila(guild.id).insert(0, dict(atual))
            anterior = dict(hist[-2])
            anterior["needs_resolve"] = True
            get_fila(guild.id).insert(0, anterior)
            historico[guild.id] = hist[:-1]
            vc.stop()
        await interaction.followup.send("Voltando para música anterior!", ephemeral=True)

    @discord.ui.button(label="repetir", custom_id="musica_repetir", row=1)
    async def _repetir(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        repetindo[guild_id] = not repetindo.get(guild_id, False)
        estado = "ativada" if repetindo[guild_id] else "desativada"
        await interaction.response.defer(ephemeral=True)
        await atualizar_embed_player(interaction.guild, guild_id=guild_id)
        await interaction.followup.send("Repetição " + estado + "!", ephemeral=True)

    @discord.ui.button(label="adicionar", custom_id="musica_adicionar", row=1)
    async def _adicionar(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("O bot não está em nenhum canal de voz!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMusicaModal())

    @discord.ui.button(label="sem_parar", custom_id="musica_sem_parar", row=2)
    async def _sem_parar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if vc:
            filas.pop(interaction.guild.id, None)
            tocando_agora.pop(interaction.guild.id, None)
            interaction.client.dj_parado_por[interaction.guild.id] = interaction.user
            bye = _bye_audio_path()
            import os as _os
            if _os.path.exists(bye):
                try:
                    vc.stop()
                    await asyncio.sleep(0.3)
                    vc.play(discord.FFmpegPCMAudio(bye))
                    while vc.is_playing(): await asyncio.sleep(0.1)
                except Exception: pass
            else:
                vc.stop()
            await asyncio.sleep(0.2)
            await vc.disconnect()
            await interaction.client.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"))
        await atualizar_embed_player(interaction.guild)
        await interaction.followup.send("Saí do canal!", ephemeral=True)

    @discord.ui.button(label="sem_adicionar", custom_id="musica_sem_adicionar", row=2)
    async def _sem_adicionar(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("O bot não está em nenhum canal!", ephemeral=True)
            return
        await interaction.response.send_modal(AdicionarMusicaModal())

    @discord.ui.button(label="playlist", custom_id="musica_playlist", row=2)
    async def _playlist(self, interaction: discord.Interaction, button: Button):
        if not PLAYLIST_URL:
            await interaction.response.send_message("❌ Nenhuma playlist configurada ainda.", ephemeral=True)
            return
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message("❌ O bot não está em nenhum canal. Pressione Play primeiro!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            resultado = await buscar_info(PLAYLIST_URL)
        except Exception as e:
            await interaction.followup.send("❌ Erro ao carregar playlist: " + str(e)[:200], ephemeral=True)
            return
        if resultado is None:
            await interaction.followup.send("❌ Não foi possível carregar a playlist.", ephemeral=True)
            return
        guild = interaction.guild
        bot = interaction.client
        fila = get_fila(guild.id)
        cancelar_timeout(guild.id)
        musicas = resultado["musicas"] if resultado["tipo"] == "playlist" else [resultado]
        nome_playlist = resultado.get("titulo") if resultado["tipo"] == "playlist" else ""
        for m in musicas:
            if nome_playlist:
                m["titulo_embed"] = f"<:_playlist:1514529877770899546> {nome_playlist} | {m['titulo']}"
            fila.append(m)
        if not vc.is_playing() and not vc.is_paused():
            await tocar_proxima(guild, bot)
        else:
            await atualizar_embed_player(guild, guild_id=guild.id)
        await interaction.followup.send(
            "🎶 Playlist adicionada! **" + str(len(musicas)) + " músicas** na fila.", ephemeral=True
        )

    @discord.ui.button(label="sem_playlist", custom_id="musica_sem_playlist", row=2)
    async def _sem_playlist(self, interaction: discord.Interaction, button: Button):
        # Mesmo callback — reutiliza a lógica do playlist principal
        await self._playlist(interaction, button)


# ── Cog principal ──────────────────────────────────────────
class MusicaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Registrar handler persistente V1 para capturar botões após restart
        bot.add_view(_PersistentMusicaHandler())

    @app_commands.command(name="sair", description="Fazer o bot sair do canal de voz")
    async def sair(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            filas.pop(interaction.guild.id, None)
            tocando_agora.pop(interaction.guild.id, None)
            interaction.client.dj_parado_por[interaction.guild.id] = interaction.user
            import os as _os
            bye_audio = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'audio', 'ei_ei_oooo.mp3'))
            if _os.path.exists(bye_audio):
                try:
                    vc.stop()
                    await asyncio.sleep(0.3)
                    vc.play(discord.FFmpegPCMAudio(bye_audio))
                    while vc.is_playing():
                        await asyncio.sleep(0.1)
                except Exception:
                    pass
            else:
                vc.stop()
            await asyncio.sleep(0.2)
            await vc.disconnect()
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"),
            )
            await atualizar_embed_player(interaction.guild)
            await interaction.response.send_message("✅ Saí do canal de voz!", ephemeral=True)
        else:
            await interaction.response.send_message("Não estou em nenhum canal de voz.", ephemeral=True)

    @commands.Cog.listener()
    async def on_socket_raw_receive(self, msg):
        import json
        try:
            data = json.loads(msg) if isinstance(msg, str) else msg
            if data.get("t") != "VOICE_CHANNEL_STATUS_UPDATE":
                return
            d = data.get("d", {})
            channel_id = int(d.get("id", 0))
            status = d.get("status") or ""
            if not channel_id:
                return
            status_canal_cache[channel_id] = status
            print(f"[Música] Status capturado via gateway: canal={channel_id} status='{status}'")
            for guild in self.bot.guilds:
                vc = guild.voice_client
                if vc and vc.channel.id == channel_id and guild.id not in status_canal_original:
                    status_canal_original[guild.id] = status
                    print(f"[Música] Status original salvo: '{status}'")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        import random

        if not member.bot and after.channel is not None and before.channel != after.channel:
            canal = after.channel
            status_atual = status_canal_cache.get(canal.id, "")
            task_existente = _status_dono_tasks.get(canal.id)
            ja_rodando = task_existente and not task_existente.done()
            if not status_atual and not ja_rodando:
                frase = random.choice(FRASES_DONO)
                try:
                    await self.bot.http.request(
                        discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=canal.id),
                        json={"status": frase},
                    )
                    _iniciar_status_dono(canal.id, self.bot, frase)
                    print(f"[Status Canal] Definido: '{frase}' em #{canal.name}")
                except Exception as e:
                    print(f"[Status Canal] Erro ao definir status: {e}")

        if not member.bot and before.channel is not None and (after.channel is None or after.channel != before.channel):
            canal = before.channel
            membros_humanos = [m for m in canal.members if not m.bot]
            if len(membros_humanos) == 0:
                _parar_status_dono(canal.id)
                vc = member.guild.voice_client
                if not vc or vc.channel != canal:
                    try:
                        await self.bot.http.request(
                            discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=canal.id),
                            json={"status": ""},
                        )
                    except Exception as e:
                        print(f"[Status Canal] Erro ao limpar status: {e}")

        if member.id == self.bot.user.id and before.channel is None and after.channel is not None:
            guild = member.guild
            if guild.id not in status_canal_original:
                original = status_canal_cache.get(after.channel.id, "")
                status_canal_original[guild.id] = original

        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            guild = member.guild
            cancelar_timeout(guild.id)
            filas.pop(guild.id, None)
            tocando_agora.pop(guild.id, None)
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"),
            )
            await atualizar_embed_player(guild)
            return

        if before.channel is not None and member.id != self.bot.user.id:
            vc = member.guild.voice_client
            if vc and vc.channel == before.channel:
                membros_humanos = [m for m in before.channel.members if not m.bot]
                if len(membros_humanos) == 0:
                    guild = member.guild
                    cancelar_timeout(guild.id)
                    filas.pop(guild.id, None)
                    tocando_agora.pop(guild.id, None)
                    if vc.is_playing() or vc.is_paused():
                        vc.stop()
                    if self.bot.dj_parado_por.get(guild.id, "VAZIO") == "VAZIO":
                        self.bot.dj_parado_por[guild.id] = None
                    await vc.disconnect()
                    await self.bot.change_presence(
                        status=discord.Status.online,
                        activity=discord.Activity(type=discord.ActivityType.playing, name="GtaV Roleplay"),
                    )
                    await atualizar_embed_player(guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id != config.MUSICA_CANAL_ID():
            return
        query = message.content.strip()
        if not query:
            return
        try:
            await message.delete()
        except Exception:
            pass
        guild = message.guild
        member = message.author
        if not member.voice:
            await message.channel.send(member.mention + " você precisa estar em um canal de voz!", delete_after=5)
            return
        vc = guild.voice_client
        if vc is None:
            try:
                vc = await member.voice.channel.connect()
                await atualizar_embed_player(guild, estado="sem_musica")
            except Exception as e:
                await message.channel.send(member.mention + " ❌ erro ao conectar: " + str(e)[:80], delete_after=5)
                return
        msg_buscando = await message.channel.send("🔍 Buscando **" + query[:80] + "**...", delete_after=30)
        try:
            resultado = await buscar_info(query)
        except Exception as e:
            await message.channel.send(member.mention + " ❌ Erro: " + str(e)[:100], delete_after=8)
            return
        if resultado is None:
            await message.channel.send(member.mention + " ❌ Nenhuma música encontrada.", delete_after=8)
            return
        fila = get_fila(guild.id)
        cancelar_timeout(guild.id)
        try:
            await msg_buscando.delete()
        except Exception:
            pass
        if resultado["tipo"] == "playlist":
            musicas = resultado["musicas"]
            for m in musicas:
                fila.append(m)
            if not vc.is_playing() and not vc.is_paused():
                await tocar_proxima(guild, self.bot)
            else:
                await atualizar_embed_player(guild, guild_id=guild.id)
            await message.channel.send(member.mention + " ✅ Playlist com **" + str(len(musicas)) + " músicas** adicionada!", delete_after=8)
        else:
            if vc.is_playing() or vc.is_paused():
                fila.append(resultado)
                await atualizar_embed_player(guild, guild_id=guild.id)
                await message.channel.send(member.mention + " ✅ **" + resultado["titulo"] + "** na fila! (posição " + str(len(fila)) + ")", delete_after=8)
            else:
                fila.insert(0, resultado)
                await tocar_proxima(guild, self.bot)
                await message.channel.send(member.mention + " ▶️ Tocando **" + resultado["titulo"] + "**!", delete_after=8)


async def setup_player_embed(bot):
    canal_musica = bot.get_channel(config.MUSICA_CANAL_ID())
    if not canal_musica:
        print("⚠️ Canal de música não encontrado.")
        return

    # Limpar estado de reprodução (bot reiniciou, não está tocando nada)
    for guild in bot.guilds:
        filas.pop(guild.id, None)
        tocando_agora.pop(guild.id, None)

    # Procurar mensagem existente do player (pode ter embeds V1 ou components V2)
    msg_existente = None
    async for msg in canal_musica.history(limit=10):
        if msg.author == bot.user and (msg.embeds or msg.components):
            msg_existente = msg
            break

    if msg_existente:
        # Tentar editar a mensagem existente para o estado vazio V2
        editado = False
        try:
            arquivo = discord.File(config.PLAYER_IMAGE_PATH, filename="player.png")
            await msg_existente.edit(embed=None, view=PlayerLayoutVazio(), attachments=[arquivo])
            editado = True
        except Exception as e:
            print(f"⚠️ Erro ao editar embed de música (com arquivo): {e}")
            try:
                await msg_existente.edit(embed=None, view=PlayerLayoutVazio())
                editado = True
            except Exception as e2:
                print(f"⚠️ Erro ao editar embed de música (sem arquivo): {e2}")

        if not editado:
            # Fallback: deletar mensagem antiga e criar nova
            print("⚠️ Não foi possível editar, recriando mensagem do player...")
            try:
                await msg_existente.delete()
            except Exception:
                pass
            try:
                arquivo = discord.File(config.PLAYER_IMAGE_PATH, filename="player.png")
                msg_existente = await canal_musica.send(files=[arquivo], view=PlayerLayoutVazio())
            except Exception:
                msg_existente = await canal_musica.send(view=PlayerLayoutVazio())

        for guild in bot.guilds:
            mensagem_player[guild.id] = msg_existente
        print("✅ Embed de música atualizado.")
    else:
        try:
            arquivo = discord.File(config.PLAYER_IMAGE_PATH, filename="player.png")
            msg = await canal_musica.send(files=[arquivo], view=PlayerLayoutVazio())
        except Exception:
            msg = await canal_musica.send(view=PlayerLayoutVazio())
        for guild in bot.guilds:
            mensagem_player[guild.id] = msg
        print("✅ Embed de música criado!")


async def setup(bot):
    await bot.add_cog(MusicaCog(bot))