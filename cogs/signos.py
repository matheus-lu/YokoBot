# ============================================================
#  COG: SIGNOS — Juunishi 星座 — Ondrakos Bot
# ============================================================

import discord
from discord.ext import commands

SIGNOS_CANAL_ID = 1484492959624728687

SIGNOS = [
    {"emoji_str": "<:Ba_rato:1508280970028253406>",      "emoji_id": 1508280970028253406, "emoji_name": "Ba_rato",      "cargo_id": 1507659962132725830},
    {"emoji_str": "<:Bb_boi:1508281115704561664>",       "emoji_id": 1508281115704561664, "emoji_name": "Bb_boi",       "cargo_id": 1507660054969581629},
    {"emoji_str": "<:Bc_tigre:1508281235577770026>",     "emoji_id": 1508281235577770026, "emoji_name": "Bc_tigre",     "cargo_id": 1507660149068922941},
    {"emoji_str": "<:Bd_coelho:1508281357531484260>",    "emoji_id": 1508281357531484260, "emoji_name": "Bd_coelho",    "cargo_id": 1507660253716680804},
    {"emoji_str": "<:Be_dragao:1508281453249560726>",    "emoji_id": 1508281453249560726, "emoji_name": "Be_dragao",    "cargo_id": 1507660358658293901},
    {"emoji_str": "<:Bf_cobra:1508281550561869935>",     "emoji_id": 1508281550561869935, "emoji_name": "Bf_cobra",     "cargo_id": 1507660477977592009},
    {"emoji_str": "<:Bg_cavalo:1508281655641505853>",    "emoji_id": 1508281655641505853, "emoji_name": "Bg_cavalo",    "cargo_id": 1507660584492072971},
    {"emoji_str": "<:Bh_ovelha:1508281755273134110>",    "emoji_id": 1508281755273134110, "emoji_name": "Bh_ovelha",    "cargo_id": 1507660676410376312},
    {"emoji_str": "<:Bi_macaco:1508281832217772253>",    "emoji_id": 1508281832217772253, "emoji_name": "Bi_macaco",    "cargo_id": 1507660808014925914},
    {"emoji_str": "<:Bj_galo:1508281914291654727>",      "emoji_id": 1508281914291654727, "emoji_name": "Bj_galo",      "cargo_id": 1507660899945545778},
    {"emoji_str": "<:Bk_cachorro:1508281995883712713>",  "emoji_id": 1508281995883712713, "emoji_name": "Bk_cachorro",  "cargo_id": 1507660983143759902},
    {"emoji_str": "<:Bl_javali:1508282135004319864>",    "emoji_id": 1508282135004319864, "emoji_name": "Bl_javali",    "cargo_id": 1507661072281370725},
]

TODOS_CARGOS_IDS = {s["cargo_id"] for s in SIGNOS}

EMBED_DESC = """No calendário dos signos japoneses, cada pessoa pertence a um animal de acordo com o ano em que nasceu.

Confira abaixo qual é o seu signo e clique no emoji correspondente para receber o cargo no servidor.

Exemplo: se você nasceu em 2000, seu signo é Dragão.
Então clique no emoji do Dragão para ganhar o cargo.

<:Ba_rato:1508280970028253406>↪**Rato — 子 / Ne**
›Anos: 1996, 2008, 2020, 2032↩

<:Bb_boi:1508281115704561664>↪**Boi — 丑 / Ushi**
›Anos: 1997, 2009, 2021, 2033↩

<:Bc_tigre:1508281235577770026>↪**Tigre — 寅 / Tora**
›Anos: 1998, 2010, 2022, 2034↩

<:Bd_coelho:1508281357531484260>↪**Coelho — 卯 / U**
›Anos: 1999, 2011, 2023, 2035↩

<:Be_dragao:1508281453249560726>↪**Dragão — 辰 / Tatsu**
›Anos: 2000, 2012, 2024, 2036↩

<:Bf_cobra:1508281550561869935>↪**Cobra — 巳 / Mi**
›Anos: 2001, 2013, 2025, 2037↩

<:Bg_cavalo:1508281655641505853>↪**Cavalo — 午 / Uma**
›Anos: 2002, 2014, 2026, 2038↩

<:Bh_ovelha:1508281755273134110>↪**Ovelha — 未 / Hitsuji**
›Anos: 2003, 2015, 2027, 2039↩

<:Bi_macaco:1508281832217772253>↪**Macaco — 申 / Saru**
›Anos: 2004, 2016, 2028, 2040↩

<:Bj_galo:1508281914291654727>↪**Galo — 酉 / Tori**
›Anos: 2005, 2017, 2029, 2041↩

<:Bk_cachorro:1508281995883712713>↪**Cachorro — 戌 / Inu**
›Anos: 2006, 2018, 2030, 2042↩

<:Bl_javali:1508282135004319864>↪**Javali — 亥 / I**
›Anos: 2007, 2019, 2031, 2043↩

*Clique no emoji do seu signo para liberar o cargo correspondente.*"""

# ID da mensagem do embed — salvo em memória, persiste enquanto bot roda
_mensagem_signos_id = None


SIGNOS_IMAGE_PATH = "signos.png"

def _build_embed():
    embed = discord.Embed(
        title="🐉 Escolha seu Signo Japonês 🍀│▸juunishi",
        description=EMBED_DESC,
        color=discord.Color.from_rgb(31, 139, 76),
    )
    embed.set_footer(text="十二支 — Juunishi 星座")
    return embed


class SignosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    async def _garantir_reacoes(self, msg):
        reacoes_existentes = {r.emoji.id if hasattr(r.emoji, 'id') else None for r in msg.reactions}
        for s in SIGNOS:
            if s["emoji_id"] not in reacoes_existentes:
                emoji = self.bot.get_emoji(s["emoji_id"])
                if emoji:
                    await msg.add_reaction(emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != SIGNOS_CANAL_ID:
            return
        if payload.message_id != _mensagem_signos_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        emoji = payload.emoji
        signo = next((s for s in SIGNOS if s["emoji_id"] == emoji.id), None)
        if not signo:
            # Remover reação não reconhecida
            canal = self.bot.get_channel(payload.channel_id)
            if canal:
                msg = await canal.fetch_message(payload.message_id)
                await msg.remove_reaction(emoji, member)
            return

        cargo_novo = guild.get_role(signo["cargo_id"])
        if not cargo_novo:
            return

        # Remover cargos de outros signos
        cargos_remover = [r for r in member.roles if r.id in TODOS_CARGOS_IDS and r.id != signo["cargo_id"]]
        if cargos_remover:
            await member.remove_roles(*cargos_remover, reason="Troca de signo")

        # Adicionar novo cargo
        if cargo_novo not in member.roles:
            await member.add_roles(cargo_novo, reason="Signo escolhido")

        # Remover a reação do usuário para manter o embed limpo
        canal = self.bot.get_channel(payload.channel_id)
        if canal:
            try:
                msg = await canal.fetch_message(payload.message_id)
                await msg.remove_reaction(emoji, member)
            except Exception:
                pass

        try:
            await member.send(
                f"✅ Seu signo foi definido como **{signo['emoji_str']}** no servidor **{guild.name}**!"
            )
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        # Ignorar — o cargo só é removido ao escolher outro
        pass


async def setup_signos_embed(bot):
    global _mensagem_signos_id
    canal = bot.get_channel(SIGNOS_CANAL_ID)
    if not canal:
        print(f"SIGNOS: ⚠️ Canal {SIGNOS_CANAL_ID} nao encontrado.")
        return
    msg_existente = None
    async for msg in canal.history(limit=20):
        if msg.author == bot.user and msg.embeds:
            if "juunishi" in msg.embeds[0].title.lower() or "signo" in msg.embeds[0].title.lower():
                msg_existente = msg
                break
    if msg_existente:
        _mensagem_signos_id = msg_existente.id
        cog = bot.cogs.get("SignosCog")
        if cog:
            await cog._garantir_reacoes(msg_existente)
        print("✅ Embed de signos ja existe, mantendo.")
    else:
        import os as _os
        _img = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", SIGNOS_IMAGE_PATH))
        if _os.path.exists(_img) and _os.path.getsize(_img) < 9_000_000:
            _arquivo = discord.File(_img, filename="signos.png")
            _embed = _build_embed()
            _embed.set_image(url="attachment://signos.png")
            msg = await canal.send(file=_arquivo, embed=_embed)
        else:
            msg = await canal.send(embed=_build_embed())
        _mensagem_signos_id = msg.id
        for s in SIGNOS:
            emoji = bot.get_emoji(s["emoji_id"])
            if emoji:
                await msg.add_reaction(emoji)
        print("✅ Embed de signos criado!")


async def setup(bot):
    await bot.add_cog(SignosCog(bot))