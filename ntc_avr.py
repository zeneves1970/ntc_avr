import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sqlite3
import smtplib
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Inicializa o banco de dados
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

# 2. Carrega links já processados
def load_seen_links():
    """Carrega os links já processados do banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM seen_links")
    seen_links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return seen_links

# 3. Salva novos links
def save_seen_links(new_links):
    """Salva novos links no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO seen_links (link) VALUES (?)", [(link,) for link in new_links])
    conn.commit()
    conn.close()

# 4. Coleta links da página principal
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

# 5. Extrai título e URL
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

# 6. Envia e-mail
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

# 7. Monitoramento principal
def monitor_news():
    """Monitora o site e envia notificações para novos links."""
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

# 8. Execução
if __name__ == "__main__":
    monitor_news()
