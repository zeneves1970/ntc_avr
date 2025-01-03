import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3

# Cabeçalhos HTTP padrão para requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Função para extrair texto mantendo a ordem, com formatação para listas
def extract_text_ordered(soup):
    content = []
    for element in soup.contents:
        if element.name == 'div':  # Para <div>
            content.append(element.get_text(strip=True))
        elif element.name == 'ul':  # Para listas não ordenadas
            for li in element.find_all('li', recursive=False):
                content.append(f"- {li.get_text(strip=True)}")
        elif element.name == 'ol':  # Para listas ordenadas
            for li in element.find_all('li', recursive=False):
                content.append(f"- {li.get_text(strip=True)}")
    return "\n".join(content)


# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações do e-mail
EMAIL_USER = os.getenv("EMAIL_USER")  # Recupera do Secret
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Recupera do Secret
TO_EMAIL = os.getenv("TO_EMAIL")  # Recupera do Secret

# URL da página a ser monitorada
BASE_URL = "https://www.noticiasdeaveiro.pt/ultimos-artigos/"
URL = f"{BASE_URL}"  # Página principal
SEEN_LINKS_NTC_FILE = "seen_links_ntc.txt"  # Nome do arquivo para armazenar links já vistos


# Função para carregar links já vistos de um arquivo
def load_seen_links_ntc():
    seen_links = set()
    try:
        if os.path.exists(SEEN_LINKS_NTC_FILE) and os.path.getsize(SEEN_LINKS_NTC_FILE) > 0:
            with open(SEEN_LINKS_NTC_FILE, "r") as file:
                seen_links = {line.strip() for line in file if line.strip()}
        print(f"Links carregados da cache: {seen_links}")
    except Exception as e:
        print(f"Erro ao carregar a cache de links: {e}")
    return seen_links


def save_seen_links_ntc(seen_links_ntc):
    try:
        with open(SEEN_LINKS_NTC_FILE, "w") as file:
            file.writelines(f"{link}\n" for link in sorted(seen_links_ntc))
        print("Cache atualizada com novos links.")
    except Exception as e:
        print(f"Erro ao salvar a cache: {e}")


# Função para enviar uma notificação por e-mail
def send_email_notification(article_title, article_url):
    subject = "Nova noticia!"

    # Criar o corpo do e-mail com HTML
    email_text = f"""\
From: {EMAIL_USER}
To: {TO_EMAIL}
Subject: {subject}
Content-Type: text/html; charset=utf-8
Content-Transfer-Encoding: 8bit

<p><strong>{article_title}</strong></p>
<p>Leia o artigo completo clicando no link abaixo:</p>
<p><a href="{article_url}" target="_blank">{article_url}</a></p>
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, TO_EMAIL, email_text.encode("utf-8"))
        print("E-mail enviado com sucesso.")
    except Exception as e:
        print("Erro ao enviar e-mail:", e)


# Função para buscar links de notícias da URL fornecida
from urllib.parse import urljoin

def get_news_links(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"Erro ao acessar a página: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = set()

        # Selecionar links dentro da <div class="td-module-thumb">
        for div in soup.find_all("div", class_="td-module-thumb"):
            a_tag = div.find("a", href=True)  # Encontrar a tag <a> dentro da <div>
            if a_tag:
                full_link = urljoin(BASE_URL, a_tag['href'])  # Montar a URL completa
                links.add(full_link)
        
        print(f"Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"Erro ao buscar links: {e}")
        return set()


def get_article_title_and_url(url):
    try:
        # Realiza a requisição da página da notícia
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"Erro ao acessar a notícia: {response.status_code}")
            return None, None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extrair título
        title_elem = soup.find("h1", class_="entry-title")
        title = title_elem.get_text(strip=True) if title_elem else "Título não encontrado."

        return title, url  # Retorna o título e o link da notícia
    except Exception as e:
        print(f"Erro ao processar a notícia: {e}")
        return None, None


def monitor_news():
    seen_links_ntc = load_seen_links_ntc()  # Carregar links já vistos
    current_links = get_news_links(URL)  # Obter os links atuais

    print(f"Links atuais na página: {current_links}")
    print(f"Links já vistos: {seen_links_ntc}")

    new_links = {link for link in current_links if link not in seen_links_ntc}

    if new_links:
        print(f"Novos links encontrados: {new_links}")
        for link in new_links:
            try:
                article_title, article_url = get_article_title_and_url(link)
                if article_title and article_url:
                    send_email_notification(article_title, article_url)
            except Exception as e:
                print(f"Erro ao enviar e-mail: {e}")
        seen_links_ntc.update(new_links)
        save_seen_links_ntc(seen_links_ntc)
    else:
        print("Nenhuma nova notícia para enviar e-mail.")


# Execução principal
if __name__ == "__main__":
    monitor_news()
