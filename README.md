# Nuxora Bot

Bot Discord + API FastAPI + Dashboard Web + Postgres + Docker.

## Instalar
```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

## Acessar
Dashboard: `http://SEU_IP:8088`
API Docs: `http://SEU_IP:8008/docs`

Login padrão: `admin / admin123`.

## Discord
Ative no Developer Portal:
- Message Content Intent
- Server Members Intent
- Presence Intent

Convide com scopes:
- bot
- applications.commands

## O que tem
- Sistema de Allowlist
- Postagem em Embed via modal 
- Decisão da staff com botões
- Cargo automático aprovado/entrevista
- Sugestões com thread e votos
- Dashboard com applications, sugestões e configurações
- API pronta para painel/site/launcher
- Integrações opcionais preparadas para FiveM, Minecraft, Conan e Hytale

# Comandos do Bot

Abaixo estão os principais comandos disponíveis no bot.

> Alguns comandos são restritos à staff/administração e exigem permissões como `Gerenciar Servidor`, `Gerenciar Canais` ou `Gerenciar Mensagens`.

---

# Allowlist

## `/painel_allowlist`

Envia o painel principal de allowlist no canal atual.

### Uso

```txt
/painel_allowlist
```

### Descrição

Cria uma embed fixa com botão para iniciar a allowlist.  
Quando o usuário clica, o bot cria um canal privado, faz as perguntas configuradas e envia a ficha para o canal da staff.

---

# Decisão de Allowlist

As decisões são feitas pelos botões enviados no canal da staff:

```txt
Aprovar
Entrevista
Reprovar
```

## Aprovar

Ao aprovar uma allowlist, o bot pode:

- alterar o apelido do usuário para a primeira resposta da allowlist;
- adicionar o cargo aprovado;
- remover um cargo antigo configurado;
- enviar mensagem na DM do usuário;
- enviar mensagem no canal de aprovados, se configurado.

## Entrevista

Ao encaminhar para entrevista, o bot pode:

- adicionar o cargo de entrevista;
- enviar mensagem na DM do usuário.

## Reprovar

Ao reprovar, o bot pode:

- enviar mensagem na DM do usuário;
- enviar mensagem no canal de reprovados, se configurado.

---

# Embeds Personalizados

## `/embed`

Envia uma embed personalizada no canal atual.

### Uso

```txt
/embed
```

### Recursos

- título;
- descrição;
- imagem;
- thumbnail;
- botão com link;
- footer fixo configurado no código.

---

# Tickets

## `/painel_tickets`

Envia o painel de tickets no canal atual.

### Uso

```txt
/painel_tickets
```

### Descrição

Cria uma embed com botões para abrir tickets conforme os tipos configurados no painel ou via comandos.

---

## `/ticket_config`

Configura o sistema de tickets pelo Discord.

### Uso

```txt
/ticket_config
```

### Parâmetros principais

```txt
titulo
descricao
categoria_padrao
cargo_staff_padrao
canal_logs
cor_hex
```

### Exemplo

```txt
/ticket_config titulo:"Central de Atendimento" descricao:"Escolha o tipo de atendimento abaixo." cor_hex:"#8B0000"
```

---

## `/ticket_tipo_add`

Adiciona ou atualiza um tipo de ticket.

### Uso

```txt
/ticket_tipo_add
```

### Parâmetros

```txt
id_tipo
label
emoji
descricao
estilo
categoria
cargos_acesso
```

### Estilos disponíveis

```txt
gray
red
green
blurple
```

### Exemplo

```txt
/ticket_tipo_add id_tipo:denuncia label:"Denúncia" emoji:"🚨" descricao:"Abra um ticket para denúncias." estilo:red
```

Para cargos de acesso, use IDs separados por vírgula:

```txt
111111111111111111,222222222222222222
```

---

## `/ticket_tipo_remove`

Remove um tipo de ticket.

### Uso

```txt
/ticket_tipo_remove id_tipo:denuncia
```

---

## `/ticket_criar`

Cria manualmente um ticket para um usuário pelo ID do Discord.

### Uso

```txt
/ticket_criar usuario_id:123456789012345678 tipo_id:suporte
```

Com título personalizado:

```txt
/ticket_criar usuario_id:123456789012345678 tipo_id:suporte titulo:"Atendimento manual da staff"
```

---

## `/fechar_ticket`

Fecha o ticket atual.

### Uso

```txt
/fechar_ticket
```

### Descrição

Fecha o canal de ticket atual, gera transcript e envia no canal de logs, se configurado.

---

# Autorole

## `/autorole_config`

Configura um cargo automático para novos membros.

### Ver configuração atual

```txt
/autorole_config
```

### Definir cargo

```txt
/autorole_config cargo:@Membro
```

### Desativar

```txt
/autorole_config desativar:true
```

---

# Logs de Entrada e Saída

## `/memberlog_config`

Configura canais separados para logs de entrada e saída de membros.

### Uso

```txt
/memberlog_config canal_entrada:#entradas canal_saida:#saidas
```

### Desativar entrada

```txt
/memberlog_config desativar_entrada:true
```

### Desativar saída

```txt
/memberlog_config desativar_saida:true
```

---

## `/memberlog_embed`

Configura a embed de entrada ou saída de membros.

### Entrada

```txt
/memberlog_embed tipo:entrada titulo:"👋 Bem-vindo(a)" descricao:"{user} entrou em {server}!" footer:"Bem-vindo" cor_hex:"#8B0000"
```

### Saída

```txt
/memberlog_embed tipo:saida titulo:"📤 Membro saiu" descricao:"**{username}** deixou {server}." footer:"Saídas" cor_hex:"#8B0000"
```

### Variáveis disponíveis

```txt
{user}
{username}
{display_name}
{id}
{server}
{member_count}
```

---

# Sugestões

O sistema de sugestões funciona a partir do canal configurado.

Quando um usuário envia uma sugestão no canal definido, o bot pode:

- transformar a sugestão em embed;
- adicionar reações;
- criar tópico de discussão;
- registrar a sugestão no dashboard.

---

# Streamer Rewards / XP por Live

Sistema de parceria com streamers usando Twitch, XP e recompensas.

## `/streamer_add`

Cadastra um streamer parceiro.

### Uso

```txt
/streamer_add membro:@Streamer twitch_login:nomedatwitch jogo:conan xp_por_minuto:1
```

### Jogos aceitos

```txt
conan
fivem
minecraft
todos
```

---

## `/streamer_remove`

Desativa um streamer parceiro.

### Uso

```txt
/streamer_remove membro:@Streamer
```

---

## `/xp`

Mostra o XP do streamer.

### Uso

```txt
/xp
```

---

## `/ranking_streamers`

Mostra o ranking dos streamers por XP.

### Uso

```txt
/ranking_streamers
```

---

## `/recompensa_add`

Cria uma recompensa para streamers.

### Uso

```txt
/recompensa_add jogo:conan nome:"Kit Guerreiro" custo:300 descricao:"Kit inicial para Conan" entrega:manual
```

### Exemplo FiveM

```txt
/recompensa_add jogo:fivem nome:"50 mil no banco" custo:500 descricao:"R$ 50.000 dentro do servidor" entrega:manual
```

### Exemplo Minecraft

```txt
/recompensa_add jogo:minecraft nome:"Kit Diamante" custo:250 descricao:"10 diamantes + 1 picareta" entrega:manual
```

---

## `/loja_streamer`

Mostra as recompensas disponíveis.

### Uso

```txt
/loja_streamer jogo:todos
```

### Por jogo

```txt
/loja_streamer jogo:conan
/loja_streamer jogo:fivem
/loja_streamer jogo:minecraft
```

---

## `/resgatar`

Resgata uma recompensa usando XP.

### Uso

```txt
/resgatar recompensa_id:1
```

---

## `/resgates_pendentes`

Lista os resgates pendentes para a staff.

### Uso

```txt
/resgates_pendentes
```

---

## `/resgate_entregar`

Marca um resgate como entregue.

### Uso

```txt
/resgate_entregar resgate_id:1 nota:"Entregue no jogo"
```

---

## `/resgate_rejeitar`

Rejeita um resgate e devolve o XP ao streamer.

### Uso

```txt
/resgate_rejeitar resgate_id:1 nota:"Solicitação inválida"
```

---

## `/xp_add`

Adiciona XP manualmente a um streamer.

### Uso

```txt
/xp_add membro:@Streamer quantidade:100 motivo:"Evento especial"
```

---

## `/xp_remove`

Remove XP manualmente de um streamer.

### Uso

```txt
/xp_remove membro:@Streamer quantidade:50 motivo:"Correção"
```

---

# Permissões Recomendadas

Para funcionamento completo, o bot precisa das seguintes permissões no Discord:

```txt
Gerenciar Canais
Gerenciar Cargos
Gerenciar Apelidos
Enviar Mensagens
Ler Histórico de Mensagens
Anexar Arquivos
Criar Tópicos
Usar Comandos de Aplicativo
```

> Para adicionar/remover cargos e alterar apelidos, o cargo do bot precisa estar acima dos cargos que ele vai gerenciar.

---

# Observações

- O painel de allowlist e tickets deve ser enviado pelo menos uma vez no Discord.
- Se novos tipos de ticket forem criados, use `/painel_tickets` novamente para gerar um painel atualizado.
- O sistema de Twitch XP exige `TWITCH_CLIENT_ID` e `TWITCH_CLIENT_SECRET` no `.env`.
- A entrega de recompensas para Conan, FiveM e Minecraft começa como manual, podendo ser automatizada depois por integração específica.

- O painel de allowlist e tickets deve ser enviado pelo menos uma vez no Discord.
- Se novos tipos de ticket forem criados, use `/painel_tickets` novamente para gerar um painel atualizado.
- O sistema de Twitch XP exige `TWITCH_CLIENT_ID` e `TWITCH_CLIENT_SECRET` no `.env`.
- A entrega de recompensas para Conan, FiveM e Minecraft começa como manual, podendo ser automatizada depois por integração específica.
