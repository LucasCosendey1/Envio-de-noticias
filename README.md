# 📰 Envio de Notícias Diárias

Automação que busca notícias do tema que você escolher e envia um email formatado todo dia no horário configurado — sem precisar de servidor ou computador ligado.

Funciona 100% na nuvem usando **GitHub Actions** + **NewsAPI** + **Gmail API**.

---

## Como funciona

1. O GitHub Actions dispara automaticamente no horário agendado
2. O script busca as últimas notícias via NewsAPI
3. Formata um email HTML e envia via Gmail

---

## Como fazer seu próprio

### 1. Faça um fork deste repositório

Clique em **Fork** no canto superior direito.

### 2. Obtenha as credenciais necessárias

**NewsAPI**
- Crie uma conta gratuita em [newsapi.org](https://newsapi.org)
- Copie sua API Key (plano gratuito: 100 req/dia)

**Gmail API**
- Acesse o [Google Cloud Console](https://console.cloud.google.com)
- Crie um projeto e habilite a **Gmail API**
- Em **Credenciais**, crie um **ID do cliente OAuth 2.0** do tipo **App para computador**
- Baixe o `credentials.json`
- Rode localmente uma vez para gerar o `token.json`:

```bash
pip install google-auth-oauthlib google-api-python-client
python gerar_token.py
```

> O arquivo `gerar_token.py` está incluído no repositório.

### 3. Configure os secrets no GitHub

No seu fork, vá em **Settings → Secrets and variables → Actions → New repository secret** e adicione:

| Secret | Descrição |
|--------|-----------|
| `NEWSAPI_KEY` | Sua chave da NewsAPI |
| `GMAIL_TOKEN_JSON` | Conteúdo completo do `token.json` gerado |
| `EMAIL_REMETENTE` | Email que vai enviar (o Gmail autorizado) |
| `EMAIL_DESTINATARIO` | Email que vai receber as notícias |
| `NEWS_QUERY` | Tema das notícias (ex: `inteligencia artificial`) |

### 4. Ajuste o horário (opcional)

No arquivo `.github/workflows/news.yml`, edite a linha do cron:

```yaml
- cron: "0 11 * * *"  # 8h horário de Brasília
```

Referência de horários (UTC):

| Brasília | UTC |
|----------|-----|
| 7h | `0 10 * * *` |
| 8h | `0 11 * * *` |
| 9h | `0 12 * * *` |
| 12h | `0 15 * * *` |

### 5. Teste manualmente

Vá em **Actions → Enviar Notícias Diárias → Run workflow** para testar antes de esperar o horário agendado.

---

## Variáveis de ambiente

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `NEWSAPI_KEY` | ✅ | — | Chave da NewsAPI |
| `GMAIL_TOKEN_JSON` | ✅ | — | JSON do token Gmail |
| `EMAIL_REMETENTE` | ✅ | — | Email remetente |
| `EMAIL_DESTINATARIO` | ✅ | — | Email destinatário |
| `NEWS_QUERY` | ❌ | top headlines BR | Tema de busca |
| `NEWS_LANGUAGE` | ❌ | `pt` | Idioma (`pt` ou `en`) |
| `NEWS_COUNT` | ❌ | `8` | Quantidade de notícias |

---

## Tecnologias

- [GitHub Actions](https://github.com/features/actions) — agendamento e execução
- [NewsAPI](https://newsapi.org) — fonte das notícias
- [Gmail API](https://developers.google.com/gmail/api) — envio do email
- Python 3.11
