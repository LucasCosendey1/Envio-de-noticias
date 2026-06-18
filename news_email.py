import base64
import json
import os
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Configuração ─────────────────────────────────────────────────────────────

NEWSAPI_KEY   = os.environ["NEWSAPI_KEY"]
DESTINATARIO  = os.environ.get("EMAIL_DESTINATARIO", "lukecosendey@gmail.com")
REMETENTE     = os.environ.get("EMAIL_REMETENTE", "honeylabsai@gmail.com")

# Query de notícias — ajuste conforme quiser
NEWS_QUERY    = os.environ.get("NEWS_QUERY", "mercado financeiro brasil")
NEWS_LANGUAGE = os.environ.get("NEWS_LANGUAGE", "pt")
NEWS_COUNT    = int(os.environ.get("NEWS_COUNT", "8"))

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# ─── Gmail ────────────────────────────────────────────────────────────────────

def get_gmail_service():
    """Carrega credenciais dos secrets do GitHub e retorna o serviço Gmail."""
    # No GitHub Actions, token.json e credentials.json vêm de secrets
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if token_json:
        with open("token.json", "w") as f:
            f.write(token_json)

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ─── NewsAPI ──────────────────────────────────────────────────────────────────

def buscar_noticias():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": NEWS_QUERY,
        "language": NEWS_LANGUAGE,
        "sortBy": "publishedAt",
        "pageSize": NEWS_COUNT,
        "apiKey": NEWSAPI_KEY,
    }
    res = requests.get(url, params=params, timeout=10)
    res.raise_for_status()
    data = res.json()
    if data["status"] != "ok":
        raise RuntimeError(f"NewsAPI erro: {data}")
    return data["articles"]


# ─── HTML do email ────────────────────────────────────────────────────────────

MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho",
            "julho","agosto","setembro","outubro","novembro","dezembro"]

def gerar_html(artigos):
    hoje = datetime.now()
    data_str = f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"

    cards = ""
    for a in artigos:
        titulo     = a.get("title", "Sem título") or "Sem título"
        descricao  = a.get("description", "") or ""
        url        = a.get("url", "#") or "#"
        fonte      = a.get("source", {}).get("name", "") or ""
        pub_raw    = a.get("publishedAt", "")
        try:
            pub = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            pub_str = pub.strftime("%d/%m %H:%M")
        except Exception:
            pub_str = ""

        cards += f"""
        <div style="background:#111; border-radius:12px; padding:20px 24px;
                    margin-bottom:16px; border-left:3px solid #FFD60A;">
          <p style="margin:0 0 4px; color:#FFD60A; font-size:11px;
                    font-weight:700; letter-spacing:1px; text-transform:uppercase;">
            {fonte}{' · ' + pub_str if pub_str else ''}
          </p>
          <a href="{url}" style="text-decoration:none;">
            <h3 style="margin:0 0 8px; color:#fff; font-size:16px;
                       font-weight:700; line-height:1.4;">{titulo}</h3>
          </a>
          <p style="margin:0; color:#888; font-size:13px; line-height:1.6;">
            {descricao}
          </p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0a0a;
             font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0a0a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;">

        <!-- Header -->
        <tr><td style="background:#111;border-radius:16px 16px 0 0;
                       padding:32px 40px;border-bottom:2px solid #FFD60A;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <p style="margin:0;color:#FFD60A;font-size:11px;font-weight:700;
                          letter-spacing:3px;text-transform:uppercase;">
                  Honey Labs
                </p>
                <h1 style="margin:8px 0 0;color:#fff;font-size:24px;
                           font-weight:700;">📰 Notícias do dia</h1>
              </td>
              <td align="right">
                <div style="background:#FFD60A;border-radius:12px;
                            padding:10px 16px;display:inline-block;">
                  <p style="margin:0;color:#111;font-size:11px;
                            font-weight:700;">{data_str}</p>
                </div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:#111;padding:32px 40px;">
          <p style="margin:0 0 24px;color:#666;font-size:13px;">
            {len(artigos)} notícias sobre: <em>{NEWS_QUERY}</em>
          </p>
          {cards}
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#0d0d0d;border-radius:0 0 16px 16px;
                       padding:20px 40px;border-top:1px solid #1a1a1a;">
          <p style="margin:0;color:#444;font-size:12px;">
            Enviado automaticamente ·
            <a href="https://www.honeylabs.com.br"
               style="color:#FFD60A;text-decoration:none;">Honey Labs</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ─── Envio ────────────────────────────────────────────────────────────────────

def enviar_email(service, html, total):
    hoje = datetime.now()
    assunto = f"📰 Notícias do mercado — {hoje.strftime('%d/%m/%Y')} ({total} artigos)"

    msg = MIMEMultipart("alternative")
    msg["To"]      = DESTINATARIO
    msg["From"]    = REMETENTE
    msg["Subject"] = assunto
    msg.attach(MIMEText("Abra este email em um cliente que suporte HTML.", "plain"))
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"✅ Email enviado! ID: {result['id']}")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Buscando notícias...")
    artigos = buscar_noticias()
    print(f"{len(artigos)} artigos encontrados.")

    print("Conectando ao Gmail...")
    service = get_gmail_service()

    html = gerar_html(artigos)
    enviar_email(service, html, len(artigos))
