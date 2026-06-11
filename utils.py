# ============================================================
#  UTILITÁRIOS — Ondrakos Bot  水の竜
#  Geração de imagens temáticas, download de fonte, helpers.
# ============================================================

import math, random, io, os, requests
from PIL import Image, ImageDraw, ImageFont
import config


# ── Download das Fontes ────────────────────────────────────
def baixar_fonte():
    """Baixa todas as fontes configuradas que ainda não existem localmente."""
    fontes = [
        (getattr(config, "FONTE_TITULO_PATH", None), getattr(config, "FONTE_TITULO_URL", None)),
        (getattr(config, "FONTE_NOME_PATH",   None), getattr(config, "FONTE_NOME_URL",   None)),
    ]
    for path, url in fontes:
        if not path:
            continue
        if not os.path.exists(path) and url:
            print(f"Baixando fonte: {path}...")
            r = requests.get(url)
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"Fonte {path} baixada!")


def _carregar_fonte(path, size, fallback=None):
    """Carrega uma fonte TTF/OTF com fallback seguro."""
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        if fallback:
            try:
                return ImageFont.truetype(fallback, size)
            except Exception:
                pass
        return ImageFont.load_default()


# ── Cores do tema Ondrakos ──────────────────────────────
CRIMSON       = (163,  0, 12)
CRIMSON_DARK  = (122,  0,  9)
CRIMSON_LIGHT = (196, 18, 24)
INK           = ( 12, 10,  9)
INK_SOFT      = ( 42, 37, 32)
PAPER         = (244, 237, 224)
GOLD          = (200, 162, 94)


# ── Kanjis temáticos por evento ────────────────────────────
KANJIS_BOAS_VINDAS = ['歓', '迎', '入', '来', '新', '員', '仲', '間', '喜', '福']
KANJIS_ATE_LOGO    = ['別', '去', '離', '旅', '道', '再', '会', '縁', '感', '謝']
KANJIS_DECO        = ['新', '聞', '報', '道', '真', '実', '記', '事', '速', '報',
                      '取', '材', '情', '報', '日', '本', '東', '京', '戦', '士']


# ── Funções de Imagem ──────────────────────────────────────

def _desenhar_circulo_deco(draw, cx, cy, raio, rnd, cor_base=CRIMSON):
    r, g, b = cor_base
    draw.ellipse(
        [cx - raio, cy - raio, cx + raio, cy + raio],
        fill=None, outline=(r, g, b, 40), width=1
    )
    r2 = int(raio * 0.7)
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(r, g, b, 20))
    r3 = int(raio * 0.3)
    draw.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill=(r, g, b, 35))


def _desenhar_kanji_deco(draw, rnd, w, h, lista_kanjis=None, fonte_path=None, qtd=14):
    """
    Espalha kanjis decorativos sutis pelo fundo.
    lista_kanjis: lista de kanjis a usar (None = lista genérica)
    qtd: quantidade de kanjis
    """
    kanjis = lista_kanjis if lista_kanjis else KANJIS_DECO

    # Tamanhos variados para profundidade
    tamanhos = [22, 30, 40, 52]
    fontes_cache = {}
    path = fonte_path or getattr(config, "FONTE_TITULO_PATH", None)

    for _ in range(qtd):
        size = rnd.choice(tamanhos)
        if size not in fontes_cache:
            try:
                fontes_cache[size] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
            except Exception:
                fontes_cache[size] = ImageFont.load_default()

        x = rnd.randint(0, w - size - 10)
        y = rnd.randint(0, h - size - 10)
        kanji = rnd.choice(kanjis)
        alpha = rnd.randint(18, 45)
        draw.text((x, y), kanji, font=fontes_cache[size], fill=(163, 0, 12, alpha))


def gerar_fundo_japao(w=900, h=400, seed=None, kanjis=None):
    """Fundo temático Ondrakos."""
    rnd = random.Random(seed)

    img = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(img)

    # Gradiente escuro
    for y in range(h):
        t = y / h
        r = int(12 + t * 30)
        g = int(8  + t * 5)
        b = int(9  + t * 5)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Sol vermelho (hinomaru)
    sol_raio = 85
    sol_x = w // 2
    sol_y = int(h * 0.45)
    for i in range(sol_raio + 30, 0, -1):
        if i > sol_raio:
            alpha = int(40 * ((sol_raio + 30 - i) / 30))
        else:
            alpha = int(120 + 80 * (i / sol_raio))
        draw.ellipse([sol_x - i, sol_y - i, sol_x + i, sol_y + i], fill=(163, 0, 12, alpha))

    # Kanjis decorativos temáticos no fundo
    _desenhar_kanji_deco(draw, rnd, w, h, lista_kanjis=kanjis, qtd=16)

    # Círculos decorativos
    for _ in range(3):
        cx = rnd.randint(50, w - 50)
        cy = rnd.randint(30, h - 30)
        raio = rnd.randint(20, 45)
        _desenhar_circulo_deco(draw, cx, cy, raio, rnd)

    # Pontos sutis
    for px in range(0, w, 30):
        for py in range(0, h, 30):
            if rnd.random() > 0.7:
                draw.ellipse([px, py, px + 2, py + 2], fill=(163, 0, 12, rnd.randint(8, 20)))

    # Faixa lateral crimson
    faixa_x = rnd.choice([0, w - 6])
    draw.rectangle([faixa_x, 0, faixa_x + 6, h], fill=(163, 0, 12, 180))

    # Linhas horizontais sutis
    for _ in range(3):
        ly = rnd.randint(20, h - 20)
        draw.line([(30, ly), (w - 30, ly)], fill=(163, 0, 12, 15), width=1)

    overlay = Image.new("RGBA", (w, h), (12, 10, 9, 30))
    img = Image.alpha_composite(img, overlay)
    return img


def gerar_fundo_japao_escuro(w=900, h=400, seed=None, kanjis=None):
    """Fundo escuro para logs — estilo noturno do Ondrakos."""
    rnd = random.Random(seed)

    img = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / h
        r = int(8  + t * 18)
        g = int(5  + t * 8)
        b = int(6  + t * 8)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    cx, cy = int(w * 0.8), int(h * 0.3)
    for i in range(80, 0, -1):
        alpha = int(25 * (i / 80))
        draw.ellipse([cx - i * 2, cy - i * 2, cx + i * 2, cy + i * 2], fill=(163, 0, 12, alpha))

    _desenhar_kanji_deco(draw, rnd, w, h, lista_kanjis=kanjis, qtd=12)

    for _ in range(20):
        x = rnd.randint(0, w)
        y = rnd.randint(0, h)
        tamanho = rnd.randint(2, 6)
        draw.ellipse([x, y, x + tamanho, y + tamanho], fill=(163, 0, 12, rnd.randint(25, 60)))

    for px in range(0, w, 30):
        for py in range(0, h, 30):
            if rnd.random() > 0.85:
                draw.ellipse([px, py, px + 2, py + 2], fill=(163, 0, 12, rnd.randint(10, 25)))

    draw.rectangle([0, 0, w, 3], fill=(163, 0, 12, 150))

    overlay = Image.new("RGBA", (w, h), (12, 10, 9, 25))
    img = Image.alpha_composite(img, overlay)
    return img


def avatar_circular(avatar_bytes, size=160):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    av.putalpha(mask)
    return av


def _texto_centralizado(draw, y, texto, fonte, cor, W, sombra=True):
    """Desenha texto centralizado horizontalmente com sombra opcional."""
    tw = draw.textlength(texto, font=fonte)
    tx = (W - tw) // 2
    if sombra:
        draw.text((tx + 2, y + 2), texto, font=fonte, fill=(0, 0, 0, 180))
    draw.text((tx, y), texto, font=fonte, fill=cor)
    return tw


def _colar_logo(img, y, W, altura=50):
    """
    Cola a marca d'água (DORORO NEWS) centralizada na imagem.
    O arquivo é configurado em config.LOGO_PATH.
    """
    logo_path = getattr(config, "LOGO_PATH", None)
    if not logo_path or not os.path.exists(logo_path):
        return  # sem logo, não faz nada

    logo = Image.open(logo_path).convert("RGBA")

    # Redimensiona mantendo proporção pela altura desejada
    ratio = altura / logo.height
    nova_w = int(logo.width * ratio)
    logo = logo.resize((nova_w, altura), Image.LANCZOS)

    x = (W - nova_w) // 2
    img.paste(logo, (x, y), logo)


def _normalizar_nome(texto):
    """Converte caracteres Unicode especiais (smallcaps, etc) para ASCII legível."""
    import unicodedata
    mapa = {
        'ᴀ':'A','ʙ':'B','ᴄ':'C','ᴅ':'D','ᴇ':'E','ꜰ':'F','ɢ':'G','ʜ':'H',
        'ɪ':'I','ᴊ':'J','ᴋ':'K','ʟ':'L','ᴍ':'M','ɴ':'N','ᴏ':'O','ᴘ':'P',
        'ǫ':'Q','ʀ':'R','ꜱ':'S','ᴛ':'T','ᴜ':'U','ᴠ':'V','ᴡ':'W',
        'ʏ':'Y','ᴢ':'Z','ᴬ':'A','ᴮ':'B','ᶜ':'C','ᴰ':'D','ᴱ':'E','ᶠ':'F',
        'ᴳ':'G','ᴴ':'H','ᴵ':'I','ᴶ':'J','ᴷ':'K','ᴸ':'L','ᴹ':'M','ᴺ':'N',
        'ᴼ':'O','ᴾ':'P','ᴿ':'R','ˢ':'S','ᵀ':'T','ᵁ':'U','ᵂ':'W',
        '₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
        '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9',
    }
    resultado = ""
    for ch in texto:
        if ch in mapa:
            resultado += mapa[ch]
        else:
            norm = unicodedata.normalize('NFKD', ch)
            ascii_ch = norm.encode('ascii', 'ignore').decode('ascii')
            resultado += ascii_ch if ascii_ch else ch
    return resultado

def gerar_imagem_boas_vindas(username, avatar_bytes, entrou=True):
    W, H = 900, 400
    FONTE_TWILIGHT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twilight_New_Moon.ttf")

    # ── Fundo aleatório ────────────────────────────────────
    import glob, random as _rnd
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Aceita fundo_boas_vindas.png, fundo_boas_vindas_2.png, fundo_boas_vindas_3.png ...
    fundos = sorted(glob.glob(os.path.join(base_dir, "fundo_boas_vindas*.png")))
    if fundos:
        fundo_path = _rnd.choice(fundos)
        img = Image.open(fundo_path).convert("RGBA").resize((W, H), Image.LANCZOS)
    else:
        img = Image.new("RGBA", (W, H), (10, 8, 20))
    draw = ImageDraw.Draw(img)

    # ── Avatar centralizado com borda circular ─────────────
    av_size = 160
    border  = 6
    av = avatar_circular(avatar_bytes, av_size)
    border_img = Image.new("RGBA", (av_size + border * 2, av_size + border * 2), (0, 0, 0, 0))
    ImageDraw.Draw(border_img).ellipse(
        [0, 0, av_size + border * 2, av_size + border * 2],
        fill=(31, 139, 76, 220)
    )
    border_img.paste(av, (border, border), av)
    av_x = (W - (av_size + border * 2)) // 2
    av_y = 28
    img.paste(border_img, (av_x, av_y), border_img)

    # ── Textos ─────────────────────────────────────────────
    fonte_titulo = _carregar_fonte(FONTE_TWILIGHT, 72)
    fonte_nome   = _carregar_fonte(FONTE_TWILIGHT, 48)

    titulo = "Boas-vindas" if entrou else "Adeus"
    ty = av_y + av_size + border * 2 + 8
    _texto_centralizado(draw, ty, titulo, fonte_titulo, (255, 255, 255), W)

    ny = ty + 80
    _texto_centralizado(draw, ny, _normalizar_nome(username), fonte_nome, (31, 200, 100), W)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


def gerar_imagem_log_delete(username, avatar_bytes, conteudo, user_id, guild_id, canal_id, msg_id, timestamp, deletado_por=None):
    W, H = 900, 420
    FONTE_TWILIGHT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twilight_New_Moon.ttf")

    # Fundo aleatório
    import glob, random as _rnd
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fundos = sorted(glob.glob(os.path.join(base_dir, "fundo_log*.png")))
    if fundos:
        img = Image.open(_rnd.choice(fundos)).convert("RGBA").resize((W, H), Image.LANCZOS)
    else:
        img = Image.new("RGBA", (W, H), (10, 8, 20))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    fonte_nome = _carregar_fonte(FONTE_TWILIGHT, 32)
    fonte_msg  = _carregar_fonte(FONTE_TWILIGHT, 26)
    fonte_info = _carregar_fonte(FONTE_TWILIGHT, 22)
    fonte_id   = _carregar_fonte(FONTE_TWILIGHT, 20)
    PAD = 30

    # Avatar circular
    av_size, border = 80, 3
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size))
        mask = Image.new("L", (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, av_size, av_size], fill=255)
        av.putalpha(mask)
        bi = Image.new("RGBA", (av_size+border*2, av_size+border*2), (0,0,0,0))
        ImageDraw.Draw(bi).ellipse([0,0,av_size+border*2,av_size+border*2], fill=(31,139,76,200))
        bi.paste(av, (border, border), av)
        img.paste(bi, (PAD, PAD), bi)
    except Exception:
        pass
    draw = ImageDraw.Draw(img)

    # Nome ao lado do avatar
    draw.text((PAD + av_size + border*2 + 14, PAD + 10), username, font=fonte_nome, fill=(255, 255, 255))

    # Data/hora — align right
    try:
        ts_w = draw.textbbox((0,0), timestamp, font=fonte_info)[2]
    except Exception:
        ts_w = len(timestamp) * 12
    draw.text((W - PAD - ts_w, PAD + 14), timestamp, font=fonte_info, fill=(180, 180, 180))

    # Separador 1
    sep_y = PAD + av_size + border*2 + 12
    draw.line([(PAD, sep_y), (W-PAD, sep_y)], fill=(31,139,76,140), width=1)

    # Mensagem — quebra por palavra
    conteudo_display = conteudo if conteudo else "*sem conteúdo de texto*"
    palavras = conteudo_display.split(" ")
    linhas, linha_atual = [], ""
    for palavra in palavras:
        teste = (linha_atual + " " + palavra).strip()
        try:
            larg = draw.textbbox((0,0), teste, font=fonte_msg)[2]
        except Exception:
            larg = len(teste) * 15
        if larg <= W - PAD*2:
            linha_atual = teste
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = palavra
        if len(linhas) >= 5:
            break
    if linha_atual and len(linhas) < 5:
        linhas.append(linha_atual)
    if not linhas:
        linhas = [conteudo_display[:90]]

    msg_y = sep_y + 14
    for idx, linha in enumerate(linhas):
        draw.text((PAD, msg_y + idx * 32), linha, font=fonte_msg, fill=(240, 235, 220))

    # Separador 2
    sep2_y = msg_y + len(linhas) * 32 + 14
    draw.line([(PAD, sep2_y), (W-PAD, sep2_y)], fill=(31,139,76,140), width=1)

    # ID da mensagem — centralizado
    id_texto = "ID da mensagem: " + str(msg_id)
    try:
        id_w = draw.textbbox((0,0), id_texto, font=fonte_id)[2]
    except Exception:
        id_w = len(id_texto) * 11
    draw.text(((W - id_w)//2, sep2_y + 10), id_texto, font=fonte_id, fill=(150, 150, 150))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf