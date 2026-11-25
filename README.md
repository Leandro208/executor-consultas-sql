# Executor de Consultas SQL Padronizadas

Aplicação web para a equipe manter uma biblioteca de consultas SQL usadas com
frequência, executá-las com parâmetros de formulário, exportar os resultados e
acompanhar o histórico de execução.

Substitui o hábito de procurar a query antiga em arquivos ou reescrevê-la:
a consulta fica cadastrada, organizada por grupo e pronta para executar.

## Recursos

- Biblioteca de consultas organizada por **grupos** (ex.: Estudantes).
- Cadastro de consultas com **detecção automática de parâmetros** (`:nome`).
- Formulário de parâmetros gerado a partir da definição da consulta
  (rótulo, tipo, obrigatoriedade e valor padrão).
- **Limite de linhas** por execução (estilo DBeaver), sem alterar o SQL.
- Exportação em **CSV, XLSX e JSON**.
- **Histórico** de execuções com filtros, detalhes e "executar novamente".
- **Conexões PostgreSQL configuráveis** pela interface, com senha cifrada e
  botão de teste.
- Conexões abertas em **somente leitura** (`default_transaction_read_only=on`).
- Sem login nesta versão (identificação simples por nome no histórico).
- Interface sem dependência de CDN: Bootstrap e ícones são versionados no projeto.

## Requisitos

- Python 3.10 ou superior.
- PostgreSQL acessível para as consultas (o sistema em si usa SQLite para os
  metadados).
- Opcional: `waitress` (ou `gunicorn`) para disponibilizar para a equipe.

## Configuração do ambiente (`.env`)

Todas as variáveis são opcionais. Sem `.env`, o sistema cria a chave de
criptografia e o banco de metadados automaticamente.

| Variável | Padrão | Função |
|---|---|---|
| `EXECUTOR_SECRET_KEY` | gerada em `instance/secret.key` | chave Fernet que cifra as senhas das conexões |
| `EXECUTOR_DATABASE_URL` | `sqlite:///instance/executor.db` | banco de metadados do sistema |
| `EXECUTOR_HOST` | `127.0.0.1` | interface de rede em que o servidor escuta |
| `EXECUTOR_PORT` | `5000` | porta do servidor |

Para personalizar:

```bash
cp .env.example .env
# edite o .env conforme necessário
```

> `EXECUTOR_SECRET_KEY` precisa ser uma chave Fernet válida. Gere uma com:
>
> ```bash
> python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
> ```

## Instalação

Linux/macOS:

```bash
cd executor-sql
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
cd executor-sql
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se não quiser usar ambiente virtual:

```bash
pip install -r requirements.txt --break-system-packages
```

## Executar localmente

```bash
python run.py                 # http://127.0.0.1:5000
python run.py --host 0.0.0.0 --port 8080
python run.py --debug         # modo de desenvolvimento
```

O banco de metadados é criado automaticamente em `instance/executor.db` na
primeira execução.

### Disponibilizar para a equipe

O servidor embutido do Flask (`app.run`) é adequado para uso local e testes.
Para deixar rodando na rede interna, prefira um servidor WSGI:

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 run:app
```

Sem autenticação, restrinja o acesso à rede interna/VPN.

## Primeiros passos

1. **Conexões → Nova conexão**: informe host, porta, banco, usuário e senha.
   Use o botão **Testar** para validar. Prefira um usuário **somente leitura**.
2. **Grupos → Novo grupo**: crie categorias como "Estudantes".
3. **Consultas → Nova consulta**: cole o SQL usando `:parametro` e clique em
   **Detectar parâmetros** para revisar rótulo, tipo e obrigatoriedade.
4. Na tela inicial, escolha a consulta, preencha os parâmetros, defina o limite
   de linhas e clique em **Executar**. Use os botões de exportação se precisar.
5. **Histórico** mostra quem executou, quando, com quais parâmetros e o resultado.

### Consulta mínima para validar a conexão

```sql
SELECT current_database() AS banco, now() AS hora
```

Se essa consulta funcionar, a conexão está OK e você pode cadastrar as consultas
reais.

## Sintaxe de parâmetros

```sql
SELECT u.id, u.nome, u.email
FROM usuarios u
WHERE u.id = :user_id
  AND u.criado_em >= :data_inicio::date
```

- Use `:nome` fora de aspas e comentários.
- Casts do PostgreSQL (`::text`, `::date`) são preservados.
- Somente `SELECT`, `WITH`, `TABLE`, `VALUES` e `EXPLAIN` são aceitos.
- Apenas um comando por consulta.

## Configurações

Em **Configurações** é possível ajustar:

- limite padrão de linhas;
- timeout de execução (segundos);
- teto de linhas na exportação (a exportação reexecuta a consulta).

## Backup e restauração

Todos os dados do sistema ficam em `instance/`:

- `executor.db` — conexões, grupos, consultas, parâmetros e histórico;
- `secret.key` — chave que decifra as senhas das conexões.

**Backup:** copie a pasta `instance/` inteira (pare o servidor antes, ou use
`sqlite3 instance/executor.db ".backup backup.db"`).

**Restauração:** devolva os dois arquivos para `instance/` e reinicie.

**Resetar tudo:** apague `instance/executor.db` (e `secret.key`, se quiser uma
chave nova). O sistema recria os arquivos vazios na próxima execução.

> ⚠️ Guarde `secret.key` junto do `executor.db`. Sem ela, as senhas salvas não
> podem ser decifradas e as conexões precisarão ser recadastradas.

## Segurança

- A aplicação **não possui autenticação**. Restrinja o acesso à rede interna.
- Senhas de conexão são cifradas com Fernet. A chave fica em
  `instance/secret.key` ou na variável `EXECUTOR_SECRET_KEY`.
- Toda conexão de destino é aberta em modo somente leitura, portanto comandos de
  escrita são recusados pelo PostgreSQL mesmo que a validação seja contornada.
- O SQL é validado e os parâmetros são ligados pelo driver (psycopg2), sem
  concatenação de valores.
- Recomenda-se criar um usuário PostgreSQL com `CONNECT` e apenas `SELECT`.
- Não há proteção CSRF; por ser uma ferramenta interna sem login, isso é aceitável
  nesta versão, mas deve ser revisto junto com a autenticação.

## Solução de problemas

| Sintoma | Causa provável / solução |
|---|---|
| `connection refused` ou timeout | Host/porta errados, firewall ou VPN desconectada |
| `password authentication failed` | Usuário/senha incorretos ou regra no `pg_hba.conf` |
| `SSL error` / `server does not support SSL` | Ajuste o **SSL mode** da conexão (`disable`, `prefer`, `require`) |
| `canceling statement due to statement timeout` | Aumente o timeout em **Configurações** |
| Porta 5000 ocupada | Use `python run.py --port 8080` |
| `Nao foi possivel decifrar a senha da conexao` | `secret.key` foi trocada; recadastre a senha da conexão |
| Página sem estilo | Confirme que `app/static/vendor/` está presente |

## Estrutura

```
executor-sql/
  app/
    __init__.py          # app factory
    config.py            # configuração e chave
    extensions.py        # SQLAlchemy
    models.py            # Conexao, Grupo, Consulta, Parametro, Execucao
    crypto.py            # cifra das senhas
    routes/              # blueprints (dashboard, grupos, conexões, consultas, histórico, config)
    services/
      sqlparser.py       # detecção/validação de SQL e placeholders
      connections.py     # engines PostgreSQL e teste de conexão
      executor.py        # execução com limite e timeout
      exporter.py        # csv/xlsx/json
    templates/           # Jinja2 + Bootstrap
    static/              # Bootstrap, ícones e CSS versionados
  tests/
  instance/              # SQLite de metadados e chave (não versionado)
  run.py
```

## Testes

```bash
pytest -q
```

Os testes usam SQLite temporário e não precisam de um PostgreSQL em execução.

## Limitações conhecidas

- Sem controle de permissões/login (previsto para uma próxima etapa).
- Suporte a conexões apenas PostgreSQL nesta versão.
- O histórico não possui rotina automática de retenção (use **Limpar histórico**).

## Licença

Uso interno. Consulte o arquivo [LICENSE](LICENSE).
