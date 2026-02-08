import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import re

# Télécharger les ressources NLTK
nltk.download('punkt_tab')
nltk.download('punkt')

#############################################
#        FONCTIONS DE SCRAP PAR LANGUE       #
#############################################

# ---- ITALIEN : La Stampa ----
def fetch_article_italian():
    url = "https://www.lastampa.it/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True) if '/cronaca/' in a['href']]

    for link in links:
        article_url = link if link.startswith("http") else f"https://www.lastampa.it{link}"
        article_resp = requests.get(article_url)
        article_soup = BeautifulSoup(article_resp.content, "html.parser")
        title = article_soup.find('h1').get_text(strip=True) if article_soup.find('h1') else "Titre non trouvé"

        story_div = article_soup.find('div', class_='story__text')
        if story_div:
            paragraphs = story_div.find_all('p')
            content = " ".join(p.get_text() for p in paragraphs)
            if len(content) > 500:
                return title, article_url, content
    return "Aucun article trouvé.", "", ""


# ---- FRANÇAIS : 20Minutes ----
def fetch_article_french():
    url = "https://www.france24.com/fr/france/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Récupérer les liens vers de vrais articles
    links = [
        a['href'] for a in soup.find_all('a', href=True)
        if a['href'].startswith("/fr/") and a['href'].count("-") >= 2
    ]

    for link in links:
        try:
            article_url = f"https://www.france24.com{link}"
            article_resp = requests.get(article_url)
            article_soup = BeautifulSoup(article_resp.content, "html.parser")

            title_el = article_soup.find("h1")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            paragraphs = article_soup.find_all("p")
            content = " ".join(p.get_text(strip=True) for p in paragraphs)

            if len(content) > 300:
                return title, article_url, content

        except Exception:
            pass

    return "Aucun article trouvé.", "", ""




# ---- ALLEMAND : Tagesschau ----
def fetch_article_german():
    url = "https://www.tagesschau.de"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # On récupère des liens d'articles complets
    links = [
        a['href'] for a in soup.find_all('a', href=True)
        if a['href'].startswith("/")
        and a['href'].endswith(".html")
        and "multimedia" not in a['href']
    ]

    for link in links:
        try:
            article_url = f"https://www.tagesschau.de{link}"
            article_resp = requests.get(article_url)
            article_soup = BeautifulSoup(article_resp.content, "html.parser")

            # Titre de l'article
            title_el = article_soup.find("h1")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            # Le texte de Tagesschau est dans des <p> normaux (hors chapô)
            paragraphs = [
                p.get_text(strip=True)
                for p in article_soup.find_all("p")
                if len(p.get_text(strip=True)) > 50  # éviter les brèves
            ]
            content = " ".join(paragraphs)

            # Seuil : 300 caractères minimum
            if len(content) > 300:
                return title, article_url, content

        except Exception:
            pass

    return "Aucun article trouvé.", "", ""




#############################################
#               UTILITAIRES                  #
#############################################

def split_into_sentences(text):
    return re.split(r'(?<=[.!?]) +', text)


def translate(text, src, tgt):
    return GoogleTranslator(source=src, target=tgt).translate(text)

#############################################
#               INTERFACE UI                 #
#############################################

st.title("🌍 Entraînement multilingue")
st.write("Choisissez une action :")

choice = st.selectbox(
    "Sélection",
    [
        "Charger un article en italien (→ traduction FR)",
        "Charger un article en allemand (→ traduction FR)",
        "Charger un article en français (→ traduction IT)",
        "Charger un article en français (→ traduction DE)",
    ]
)

if st.button("Charger l'article"):
    title, link, article = "", "", ""
    src, tgt = None, None

    if "italien" in choice:
        title, link, article = fetch_article_italian()
        src, tgt = "it", "fr"

    elif "allemand" in choice and "français" not in choice:
        title, link, article = fetch_article_german()
        src, tgt = "de", "fr"

    elif "français" in choice and "italien" in choice:
        title, link, article = fetch_article_20minutes()
        src, tgt = "fr", "it"

    elif "français" in choice and "allemand" in choice:
        title, link, article = fetch_article_20minutes()
        src, tgt = "fr", "de"

    # Sécurisation pour éviter le NameError
    title = title or "Titre introuvable"
    article = article or ""

    st.session_state.title = title
    st.session_state.link = link
    st.session_state.sentences = split_into_sentences(article)
    st.session_state.src = src
    st.session_state.tgt = tgt
    st.session_state.trans = {}


if "sentences" in st.session_state:
    st.header(st.session_state.title)
    st.markdown(f"[Lien vers l'article]({st.session_state.link})")

    for i, s in enumerate(st.session_state.sentences):
        if st.button(s, key=f"s_{i}"):
            if i not in st.session_state.trans:
                st.session_state.trans[i] = translate(s, st.session_state.src, st.session_state.tgt)
            else:
                del st.session_state.trans[i]
        if i in st.session_state.trans:
            st.markdown(f"<p style='color:green'>{st.session_state.trans[i]}</p>", unsafe_allow_html=True)
