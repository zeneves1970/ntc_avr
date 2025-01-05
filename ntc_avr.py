import os
import dropbox
from dropbox.exceptions import AuthError
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sqlite3
import smtplib
import requests
import urllib3

# Configurações
BASE_URL = "https://www.noticiasdeaveiro.pt/ultimos-artigos/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
DB_NAME = "seen_links.db"

# Recuperar os secrets do ambiente
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_TOKEN")

DROPBOX_PATH = f"/{DB_NAME}"

# Configurar warnings do urllib
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurando o cliente do Dropbox
def get_dropbox_client():
    """Inicializa o cliente do Dropbox com os valores do ambiente e usa o refresh_token para renovar o access_token."""
    try:
        # Usando o refresh_token para obter um novo access_token
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=APP_KEY,
            app_secret=APP_SECRET
        )
        
        # Testa a conexão com o Dropbox para garantir que o access token é válido
        user = dbx.users_get_current_account()
        print(f"[DEBUG] Conectado ao Dropbox como: {user.name.display_name}")
        return dbx
    except dropbox.exceptions.AuthError as e:
        print(f"[ERRO] Falha na autenticação do Dropbox: {e}")
        raise

# Função para baixar o banco de dados do Dropbox
def download_db_from_dropbox():
    """Faz o download do banco de dados do Dropbox."""
    try:
        dbx = get_dropbox_client()
        metadata, res = dbx.files_download(DROPBOX_PATH)
        with open(DB_NAME, "wb") as f:
            f.write(res.content)
        print("[DEBUG] Banco de dados baixado do Dropbox.")
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print("[DEBUG] Banco de dados não encontrado no Dropbox. Criando um novo.")
        else:
            print(f"[ERRO] Falha ao baixar banco de dados: {e}")

# Função para enviar o banco de dados para o Dropbox
def upload_db_to_dropbox():
    """Faz o upload do banco de dados para o Dropbox."""
    try:
        dbx = get_dropbox_client()
        with open(DB_NAME, "rb") as f:
            dbx.files_upload(f.read(), DROPBOX_PATH, mode=dropbox.files.WriteMode("overwrite"))
        print("[DEBUG] Banco de dados enviado para o Dropbox.")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar banco de dados: {e}")

# Inicializa o banco de dados
def initialize_db():
    """Cria o banco de dados e a tabela de links."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT UNIQUE NOT NULL
    )
    """)
    conn.commit()
    conn.close()

# Carrega links já processados
def load_seen_links():
    """Carrega os links já processados do banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM seen_links")
    seen_links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return seen_links

# Salva novos links
def save_seen_links(new_links):
    """Salva novos links no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO seen_links (link) VALUES (?)", [(link,) for link in new_links])
    conn.commit()
    conn.close()

# Coleta links da página principal
def get_news_links(url):
    """Busca links de notícias no site."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"[ERRO] Status {response.status_code}")
            return set()

        soup = BeautifulSoup(response.content, 'html.parser')
        links = {
            urljoin(BASE_URL, a['href'])
            for div in soup.find_all("div", class_="td-module-thumb")
            for a in div.find_all("a", href=True)
        }
        print(f"[DEBUG] Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"[ERRO] Falha ao buscar links: {e}")
        return set()

# Extrai título e URL
def get_article_title_and_url(url):
    """Extrai título e URL de uma notícia."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"[ERRO] Status {response.status_code}")
            return None, None

        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find("h1", class_="entry-title")
        return title.get_text(strip=True) if title else "Título não encontrado.", url
    except Exception as e:
        print(f"[ERRO] Falha ao processar notícia: {e}")
        return None, None

# Envia e-mail
def send_email_notification(article_title, article_url):
    """Envia notificação por e-mail."""
    subject = "Nova notícia!"
    email_text = f"""\
From: {EMAIL_USER}
To: {TO_EMAIL}
Subject: {subject}
Content-Type: text/html; charset=utf-8

<p><strong>{article_title}</strong></p>
<p>Leia o artigo completo: <a href="{article_url}" target="_blank">{article_url}</a></p>
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, TO_EMAIL, email_text.encode("utf-8"))
        print("[DEBUG] E-mail enviado.")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar e-mail: {e}")

# Monitoramento principal
def monitor_news():
    """Monitora o site e envia notificações para novos links."""
    download_db_from_dropbox()  # Baixa o banco de dados antes de iniciar
    initialize_db()  # Certifica-se de que o banco está pronto
    seen_links = load_seen_links()
    current_links = get_news_links(BASE_URL)

    new_links = set(current_links) - seen_links

    if new_links:
        print(f"[DEBUG] Novos links: {new_links}")
        for link in new_links:
            title, url = get_article_title_and_url(link)
            if title and url:
                send_email_notification(title, url)
        save_seen_links(new_links)
    else:
        print("[DEBUG] Nenhuma nova notícia.")
    
    upload_db_to_dropbox()  # Envia o banco de dados atualizado para o Dropbox

# Execução
if __name__ == "__main__":
    monitor_news()
