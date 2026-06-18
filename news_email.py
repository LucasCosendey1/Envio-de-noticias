import base64
import os
import re
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

from google import genai
from google.genai import types
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Configuração ─────────────────────────────────────────────────────────────

NEWSAPI_KEY       = os.environ["NEWSAPI_KEY"]
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
DESTINATARIO      = os.environ.get("EMAIL_DESTINATARIO", "lukecosendey@gmail.com")
REMETENTE         = os.environ.get("EMAIL_REMETENTE", "honeylabsai@gmail.com")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

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

# ─── NewsAPI ──────────────────────────────────────────────────────────────────

def buscar_noticias(query, count=1):
    """Busca artigos por query."""
    params = {
        "q": query,
        "language": "pt",
        "sortBy": "publishedAt",
        "pageSize": count,
        "apiKey": NEWSAPI_KEY,
    }
    res = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
    res.raise_for_status()
    data = res.json()
    if data["status"] != "ok":
        raise RuntimeError(f"NewsAPI erro: {data}")
    return data["articles"]

# ─── Gemini ───────────────────────────────────────────────────────────────────

def extrair_texto_pagina(url):
    """Baixa a página e extrai o texto principal."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Remove elementos desnecessários
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Pega parágrafos com conteúdo relevante
        paragrafos = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 80]
        texto = "\n".join(paragrafos[:30])  # máximo 30 parágrafos
        return texto[:6000]  # limita para não estourar o contexto do Gemini
    except Exception as e:
        return ""


def resumir_artigo(titulo, descricao, url):
    """Baixa a página e usa Gemini para resumir o conteúdo real."""
    texto_pagina = extrair_texto_pagina(url)

    if texto_pagina:
        conteudo = f"Conteúdo da página:\n{texto_pagina}"
    else:
        conteudo = f"Descrição: {descricao}"

    prompt = f"""Leia o conteúdo abaixo e escreva um resumo em português com no máximo 2 parágrafos curtos.
Seja objetivo e direto. Não use markdown, apenas texto simples.

Título: {titulo}
{conteudo}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return descricao or "Resumo não disponível."


def buscar_hackathons_paraiba():
    """Usa Gemini com Google Search para buscar hackathons na Paraíba."""
    import json, re
    prompt = """Pesquise na internet sobre hackathons na Paraíba (Brasil) que:
1. Ainda NÃO aconteceram (eventos futuros)
2. As inscrições ainda estão abertas OU ainda não foram abertas

Para cada hackathon encontrado, retorne EXATAMENTE neste formato JSON (lista):
[
  {
    "nome": "Nome do hackathon",
    "tema": "Tema principal",
    "quando": "Data do evento",
    "inscricoes": "Período de inscrições",
    "requisitos": "Requisitos se houver, ou 'Não informado'",
    "link": "Link para inscrição ou página oficial"
  }
]

Se não encontrar nenhum hackathon futuro relevante, retorne: []
Retorne APENAS o JSON, sem texto adicional."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
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

def card_noticia(artigo, resumo):
    titulo    = artigo.get("title", "Sem título") or "Sem título"
    url       = artigo.get("url", "#") or "#"
    fonte     = artigo.get("source", {}).get("name", "") or ""
    pub_raw   = artigo.get("publishedAt", "")
    try:
        pub = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
        pub_str = pub.strftime("%d/%m %H:%M")
    except Exception:
        pub_str = ""

    resumo_html = resumo.replace("\n", "<br>")

    return f"""
    <div style="background:#111;border-radius:12px;padding:20px 24px;
                margin-bottom:16px;border-left:3px solid #FFD60A;">
      <p style="margin:0 0 4px;color:#FFD60A;font-size:11px;
                font-weight:700;letter-spacing:1px;text-transform:uppercase;">
        {fonte}{' · ' + pub_str if pub_str else ''}
      </p>
      <a href="{url}" style="text-decoration:none;">
        <h3 style="margin:0 0 10px;color:#fff;font-size:16px;
                   font-weight:700;line-height:1.4;">{titulo}</h3>
      </a>
      <p style="margin:0;color:#aaa;font-size:13px;line-height:1.7;">{resumo_html}</p>
    </div>"""


def secao_hackathons(hackathons):
    if not hackathons:
        return ""

    cards = ""
    for h in hackathons:
        req = h.get("requisitos", "Não informado")
        req_html = f'<p style="margin:4px 0;color:#888;font-size:12px;">📋 <strong style="color:#ccc;">Requisitos:</strong> {req}</p>' if req and req != "Não informado" else ""
        cards += f"""
        <div style="background:#1a1a00;border-radius:12px;padding:20px 24px;
                    margin-bottom:16px;border-left:3px solid #FFD60A;">
          <p style="margin:0 0 6px;color:#FFD60A;font-size:11px;
                    font-weight:700;letter-spacing:1px;text-transform:uppercase;">
            🏆 Hackathon · Paraíba
          </p>
          <h3 style="margin:0 0 12px;color:#fff;font-size:17px;font-weight:700;">
            {h.get("nome", "")}
          </h3>
          <p style="margin:4px 0;color:#888;font-size:12px;">🎯 <strong style="color:#ccc;">Tema:</strong> {h.get("tema", "")}</p>
          <p style="margin:4px 0;color:#888;font-size:12px;">📅 <strong style="color:#ccc;">Quando:</strong> {h.get("quando", "")}</p>
          <p style="margin:4px 0;color:#888;font-size:12px;">📝 <strong style="color:#ccc;">Inscrições:</strong> {h.get("inscricoes", "")}</p>
          {req_html}
          <a href="{h.get("link", "#")}" style="display:inline-block;margin-top:14px;
             background:#FFD60A;color:#111;font-size:12px;font-weight:700;
             padding:8px 16px;border-radius:8px;text-decoration:none;">
            Saiba mais →
          </a>
        </div>"""

    return f"""
    <div style="margin-bottom:32px;">
      <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                letter-spacing:2px;text-transform:uppercase;">
        🏆 Hackathons na Paraíba
      </p>
      {cards}
    </div>
    <hr style="border:none;border-top:1px solid #222;margin-bottom:32px;">"""


def gerar_html(artigo_ia, resumo_ia, artigos_tech, resumos_tech, hackathons):
    hoje = datetime.now()
    data_str = f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"

    card_ia = card_noticia(artigo_ia, resumo_ia)
    cards_tech = "".join(card_noticia(a, r) for a, r in zip(artigos_tech, resumos_tech))

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

        <!-- Header -->
        <tr><td style="background:#111;border-radius:16px 16px 0 0;
                       padding:32px 40px;border-bottom:2px solid #FFD60A;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <p style="margin:0;color:#FFD60A;font-size:11px;font-weight:700;
                          letter-spacing:3px;text-transform:uppercase;">Honey Labs</p>
                <h1 style="margin:8px 0 0;color:#fff;font-size:24px;font-weight:700;">
                  📰 Notícias do dia
                </h1>
              </td>
              <td align="right">
                <div style="background:#FFD60A;border-radius:12px;padding:10px 16px;">
                  <p style="margin:0;color:#111;font-size:11px;font-weight:700;">{data_str}</p>
                </div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:#111;padding:32px 40px;">

          {secao_hackathons(hackathons)}

          <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                    letter-spacing:2px;text-transform:uppercase;">🤖 Inteligência Artificial</p>
          {card_ia}

          <hr style="border:none;border-top:1px solid #222;margin:24px 0;">

          <p style="margin:0 0 16px;color:#FFD60A;font-size:12px;font-weight:700;
                    letter-spacing:2px;text-transform:uppercase;">💻 Tecnologia</p>
          {cards_tech}

        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#0d0d0d;border-radius:0 0 16px 16px;
                       padding:20px 40px;border-top:1px solid #1a1a1a;">
          <p style="margin:0;color:#444;font-size:12px;">
            Resumos gerados por Gemini · Notícias via NewsAPI ·
            <a href="https://www.honeylabs.com.br" style="color:#FFD60A;text-decoration:none;">
              Honey Labs
            </a>
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
    print(f"  {len(hackathons)} hackathon(s) encontrado(s).")

    print("📰 Buscando notícias de IA...")
    artigos_ia = buscar_noticias("inteligencia artificial brasil", count=1)
    artigo_ia = artigos_ia[0] if artigos_ia else {}

    print("📰 Buscando notícias de tecnologia...")
    artigos_tech = buscar_noticias("tecnologia brasil", count=2)

    print("✍️  Resumindo artigos com Gemini...")
    resumo_ia = resumir_artigo(
        artigo_ia.get("title", ""),
        artigo_ia.get("description", ""),
        artigo_ia.get("url", ""),
    ) if artigo_ia else ""

    resumos_tech = [
        resumir_artigo(a.get("title", ""), a.get("description", ""), a.get("url", ""))
        for a in artigos_tech
    ]

    print("📧 Montando e enviando email...")
    service = get_gmail_service()
    html = gerar_html(artigo_ia, resumo_ia, artigos_tech, resumos_tech, hackathons)
    enviar_email(service, html)
