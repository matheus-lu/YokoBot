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
        blocos = data.get('blocos', [])
        reacoes = data.get('reacoes', [])
        
        if not canal_id or not blocos:
            return web.json_response({"status": "error", "message": "Canal e conteúdo são obrigatórios."}, status=400)
            
        canal = bot.get_channel(int(canal_id))
        if not canal:
            return web.json_response({"status": "error", "message": "Canal não encontrado no Discord do bot."}, status=404)
            
        fut = asyncio.get_running_loop().create_future()
        bot.dispatch('api_send_layout', canal, tipo, titulo, mensagem, imagem_url, blocos, reacoes, fut)
        
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
                    # Incluímos canais de texto, fórum, notícias, voz e palco
                    if str(channel.type) in ['text', 'forum', 'news', 'voice', 'stage_voice']:
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
                if channel.category_id is None and str(channel.type) in ['text', 'forum', 'news', 'voice', 'stage_voice']:
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
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def get_roles(request):
    bot = request.app['bot']
    try:
        data = []
        for guild in bot.guilds:
            for role in guild.roles:
                if role.name != "@everyone" and not role.managed:
                    data.append({
                        "id": str(role.id),
                        "name": role.name,
                        "color": str(role.color)
                    })
        # Sort roles alphabetically for better UX
        data.sort(key=lambda r: r['name'].lower())
        return web.json_response({"status": "success", "roles": data})
    except Exception as e:
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

async def bot_action(request):
    try:
        data = await request.json()
        action = data.get('action')
        bot = request.app['bot']
        
        if action == 'varredura_freegames':
            limite = int(data.get('limite', 50))
            canal = bot.get_channel(1507724879904903248)
            if not canal:
                return web.json_response({"status": "error", "message": "Canal freegames não encontrado!"}, status=400)
                
            emojis = [
                "<:_verificadoverde:1507463200642171142>",
                "<a:_pixellovegreen:1507139369188855878>",
                "<a:_sinosfloridos:1507143271263244299>",
                "<a:_brilha:1508358170844598272>"
            ]
            
            async def background_varredura():
                count = 0
                try:
                    async for msg in canal.history(limit=limite):
                        for emoji in emojis:
                            try:
                                await msg.add_reaction(emoji)
                            except Exception:
                                pass
                        count += 1
                        import asyncio
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Erro na varredura bg: {e}")
            
            import asyncio
            asyncio.create_task(background_varredura())
            return web.json_response({"status": "success", "message": f"A varredura foi iniciada em background para {limite} mensagens."})
            
        elif action == 'get_config':
            import config_dynamic
            return web.json_response({
                "status": "success",
                "data": config_dynamic.all_data()
            })
            
        elif action == 'save_config':
            import config_dynamic
            new_data = data.get('config', {})
            for k, v in new_data.items():
                config_dynamic.set(k, v)
            return web.json_response({"status": "success", "message": "Configurações salvas com sucesso!"})

        elif action == 'apagar_layout':
            msg_id = int(data.get('msg_id'))
            if not bot.db.db: await bot.db.connect()
            layout = await bot.db.get_layout(msg_id)
            if not layout:
                return web.json_response({"status": "error", "message": "Layout não encontrado no banco de dados."})
            canal_id = layout[1]
            canal = bot.get_channel(canal_id)
            if canal:
                try:
                    msg = await canal.fetch_message(msg_id)
                    await msg.delete()
                except Exception:
                    pass
            await bot.db.deletar_layout(msg_id)
            return web.json_response({"status": "success", "message": "Layout apagado do Discord e banco."})

        elif action == 'remandar_layout':
            msg_id = int(data.get('msg_id'))
            if not bot.db.db: await bot.db.connect()
            layout = await bot.db.get_layout(msg_id)
            if not layout:
                return web.json_response({"status": "error", "message": "Layout não encontrado no banco de dados."})
            
            # msg_id(0), canal_id(1), titulo(2), descricao(3), footer(4), estilo(5), reacoes(6), imagem_bytes(7), imagem_nome(8), tipo(9)
            canal_id = layout[1]
            titulo = layout[2]
            mensagem = layout[3]
            tipo = layout[9] or 'aviso'
            
            canal = bot.get_channel(canal_id)
            if not canal:
                return web.json_response({"status": "error", "message": "Canal de destino não encontrado no bot."})
            
            fut = asyncio.get_running_loop().create_future()
            # If imagem_bytes exist, we can't easily pass it via imagem_url.
            # But we can dispatch without it for now, or adapt main.py.
            # Wait, api_send_layout only accepts imagem_url, so if it's remandar, we could pass a special flag or just remandar without image for now, OR we can reconstruct the file.
            # Since remandar is just for testing/quick things, let's just dispatch without image for simplicity, or if we want to be exact we could modify `api_send_layout`.
            # To keep it simple: we send imagem_url as None.
            reacoes_remandar = []
            import json
            try:
                reacoes_remandar = json.loads(layout[6]) if layout[6] else []
            except: pass
            
            bot.dispatch('api_send_layout', canal, tipo, titulo, mensagem, None, [], reacoes_remandar, fut)
            novo_msg_id = await fut
            return web.json_response({"status": "success", "msg_id": novo_msg_id})

        return web.json_response({"status": "error", "message": "Ação desconhecida."}, status=400)
    except Exception as e:
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
    route_roles = app.router.add_get('/api/roles', get_roles)
    route_emojis = app.router.add_get('/api/emojis', get_emojis)
    
    # Rota de envio
    route_send = app.router.add_post('/api/send_layout', send_layout)
    route_action = app.router.add_post('/api/bot_action', bot_action)
    cors.add(route_index)
    cors.add(route_layouts)
    cors.add(route_channels)
    cors.add(route_roles)
    cors.add(route_emojis)
    cors.add(route_send)
    cors.add(route_action)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Square Cloud e outros hosts geralmente injetam a porta na variável de ambiente PORT
    porta = int(os.getenv("PORT", 8080))
    
    site = web.TCPSite(runner, '0.0.0.0', porta)
    await site.start()
    print(f"[API] 🌐 Servidor Web da API iniciado na porta {porta}")
