"""
config_dynamic.py — Configuracoes dinamicas do Ondrakos Bot
Carregadas de dynamic.json, editaveis via /setup
"""
import json, os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dynamic.json")

_DEFAULTS = {
    # Canais
    "BOAS_VINDAS_CANAL_ID":   0,
    "SAIDA_CANAL_ID":         0,
    "LOGS_CANAL_ID":          0,
    "MUSICA_CANAL_ID":        0,
    "DIVULGACAO_CANAL_ID":    0,
    "TICKET_CANAL_ID":        0,
    "TICKET_CATEGORY_ID":     0,
    "TICKET_CLOSED_CATEGORY_ID": 0,
    "IA_CANAL_ID":            0,
    "IA_CATEGORIA_ID":        0,
    "PUNICOES_CANAL_ID":      0,
    "CONTADOR_CANAL_ID":      0,
    # Cargos
    "STAFF_ROLE_ID":          0,
    "STAFF_MENTION_ROLE_ID":  0,
    "IA_PROPRIETARIO_ID":     0,
    "IA_DEV_ID":              0,
    # Misc
    "PLAYER_IMAGE_PATH":      "player.png",
    "IMAGEM_URL":             "",
    "SITE_URL":               "",
}

_data = {}

def _load():
    global _data
    if os.path.exists(_PATH):
        with open(_PATH, "r", encoding="utf-8") as f:
            _data = json.load(f)
    else:
        _data = dict(_DEFAULTS)

def save():
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2, ensure_ascii=False)

def get(key, default=None):
    if not _data:
        _load()
    return _data.get(key, _DEFAULTS.get(key, default))

def set(key, value):
    if not _data:
        _load()
    _data[key] = value
    save()

def all_data():
    if not _data:
        _load()
    return dict(_data)

# Carregar ao importar
_load()
