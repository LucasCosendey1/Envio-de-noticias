"""
Execute este script UMA VEZ localmente para gerar o token.json.
O conteúdo do token.json deve ser colado no secret GMAIL_TOKEN_JSON do GitHub.

Uso:
    pip install google-auth-oauthlib
    python gerar_token.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("\ntoken.json gerado com sucesso!")
print("Copie o conteúdo abaixo e cole no secret GMAIL_TOKEN_JSON do GitHub:\n")
print(open("token.json").read())
