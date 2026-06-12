import os
import base64
from aiohttp import web

# ── Rota para pegar os anúncios/postagens ──
async def get_layouts(request):
    bot = request.app['bot']
    try:
        if not bot.db.db:
            await bot.db.connect()
        
        cursor = await bot.db.db.execute("SELECT * FROM mensagens_layout ORDER BY msg_id DESC")
        rows = await cursor.fetchall()
        
        # O aiosqlite geralmente usa tuples ou Row objects. Vamos mapear para dict:
        columns = [description[0] for description in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        
        # Tratamento especial para as imagens BLOB
        for item in data:
            if item.get("imagem_bytes"):
                # Transforma o binário em Base64 para o site poder exibir numa tag <img src="data:image/png;base64,...">
                item["imagem_base64"] = base64.b64encode(item["imagem_bytes"]).decode('utf-8')
            
            # Removemos o binário cru para o JSON não quebrar
            if "imagem_bytes" in item:
                del item["imagem_bytes"]
                
        return web.json_response({"status": "success", "total": len(data), "data": data})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

import asyncio

async def send_layout(request):
    bot = request.app['bot']
    try:
        data = await request.json()
        
        canal_id = data.get('canal_id')
        tipo = data.get('tipo', 'aviso')
        titulo = data.get('titulo', '')
        mensagem = data.get('mensagem', '')
        imagem_url = data.get('imagem_url', '')
        
        if not canal_id or not titulo or not mensagem:
            return web.json_response({"status": "error", "message": "Canal, título e mensagem são obrigatórios."}, status=400)
            
        canal = bot.get_channel(int(canal_id))
        if not canal:
            return web.json_response({"status": "error", "message": "Canal não encontrado no Discord do bot."}, status=404)
            
        fut = asyncio.get_running_loop().create_future()
        bot.dispatch('api_send_layout', canal, tipo, titulo, mensagem, imagem_url, fut)
        
        # Wait for main.py to process it
        msg_id = await fut
        
        return web.json_response({"status": "success", "msg_id": msg_id})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def get_channels(request):
    bot = request.app['bot']
    try:
        data = []
        for guild in bot.guilds:
            # Pegamos categorias e canais sem categoria
            for category in guild.categories:
                cat_data = {
                    "id": str(category.id),
                    "name": category.name,
                    "channels": []
                }
                for channel in category.channels:
                    # Incluímos canais de texto e de fórum
                    if str(channel.type) in ['text', 'forum', 'news']:
                        chan_data = {
                            "id": str(channel.id),
                            "name": channel.name,
                            "type": str(channel.type),
                            "topics": []
                        }
                        
                        # Se for fórum, pega as threads ativas
                        if str(channel.type) == 'forum':
                            for thread in channel.threads:
                                chan_data["topics"].append({
                                    "id": str(thread.id),
                                    "name": thread.name
                                })
                                
                        cat_data["channels"].append(chan_data)
                
                if cat_data["channels"]:
                    data.append(cat_data)
            
            # Para canais que não estão em nenhuma categoria
            none_cat = {"id": "none", "name": "Sem Categoria", "channels": []}
            for channel in guild.channels:
                if channel.category_id is None and str(channel.type) in ['text', 'forum', 'news']:
                    chan_data = {
                        "id": str(channel.id),
                        "name": channel.name,
                        "type": str(channel.type),
                        "topics": []
                    }
                    if str(channel.type) == 'forum':
                        for thread in channel.threads:
                            chan_data["topics"].append({
                                "id": str(thread.id),
                                "name": thread.name
                            })
                    none_cat["channels"].append(chan_data)
            if none_cat["channels"]:
                data.append(none_cat)

        return web.json_response({"status": "success", "categories": data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def get_emojis(request):
    bot = request.app['bot']
    try:
        emojis_data = []
        for guild in bot.guilds:
            for emoji in guild.emojis:
                emojis_data.append({
                    "id": str(emoji.id),
                    "name": emoji.name,
                    "url": str(emoji.url),
                    "animated": emoji.animated
                })
        return web.json_response({"status": "success", "emojis": emojis_data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ── Rota raiz simples para teste ──
async def index(request):
    return web.Response(text="API do Ondrakos V2 está online! 🐉")

# ── Inicialização do Servidor ──
async def start_server(bot):
    app = web.Application()
    app['bot'] = bot
    
    # Adicionando a política de CORS para o site conseguir acessar a API sem ser bloqueado
    import aiohttp_cors
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    # Registrando rotas
    route_index = app.router.add_get('/', index)
    route_layouts = app.router.add_get('/api/layouts', get_layouts)
    route_channels = app.router.add_get('/api/channels', get_channels)
    route_emojis = app.router.add_get('/api/emojis', get_emojis)
    
    # Rota de envio
    route_send = app.router.add_post('/api/send_layout', send_layout)
    cors.add(route_index)
    cors.add(route_layouts)
    cors.add(route_channels)
    cors.add(route_emojis)
    cors.add(route_send)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Square Cloud e outros hosts geralmente injetam a porta na variável de ambiente PORT
    porta = int(os.getenv("PORT", 8080))
    
    site = web.TCPSite(runner, '0.0.0.0', porta)
    await site.start()
    print(f"[API] 🌐 Servidor Web da API iniciado na porta {porta}")
