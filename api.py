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
    
    # Rota de envio com preflight manual CORS para métodos POST se o aiohttp_cors não pegar automaticamente
    route_send = app.router.add_post('/api/send_layout', send_layout)
    route_send_options = app.router.add_options('/api/send_layout', lambda r: web.Response(headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'}))
    
    cors.add(route_index)
    cors.add(route_layouts)
    cors.add(route_send)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Square Cloud e outros hosts geralmente injetam a porta na variável de ambiente PORT
    porta = int(os.getenv("PORT", 8080))
    
    site = web.TCPSite(runner, '0.0.0.0', porta)
    await site.start()
    print(f"[API] 🌐 Servidor Web da API iniciado na porta {porta}")
