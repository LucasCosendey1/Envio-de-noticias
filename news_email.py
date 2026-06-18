import base64
import json
import os
import re
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google import genai
from google.genai import types
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Configuração ─────────────────────────────────────────────────────────────

GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
DESTINATARIO    = os.environ.get("EMAIL_DESTINATARIO", "lukecosendey@gmail.com")
REMETENTE       = os.environ.get("EMAIL_REMETENTE", "honeylabsai@gmail.com")
SCOPES          = ["https://www.googleapis.com/auth/gmail.send"]

client = genai.Client(api_key=GEMINI_API_KEY)

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

# ─── Gemini com Google Search ─────────────────────────────────────────────────

SEARCH_CONFIG = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())]
)

def buscar_noticias_gemini(tema, quantidade):
    """Usa Gemini + Google Search para buscar notícias recentes e resumir."""
    hoje = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""Hoje é {hoje}. Pesquise na internet as {quantidade} notícia(s) mais recente(s) sobre "{tema}" dos últimos 2 dias.

Para cada notícia encontrada, retorne EXATAMENTE neste formato JSON:
[
  {{
    "titulo": "Título da notícia",
    "fonte": "Nome do site/jornal",
    "resumo": "Explique com suas próprias palavras o que aconteceu, por que é relevante e qual o impacto. Máximo 3 frases. Não copie o texto original.",
    "link": "URL da notícia"
  }}
]

Retorne APENAS o JSON, sem texto adicional. Foque em notícias relevantes e recentes, evite artigos genéricos ou digests."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=SEARCH_CONFIG,
        )
        texto = response.text.strip()
        match = re.search(r'\[.*\]', texto, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception as e:
        print(f"Erro ao buscar notícias de {tema}: {e}")
        return []


def buscar_hackathons_paraiba():
    """Usa Gemini + Google Search para buscar hackathons futuros na Paraíba."""
    hoje = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""Hoje é {hoje}. Pesquise na internet hackathons na Paraíba (Brasil) que:
1. Ainda NÃO aconteceram (eventos futuros)
2. As inscrições ainda estão abertas OU ainda não foram abertas

Para cada hackathon encontrado, retorne EXATAMENTE neste formato JSON:
[
  {{
    "nome": "Nome do hackathon",
    "tema": "Tema principal",
    "quando": "Data do evento",
    "inscricoes": "Período de inscrições",
    "requisitos": "Requisitos se houver, senão 'Não informado'",
    "link": "Link para inscrição ou página oficial"
  }}
]

Se não encontrar nenhum, retorne: []
Retorne APENAS o JSON, sem texto adicional."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=SEARCH_CONFIG,
        )
        texto = response.text.strip()
        match = re.search(r'\[.*\]', texto, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception as e:
        print(f"Erro ao buscar hackathons: {e}")
        return []

# ─── HTML ─────────────────────────────────────────────────────────────────────

MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho",
            "julho","agosto","setembro","outubro","novembro","dezembro"]

def card_noticia(noticia):
    titulo  = noticia.get("titulo", "Sem título")
    fonte   = noticia.get("fonte", "")
    resumo  = noticia.get("resumo", "").replace("\n", "<br>")
    link    = noticia.get("link", "#")

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


def secao_hackathons(hackathons):
    if not hackathons:
        return ""

    cards = ""
    for h in hackathons:
        req = h.get("requisitos", "")
        req_html = f'<p style="margin:4px 0;color:#888;font-size:12px;">📋 <strong style="color:#ccc;">Requisitos:</strong> {req}</p>' if req and req != "Não informado" else ""
        cards += f"""
        <div style="background:#1a1a00;border-radius:12px;padding:20px 24px;
                    margin-bottom:16px;border-left:3px solid #FFD60A;">
          <p style="margin:0 0 6px;color:#FFD60A;font-size:11px;
                    font-weight:700;letter-spacing:1px;text-transform:uppercase;">🏆 Hackathon · Paraíba</p>
          <h3 style="margin:0 0 12px;color:#fff;font-size:17px;font-weight:700;">{h.get("nome","")}</h3>
          <p style="margin:4px 0;color:#888;font-size:12px;">🎯 <strong style="color:#ccc;">Tema:</strong> {h.get("tema","")}</p>
          <p style="margin:4px 0;color:#888;font-size:12px;">📅 <strong style="color:#ccc;">Quando:</strong> {h.get("quando","")}</p>
          <p style="margin:4px 0;color:#888;font-size:12px;">📝 <strong style="color:#ccc;">Inscrições:</strong> {h.get("inscricoes","")}</p>
          {req_html}
          <a href="{h.get("link","#")}" style="display:inline-block;margin-top:14px;
             background:#FFD60A;color:#111;font-size:12px;font-weight:700;
             padding:8px 16px;border-radius:8px;text-decoration:none;">Saiba mais →</a>
        </div>"""

    return f"""
    <div style="margin-bottom:32px;">
      <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                letter-spacing:2px;text-transform:uppercase;">🏆 Hackathons na Paraíba</p>
      {cards}
    </div>
    <hr style="border:none;border-top:1px solid #222;margin-bottom:32px;">"""


def gerar_html(noticias_ia, noticias_tech, hackathons):
    hoje = datetime.now()
    data_str = f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"

    cards_ia   = "".join(card_noticia(n) for n in noticias_ia)
    cards_tech = "".join(card_noticia(n) for n in noticias_tech)

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
          {secao_hackathons(hackathons)}

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
            Gerado por Gemini com Google Search ·
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
    print("🔍 Buscando hackathons na Paraíba...")
    hackathons = buscar_hackathons_paraiba()
    print(f"  {len(hackathons)} encontrado(s).")

    print("🤖 Buscando notícias de IA...")
    noticias_ia = buscar_noticias_gemini("inteligência artificial", 1)
    print(f"  {len(noticias_ia)} notícia(s).")

    print("💻 Buscando notícias de tecnologia...")
    noticias_tech = buscar_noticias_gemini("tecnologia", 2)
    print(f"  {len(noticias_tech)} notícia(s).")

    print("📧 Enviando email...")
    service = get_gmail_service()
    html = gerar_html(noticias_ia, noticias_tech, hackathons)
    enviar_email(service, html)
