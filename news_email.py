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

NEWSAPI_KEY  = os.environ["NEWSAPI_KEY"]
DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO", "lukecosendey@gmail.com")
REMETENTE    = os.environ.get("EMAIL_REMETENTE", "honeylabsai@gmail.com")
SCOPES       = ["https://www.googleapis.com/auth/gmail.send"]

# ─── Gmail ────────────────────────────────────────────────────────────────────

def get_gmail_service():
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if token_json:
        with open("token.json", "w") as f:
            f.write(token_json)
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

# ─── NewsAPI ──────────────────────────────────────────────────────────────────

def buscar_noticias(query, quantidade):
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NEWSAPI_KEY,
        "q": query,
        "language": "pt",
        "pageSize": quantidade,
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    artigos = data.get("articles", [])

    # Fallback: se não vier nada em pt, tenta em inglês
    if not artigos:
        params["language"] = "en"
        resp = requests.get(url, params=params, timeout=10)
        artigos = resp.json().get("articles", [])

    resultado = []
    for a in artigos[:quantidade]:
        resultado.append({
            "titulo": a.get("title") or "Sem título",
            "fonte":  (a.get("source") or {}).get("name") or "",
            "resumo": a.get("description") or a.get("content") or "",
            "link":   a.get("url") or "#",
        })
    return resultado

# ─── HTML ─────────────────────────────────────────────────────────────────────

MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho",
            "julho","agosto","setembro","outubro","novembro","dezembro"]

def card_noticia(noticia):
    titulo = noticia.get("titulo", "Sem título")
    fonte  = noticia.get("fonte", "")
    resumo = (noticia.get("resumo") or "").replace("\n", "<br>")
    link   = noticia.get("link", "#")

    return f"""
    <div style="background:#111;border-radius:12px;padding:20px 24px;
                margin-bottom:16px;border-left:3px solid #FFD60A;">
      <p style="margin:0 0 6px;color:#FFD60A;font-size:11px;
                font-weight:700;letter-spacing:1px;text-transform:uppercase;">{fonte}</p>
      <a href="{link}" style="text-decoration:none;">
        <h3 style="margin:0 0 10px;color:#fff;font-size:16px;
                   font-weight:700;line-height:1.4;">{titulo}</h3>
      </a>
      <p style="margin:0;color:#aaa;font-size:13px;line-height:1.7;">{resumo}</p>
    </div>"""


def gerar_html(noticias_ia, noticias_tech):
    hoje = datetime.now()
    data_str = f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"

    cards_ia   = "".join(card_noticia(n) for n in noticias_ia)  if noticias_ia   else "<p style='color:#666'>Nenhuma notícia encontrada.</p>"
    cards_tech = "".join(card_noticia(n) for n in noticias_tech) if noticias_tech else "<p style='color:#666'>Nenhuma notícia encontrada.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

        <tr><td style="background:#111;border-radius:16px 16px 0 0;
                       padding:32px 40px;border-bottom:2px solid #FFD60A;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <p style="margin:0;color:#FFD60A;font-size:11px;font-weight:700;
                          letter-spacing:3px;text-transform:uppercase;">Honey Labs</p>
                <h1 style="margin:8px 0 0;color:#fff;font-size:24px;font-weight:700;">📰 Notícias do dia</h1>
              </td>
              <td align="right">
                <div style="background:#FFD60A;border-radius:12px;padding:10px 16px;">
                  <p style="margin:0;color:#111;font-size:11px;font-weight:700;">{data_str}</p>
                </div>
              </td>
            </tr>
          </table>
        </td></tr>

        <tr><td style="background:#111;padding:32px 40px;">

          <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                    letter-spacing:2px;text-transform:uppercase;">🤖 Inteligência Artificial</p>
          {cards_ia}

          <hr style="border:none;border-top:1px solid #222;margin:24px 0;">

          <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                    letter-spacing:2px;text-transform:uppercase;">💻 Tecnologia</p>
          {cards_tech}

        </td></tr>

        <tr><td style="background:#0d0d0d;border-radius:0 0 16px 16px;
                       padding:20px 40px;border-top:1px solid #1a1a1a;">
          <p style="margin:0;color:#444;font-size:12px;">
            Powered by NewsAPI ·
            <a href="https://www.honeylabs.com.br" style="color:#FFD60A;text-decoration:none;">Honey Labs</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

# ─── Envio ────────────────────────────────────────────────────────────────────

def enviar_email(service, html):
    hoje = datetime.now()
    assunto = f"📰 Tech & IA — {hoje.strftime('%d/%m/%Y')}"

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
    print("🤖 Buscando notícias de IA...")
    noticias_ia = buscar_noticias("inteligência artificial", 1)
    print(f"  {len(noticias_ia)} notícia(s).")

    print("💻 Buscando notícias de tecnologia...")
    noticias_tech = buscar_noticias("tecnologia", 2)
    print(f"  {len(noticias_tech)} notícia(s).")

    print("📧 Enviando email...")
    service = get_gmail_service()
    html = gerar_html(noticias_ia, noticias_tech)
    enviar_email(service, html)
