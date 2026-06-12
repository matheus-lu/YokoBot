# ============================================================
#  BANCO DE DADOS — SQLite — Ondrakos
#  Gerencia criação de tabelas e operações do banco.
# ============================================================

import aiosqlite
import config


class Database:
    """Gerenciador assíncrono do banco SQLite."""

    def __init__(self, path: str = None):
        self.path = path or config.DB_PATH
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        """Conecta ao banco e cria as tabelas se não existirem."""
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self._criar_tabelas()
        await self._migrations()
        print(f"✅ Banco de dados conectado: {self.path}")

    async def close(self):
        if self.db:
            await self.db.close()

    async def _migrations(self):
        """Adiciona colunas novas sem quebrar banco existente."""
        migracoes = [
            ("xp",      "tempo_voz",  "INTEGER DEFAULT 0"),
            ("tickets", "avaliacao",  "INTEGER"),
            # Colunas de imagem para lembretes criados antes dessa versão
            ("calendario_lembretes", "imagem",       "BLOB"),
            ("calendario_lembretes", "imagem_nome",  "TEXT"),
            ("mensagens_layout", "reacoes", "TEXT"),
            ("mensagens_layout", "imagem_bytes", "BLOB"),
            ("mensagens_layout", "imagem_nome", "TEXT"),
            ("mensagens_layout", "tipo", "TEXT"),
        ]
        for tabela, coluna, tipo in migracoes:
            try:
                await self.db.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
                await self.db.commit()
                print(f"✅ Migration: coluna {coluna} adicionada em {tabela}")
            except Exception:
                pass  # Coluna ja existe

    # ── Criação de Tabelas ─────────────────────────────────
    async def _criar_tabelas(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                categoria   TEXT NOT NULL,
                descricao   TEXT,
                status      TEXT DEFAULT 'aberto',
                staff_id    INTEGER,
                criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fechado_em  TIMESTAMP,
                avaliacao   INTEGER
            );

            CREATE TABLE IF NOT EXISTS xp (
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                xp          INTEGER DEFAULT 0,
                level       INTEGER DEFAULT 0,
                mensagens   INTEGER DEFAULT 0,
                tempo_voz   INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS economia (
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                saldo       INTEGER DEFAULT 0,
                banco       INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS config_guild (
                guild_id    INTEGER PRIMARY KEY,
                prefixo     TEXT DEFAULT '!',
                dados_json  TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS anuncio_presencas (
                mensagem_id INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                user_nome   TEXT NOT NULL,
                status      TEXT NOT NULL,
                PRIMARY KEY (mensagem_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS calendario_lembretes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                nome            TEXT NOT NULL,
                data_iso        TEXT NOT NULL,
                horario         TEXT NOT NULL,
                mensagem        TEXT NOT NULL,
                canal_id        INTEGER NOT NULL,
                anual           INTEGER DEFAULT 0,
                notificado_ano  INTEGER DEFAULT 0,
                imagem          BLOB,
                imagem_nome     TEXT
            );
            CREATE TABLE IF NOT EXISTS mensagens_layout (
                msg_id      INTEGER PRIMARY KEY,
                canal_id    INTEGER NOT NULL,
                titulo      TEXT,
                descricao   TEXT,
                footer      TEXT,
                estilo      TEXT DEFAULT 'padrao',
                reacoes     TEXT,
                imagem_bytes BLOB,
                imagem_nome  TEXT,
                tipo         TEXT DEFAULT 'anuncio'
            );
        """)
        await self.db.commit()

    # ── Tickets ────────────────────────────────────────────
    async def criar_ticket(self, guild_id: int, channel_id: int, user_id: int,
                           categoria: str, descricao: str) -> int:
        cursor = await self.db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, categoria, descricao) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, channel_id, user_id, categoria, descricao)
        )
        await self.db.commit()
        return cursor.lastrowid

    async def fechar_ticket(self, channel_id: int, staff_id: int = None):
        await self.db.execute(
            "UPDATE tickets SET status='fechado', fechado_em=CURRENT_TIMESTAMP, "
            "staff_id=COALESCE(?, staff_id) WHERE channel_id=? AND status='aberto'",
            (staff_id, channel_id)
        )
        await self.db.commit()

    async def reabrir_ticket(self, channel_id: int):
        await self.db.execute(
            "UPDATE tickets SET status='aberto', fechado_em=NULL WHERE channel_id=?",
            (channel_id,)
        )
        await self.db.commit()

    async def get_ticket(self, channel_id: int):
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE channel_id=? ORDER BY id DESC LIMIT 1",
            (channel_id,)
        )
        return await cursor.fetchone()

    async def salvar_avaliacao_ticket(self, channel_id: int, nota: int):
        """Salva a nota de avaliação (1-5) de um ticket pelo channel_id."""
        await self.db.execute(
            "UPDATE tickets SET avaliacao=? WHERE channel_id=?",
            (nota, channel_id)
        )
        await self.db.commit()

    async def contar_tickets(self, guild_id: int, status: str = None) -> int:
        if status:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id=? AND status=?",
                (guild_id, status)
            )
        else:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id=?",
                (guild_id,)
            )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ── XP ──────────────────────────────────────────────────
    async def registrar_membro(self, user_id: int, guild_id: int):
        """Registra um membro com 0 XP se não existir ainda."""
        row = await self.get_xp(user_id, guild_id)
        if row is None:
            await self.db.execute(
                "INSERT INTO xp (user_id, guild_id, xp, level, mensagens) "
                "VALUES (?, ?, 0, 0, 0)",
                (user_id, guild_id)
            )
            await self.db.commit()

    async def registrar_membros_em_massa(self, membros: list, guild_id: int):
        """Registra vários membros de uma vez (ignora os que já existem)."""
        for uid in membros:
            await self.db.execute(
                "INSERT OR IGNORE INTO xp (user_id, guild_id, xp, level, mensagens) "
                "VALUES (?, ?, 0, 0, 0)",
                (uid, guild_id)
            )
        await self.db.commit()

    async def limpar_membros_saiu(self, membros_atuais: list, guild_id: int) -> int:
        """Remove do XP quem não está mais no servidor. Retorna quantos removeu."""
        cursor = await self.db.execute(
            "SELECT user_id FROM xp WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        membros_set = set(membros_atuais)
        removidos = 0
        for row in rows:
            if row["user_id"] not in membros_set:
                await self.db.execute(
                    "DELETE FROM xp WHERE user_id=? AND guild_id=?",
                    (row["user_id"], guild_id)
                )
                removidos += 1
        if removidos > 0:
            await self.db.commit()
        return removidos

    async def remover_membro_xp(self, user_id: int, guild_id: int):
        """Remove um membro específico do XP."""
        await self.db.execute(
            "DELETE FROM xp WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        await self.db.commit()

    async def get_xp(self, user_id: int, guild_id: int):
        cursor = await self.db.execute(
            "SELECT * FROM xp WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        return await cursor.fetchone()

    async def add_xp(self, user_id: int, guild_id: int, quantidade: int) -> dict:
        """Adiciona XP e retorna {'xp': ..., 'level': ..., 'subiu': bool}."""
        row = await self.get_xp(user_id, guild_id)
        if row is None:
            await self.db.execute(
                "INSERT INTO xp (user_id, guild_id, xp, level, mensagens) "
                "VALUES (?, ?, ?, 0, 1)",
                (user_id, guild_id, quantidade)
            )
            await self.db.commit()
            return {"xp": quantidade, "level": 0, "subiu": False}

        novo_xp = row["xp"] + quantidade
        mensagens = row["mensagens"] + 1
        level_atual = row["level"]
        xp_proximo = 100 * (level_atual + 1) ** 2
        subiu = novo_xp >= xp_proximo
        novo_level = level_atual + 1 if subiu else level_atual

        await self.db.execute(
            "UPDATE xp SET xp=?, level=?, mensagens=? WHERE user_id=? AND guild_id=?",
            (novo_xp, novo_level, mensagens, user_id, guild_id)
        )
        await self.db.commit()
        return {"xp": novo_xp, "level": novo_level, "subiu": subiu}

    async def ranking_xp(self, guild_id: int, limite: int = 10):
        cursor = await self.db.execute(
            "SELECT * FROM xp WHERE guild_id=? ORDER BY xp DESC LIMIT ?",
            (guild_id, limite)
        )
        return await cursor.fetchall()

    async def add_tempo_voz(self, user_id: int, guild_id: int, segundos: int):
        """Adiciona segundos ao tempo total em voz do usuário."""
        await self.db.execute(
            "INSERT INTO xp (user_id, guild_id, tempo_voz) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, guild_id) DO UPDATE SET tempo_voz = tempo_voz + ?",
            (user_id, guild_id, segundos, segundos)
        )
        await self.db.commit()

    async def total_membros_xp(self, guild_id: int) -> int:
        """Retorna o total de membros registrados no XP."""
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM xp WHERE guild_id=?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def posicao_usuario(self, user_id: int, guild_id: int) -> dict | None:
        """Retorna a posição, xp e level de um usuário no ranking."""
        cursor = await self.db.execute(
            "SELECT user_id, xp, level FROM xp WHERE guild_id=? ORDER BY xp DESC",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        for i, row in enumerate(rows):
            if row["user_id"] == user_id:
                return {"posicao": i + 1, "xp": row["xp"], "level": row["level"]}
        return None

    # ── Economia (preparado para a Fase 2) ─────────────────
    async def get_saldo(self, user_id: int, guild_id: int):
        cursor = await self.db.execute(
            "SELECT * FROM economia WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()
        if row is None:
            await self.db.execute(
                "INSERT INTO economia (user_id, guild_id) VALUES (?, ?)",
                (user_id, guild_id)
            )
            await self.db.commit()
            return {"saldo": 0, "banco": 0}
        return {"saldo": row["saldo"], "banco": row["banco"]}

    async def add_saldo(self, user_id: int, guild_id: int, quantidade: int):
        await self.get_saldo(user_id, guild_id)  # garante que existe
        await self.db.execute(
            "UPDATE economia SET saldo = saldo + ? WHERE user_id=? AND guild_id=?",
            (quantidade, user_id, guild_id)
        )
        await self.db.commit()

    # ── Presenças de Anúncios ──────────────────────────────
    async def registrar_presenca(self, mensagem_id: int, user_id: int, user_nome: str, status: str):
        """Registra ou atualiza presença. status: 'confirmado' ou 'ausente'."""
        await self.db.execute(
            "INSERT INTO anuncio_presencas (mensagem_id, user_id, user_nome, status) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(mensagem_id, user_id) DO UPDATE SET status=?, user_nome=?",
            (mensagem_id, user_id, user_nome, status, status, user_nome)
        )
        await self.db.commit()

    async def get_presencas(self, mensagem_id: int) -> dict:
        """Retorna {'confirmados': {uid: nome}, 'ausentes': {uid: nome}}."""
        cursor = await self.db.execute(
            "SELECT user_id, user_nome, status FROM anuncio_presencas WHERE mensagem_id=?",
            (mensagem_id,)
        )
        rows = await cursor.fetchall()
        resultado = {"confirmados": {}, "ausentes": {}}
        for row in rows:
            if row["status"] == "confirmado":
                resultado["confirmados"][row["user_id"]] = row["user_nome"]
            else:
                resultado["ausentes"][row["user_id"]] = row["user_nome"]
        return resultado

    # ── Calendário de Lembretes ────────────────────────────

    async def salvar_lembrete(
        self,
        guild_id: int,
        nome: str,
        data_iso: str,
        horario: str,
        mensagem: str,
        canal_id: int,
        anual: bool = False,
        imagem: bytes = None,
        imagem_nome: str = None,
    ) -> int:
        """Insere um novo lembrete e retorna o id gerado."""
        cursor = await self.db.execute(
            """
            INSERT INTO calendario_lembretes
                (guild_id, nome, data_iso, horario, mensagem, canal_id,
                 anual, notificado_ano, imagem, imagem_nome)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (guild_id, nome, data_iso, horario, mensagem, canal_id,
             int(anual), imagem, imagem_nome),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def atualizar_lembrete_imagem(
        self,
        lembrete_id: int,
        imagem: bytes,
        imagem_nome: str,
    ):
        """Atualiza a imagem de um lembrete existente."""
        await self.db.execute(
            "UPDATE calendario_lembretes SET imagem = ?, imagem_nome = ? WHERE id = ?",
            (imagem, imagem_nome, lembrete_id),
        )
        await self.db.commit()

    async def get_lembretes_guild(self, guild_id: int):
        """
        Retorna todos os lembretes de uma guild SEM o BLOB de imagem,
        para não carregar tudo na memória de uma vez.
        Use get_lembrete() quando precisar da imagem completa.
        """
        cursor = await self.db.execute(
            """
            SELECT id, guild_id, nome, data_iso, horario, mensagem,
                   canal_id, anual, notificado_ano, imagem_nome
            FROM calendario_lembretes
            WHERE guild_id = ?
            ORDER BY id ASC
            """,
            (guild_id,),
        )
        return await cursor.fetchall()

    async def get_lembrete(self, lembrete_id: int):
        """Retorna um lembrete completo (incluindo BLOB de imagem) pelo id."""
        cursor = await self.db.execute(
            "SELECT * FROM calendario_lembretes WHERE id = ?",
            (lembrete_id,),
        )
        return await cursor.fetchone()

    async def atualizar_lembrete_mensagem(self, lembrete_id: int, nova_mensagem: str):
        """Atualiza apenas a mensagem de um lembrete."""
        await self.db.execute(
            "UPDATE calendario_lembretes SET mensagem = ? WHERE id = ?",
            (nova_mensagem, lembrete_id),
        )
        await self.db.commit()

    async def deletar_lembrete(self, lembrete_id: int):
        """Remove um lembrete pelo id."""
        await self.db.execute(
            "DELETE FROM calendario_lembretes WHERE id = ?",
            (lembrete_id,),
        )
        await self.db.commit()

    async def marcar_lembrete_notificado(self, lembrete_id: int, ano: int):
        """
        Marca o lembrete como notificado no ano especificado.
        Lembretes anuais: salva o ano atual → dispara de novo no próximo ano.
        Lembretes pontuais: salva 9999 → nunca mais dispara.
        """
        await self.db.execute(
            "UPDATE calendario_lembretes SET notificado_ano = ? WHERE id = ?",
            (ano, lembrete_id),
        )
        await self.db.commit()

    async def get_lembretes_pendentes_hoje(
        self,
        data_hoje: str,
        mes_dia: str,
        hora_atual: str,
        ano_atual: int,
    ):
        """
        Retorna lembretes que devem disparar na hora atual (janela de 1h).
        Inclui BLOB de imagem para montar o embed de disparo.

        - anual=1 → data_iso é 'MM-DD'; compara com mes_dia, notificado_ano != ano_atual
        - anual=0 → data_iso é 'YYYY-MM-DD'; compara com data_hoje, notificado_ano = 0
        - horario dentro da janela: hora_atual - 1h <= horario <= hora_atual
        """
        cursor = await self.db.execute(
            """
            SELECT * FROM calendario_lembretes
            WHERE (
                (anual = 1 AND data_iso = ? AND notificado_ano != ?)
                OR
                (anual = 0 AND data_iso = ? AND notificado_ano = 0)
            )
            AND horario <= ?
            AND horario >= ?
            """,
            (mes_dia, ano_atual, data_hoje, hora_atual, _hora_menos_1h(hora_atual)),
        )
        return await cursor.fetchall()


    # ── Layouts de Mensagens (V2) ──────────────────────────
    async def salvar_layout(self, msg_id: int, canal_id: int, titulo: str, descricao: str, footer: str, estilo: str, reacoes: str = None, imagem_bytes: bytes = None, imagem_nome: str = None, tipo: str = 'anuncio'):
        await self.db.execute(
            """INSERT INTO mensagens_layout (msg_id, canal_id, titulo, descricao, footer, estilo, reacoes, imagem_bytes, imagem_nome, tipo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(msg_id) DO UPDATE SET
               titulo=excluded.titulo, descricao=excluded.descricao, footer=excluded.footer, estilo=excluded.estilo, 
               reacoes=COALESCE(excluded.reacoes, mensagens_layout.reacoes),
               imagem_bytes=COALESCE(excluded.imagem_bytes, mensagens_layout.imagem_bytes),
               imagem_nome=COALESCE(excluded.imagem_nome, mensagens_layout.imagem_nome),
               tipo=COALESCE(excluded.tipo, mensagens_layout.tipo)""",
            (msg_id, canal_id, titulo, descricao, footer, estilo, reacoes, imagem_bytes, imagem_nome, tipo)
        )
        await self.db.commit()

    async def get_layout(self, msg_id: int):
        cursor = await self.db.execute("SELECT * FROM mensagens_layout WHERE msg_id=?", (msg_id,))
        return await cursor.fetchone()

# ── Auxiliar de query (fora da classe) ────────────────────
def _hora_menos_1h(horario: str) -> str:
    """Subtrai 1 hora de uma string 'HH:MM'. Usado na janela de verificação."""
    import datetime
    h, m = map(int, horario.split(":"))
    t = datetime.time(h, m)
    dt = datetime.datetime.combine(datetime.date.today(), t) - datetime.timedelta(hours=1)
    return dt.strftime("%H:%M")