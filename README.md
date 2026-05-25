# Nuxora Automation

![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)

Nuxora é um bot para Discord com painel web estilo SaaS, feito para gerenciar servidores, clientes e automações de comunidade.

Inclui painel admin, painel do cliente, controle por servidor vinculado, allowlist, tickets, sugestões, embeds, autorole, logs de entrada/saída, lives da Twitch e personalização do bot por servidor.

---

## Recursos

- Painel web com login
- Painel admin para criar clientes
- Vinculação de servidores Discord a clientes
- Bot só funciona em servidores autorizados
- Servidor `active`: bot funciona
- Servidor `blocked`: bot permanece, mas para de responder
- Servidor removido/desvinculado: bot sai do servidor
- Allowlist com perguntas personalizadas
- Aprovação, reprovação e entrevista
- Mensagens customizadas de aprovado/reprovado/entrevista
- Tickets
- Sugestões
- Embeds pelo Discord e pelo painel
- Autorole
- Logs de entrada e saída
- Notificação automática de lives da Twitch
- Nick, avatar, banner e bio do bot por servidor

---

## Stack

- Python
- Discord.py
- FastAPI
- PostgreSQL
- Nginx
- Docker Compose
- HTML/CSS/JS

---

## Estrutura

```txt
api/                  API FastAPI
bot/                  Bot Discord
bot/modules/          Módulos do bot
bot/shared/           Banco e helpers do bot
web/                  Painel web
data/postgres/        Dados do PostgreSQL
docker-compose.yml
.env
```

---

## Comandos do bot

### Allowlist

```txt
/painel_allowlist
```

Envia ou atualiza o painel de allowlist no canal atual.

### Tickets

```txt
/painel_tickets
```

Envia o painel de tickets.

```txt
/ticket_config
```

Configura opções gerais do sistema de tickets.

```txt
/ticket_tipo_add
```

Adiciona um tipo de ticket.

```txt
/ticket_tipo_remove
```

Remove um tipo de ticket.

```txt
/ticket_criar
```

Cria um ticket manualmente.

```txt
/fechar_ticket
```

Fecha o ticket atual.

### Embeds

```txt
/embed
```

Cria um embed personalizado pelo Discord.

### Autorole

```txt
/autorole_config
```

Configura cargo automático para novos membros.

### Logs de membros

```txt
/memberlog_config
```

Configura canais de entrada e saída.

```txt
/memberlog_embed
```

Configura os embeds de entrada e saída.

---

## Configuração inicial

Clone o projeto:

```bash
git clone https://gitlab.com/seu-usuario/nuxora.git
cd nuxora
```

Crie o arquivo `.env`:

```env
POSTGRES_DB=nuxora
POSTGRES_USER=nuxora
POSTGRES_PASSWORD=troque_esta_senha
DATABASE_URL=postgresql://nuxora:troque_esta_senha@nuxora-postgres:5432/nuxora

DISCORD_BOT_TOKEN=seu_token_do_bot
DISCORD_CLIENT_ID=seu_client_id_do_bot
DISCORD_BOT_PERMISSIONS=8

BOT_COLOR=#8B0000

TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
TWITCH_CHECK_INTERVAL_SECONDS=300
```

Suba a stack:

```bash
docker compose build --no-cache
docker compose up -d
```

Ver logs:

```bash
docker compose logs -f
```

---

## Criar usuário admin

```bash
docker compose exec -T nuxora-api python - <<'PY'
from shared.db import row, execute, hash_password, now

username = "admin"
password = "admin123"
email = "admin@nuxora.local"

user = row("SELECT id FROM users WHERE username=?", (username,))

if user:
    execute(
        "UPDATE users SET password_hash=?, email=?, role=?, is_active=? WHERE username=?",
        (hash_password(password), email, "admin", True, username),
    )
    print("Admin atualizado.")
else:
    execute(
        """
        INSERT INTO users
        (username, password_hash, email, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username, hash_password(password), email, "admin", True, now()),
    )
    print("Admin criado.")

print("Login:", username)
print("Senha:", password)
PY
```

Depois acesse o painel e troque a senha em **Minha conta**.

---

## Acesso local

Painel web:

```txt
http://IP_DO_SERVIDOR:8088
```

API:

```txt
http://IP_DO_SERVIDOR:8008
```

---

## Configuração com domínio

Exemplo:

```txt
https://nuxora.seudominio.com
```

O painel web chama a API usando `/api`.

A API internamente espera rotas sem `/api`, por exemplo:

```txt
/auth/login
/me
/guilds
/health
```

Por isso, ao usar proxy reverso, é necessário encaminhar `/api/` para a API e remover o prefixo `/api`.

---

## Nginx Proxy Manager

Crie um **Proxy Host** para o domínio:

```txt
nuxora.seudominio.com
```

Aponte a rota principal para o painel:

```txt
Forward Hostname/IP: nuxora-web
Forward Port: 80
```

Depois crie uma **Custom Location**:

```txt
Location: /api/
Forward Hostname/IP: nuxora-api
Forward Port: 8000
```

Na aba **Advanced** dessa custom location, adicione:

```nginx
rewrite ^/api/(.*)$ /$1 break;
```

Isso faz:

```txt
/api/auth/login
```

virar internamente:

```txt
/auth/login
```

Sem esse rewrite, o login retorna:

```txt
404 Not Found
```

Teste:

```bash
curl -i https://nuxora.seudominio.com/api/health
```

Resposta esperada:

```json
{"ok":true}
```

---

## Fluxo SaaS

1. Admin cria um cliente.
2. Admin vincula um servidor Discord ao cliente.
3. Cliente acessa o painel.
4. Cliente convida o bot.
5. Bot verifica se o servidor está vinculado.

Status:

```txt
active   bot funciona normalmente
blocked  bot permanece no servidor, mas para de responder
removido bot sai do servidor
```

---

## Permissões do bot

Para teste:

```env
DISCORD_BOT_PERMISSIONS=8
```

Isso convida o bot como administrador.

Mesmo assim, no Discord, coloque o cargo do bot acima dos cargos que ele precisa adicionar/remover.

---

## Twitch Lives

Para notificações de live, configure:

```env
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
TWITCH_CHECK_INTERVAL_SECONDS=300
```

No painel, cadastre:

- streamer
- canal do Discord
- mensagem
- embed
- cor

Placeholders:

```txt
{streamer}
{login}
{title}
{game}
{url}
{viewers}
```

---

## Placeholders de allowlist

```txt
{user}
{username}
{display_name}
{id}
{character}
```

Exemplo:

```txt
Parabéns, {user}!
Seu personagem {character} foi aprovado.
```

---

## Comandos úteis

Rebuild completo:

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
```

Rebuild só do bot:

```bash
docker compose build --no-cache nuxora-bot
docker compose up -d --force-recreate nuxora-bot
```

Rebuild só da API:

```bash
docker compose build --no-cache nuxora-api
docker compose up -d --force-recreate nuxora-api
```

Logs do bot:

```bash
docker compose logs -f nuxora-bot
```

Logs da API:

```bash
docker compose logs -f nuxora-api
```

Entrar no banco:

```bash
docker compose exec nuxora-postgres psql -U nuxora -d nuxora
```

Listar usuários:

```bash
docker compose exec nuxora-postgres psql -U nuxora -d nuxora -c "SELECT id, username, role, is_active FROM users;"
```

---

## Problemas comuns

### Login retorna 404

Configure o rewrite no Nginx Proxy Manager:

```nginx
rewrite ^/api/(.*)$ /$1 break;
```

### Bot não adiciona cargo

Coloque o cargo do bot acima do cargo que ele precisa adicionar/remover.

### Bot sai do servidor

O servidor não está vinculado no painel admin.

### Bot fica no servidor, mas não responde

O servidor está com status `blocked`.

### Slash commands não aparecem

Reinicie o bot e aguarde a sincronização:

```bash
docker compose restart nuxora-bot
docker compose logs -f nuxora-bot
```

---

## Licença

Este projeto é licenciado sob a **AGPL-3.0**.

A AGPL-3.0 permite usar, estudar, modificar e distribuir o código, mas exige que modificações feitas e disponibilizadas como serviço em rede também tenham seu código-fonte correspondente disponibilizado sob a mesma licença.

Veja o arquivo `LICENSE` para mais detalhes.

---

## Status

Projeto em desenvolvimento ativo.