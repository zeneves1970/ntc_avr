import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3
from urllib.parse import urljoin

# Configurações
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
BASE_URL = "https://www.noticiasdeaveiro.pt/ultimos-artigos/"
SEEN_LINKS_NTC_FILE = "seen_links_ntc.txt"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_seen_links_ntc():
    """Carrega links já processados."""
    seen_links = set()
    try:
        if os.path.exists(SEEN_LINKS_NTC_FILE) and os.path.getsize(SEEN_LINKS_NTC_FILE) > 0:
            with open(SEEN_LINKS_NTC_FILE, "r") as file:
                seen_links = {line.strip() for line in file if line.strip()}
        print(f"[DEBUG] Links carregados: {seen_links}")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar links: {e}")
    return seen_links

def save_seen_links_ntc(seen_links_ntc):
    """Salva links processados."""
    try:
        with open(SEEN_LINKS_NTC_FILE, "w") as file:
            file.writelines(f"{link}\n" for link in sorted(seen_links_ntc))
        print(f"[DEBUG] Cache atualizada com {len(seen_links_ntc)} links.")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar links: {e}")

def get_news_links(url):
    """Busca links de notícias na página principal."""
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

def monitor_news():
    seen_links_ntc = load_seen_links_ntc()
    current_links = get_news_links(BASE_URL)
    new_links = current_links - seen_links_ntc

    if new_links:
        print(f"[DEBUG] Novos links: {new_links}")
        for link in new_links:
            title, url = get_article_title_and_url(link)
            if title and url:
                send_email_notification(title, url)
        seen_links_ntc.update(new_links)
        save_seen_links_ntc(seen_links_ntc)
    else:
        print("[DEBUG] Nenhuma nova notícia.")

if __name__ == "__main__":
    monitor_news()
