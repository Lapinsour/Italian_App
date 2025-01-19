import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import re
import sqlite3
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import random

# Télécharger les ressources NLTK
nltk.download('punkt')
nltk.download('stopwords')
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Connexion à la base SQLite
conn = sqlite3.connect('quiz_results.db')
cursor = conn.cursor()

# Création des tables si elles n'existent pas
cursor.execute("""
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    score INTEGER,
    date TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS quiz_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER,
    word TEXT,
    FOREIGN KEY (result_id) REFERENCES results(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,
    title TEXT,
    link TEXT,
    content TEXT
)
""")

conn.commit()

# Fonction pour scrapper un article (exécutée une fois par jour)
def fetch_article():
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
            if 3000 <= len(content) <= 5000:
                return title, article_url, content
    return "Aucun article trouvé.", "", ""

# Récupérer ou stocker l'article du jour
def get_daily_article():
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM daily_article WHERE date = ?", (today,))
    row = cursor.fetchone()
    if row:
        return row[1], row[2], row[3]  # title, link, content
    else:
        title, link, content = fetch_article()
        cursor.execute("INSERT INTO daily_article (date, title, link, content) VALUES (?, ?, ?, ?)",
                       (today, title, link, content))
        conn.commit()
        return title, link, content

# Fonction pour afficher les scores sous forme de graphique
def plot_scores(email):
    cursor.execute("SELECT date, score FROM results WHERE email = ? ORDER BY date", (email,))
    data = cursor.fetchall()
    if data:
        df = pd.DataFrame(data, columns=["Date", "Score"])
        plt.figure(figsize=(8, 5))
        plt.plot(df["Date"], df["Score"], marker="o", linestyle="-", color="blue")
        plt.title("Évolution des scores de quiz")
        plt.xlabel("Date")
        plt.ylabel("Score")
        plt.xticks(rotation=45)
        st.pyplot(plt)
    else:
        st.info("Aucun score enregistré pour le moment.")

# Fonction pour extraire des mots aléatoires
def extract_random_words(text, n=10):
    stop_words_it = set(stopwords.words('italian'))
    words = word_tokenize(text.lower())
    words = [word for word in words if word.isalpha() and word not in stop_words_it]
    return random.sample(words, n) if len(words) >= n else words

# Gestion des pages
st.set_page_config(layout="wide")
if 'page' not in st.session_state:
    st.session_state.page = 1
if 'article_data' not in st.session_state:
    st.session_state.article_data = None

# PAGE 1: ACCUEIL
if st.session_state.page == 1:
    st.title("Bienvenue dans l'application d'apprentissage")
    email = st.text_input("Veuillez entrer votre adresse email pour continuer :")
    if st.button("Poursuivre vers l'application"):
        st.session_state.user_email = email
        st.session_state.article_data = get_daily_article()
        st.session_state.page = 2

# PAGE 2: DASHBOARD
elif st.session_state.page == 2:
    st.title("Dashboard")
    st.header(f"Bonjour, {st.session_state.user_email}")
    st.subheader("Votre progression :")
    plot_scores(st.session_state.user_email)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Poursuivre vers l'article du jour"):
            st.session_state.page = 3
    with col2:
        if st.button("Révisions"):
            st.session_state.page = 4

# PAGE 3: ARTICLE DU JOUR
elif st.session_state.page == 3:
    title, link, content = st.session_state.article_data
    st.title(title)
    st.markdown(f"[Lire l'article original]({link})")
    st.markdown(content)

    if st.button("Lancer le quiz"):
        # Ajoute le code pour le quiz ici
        pass

# PAGE 4: RÉVISIONS
elif st.session_state.page == 4:
    st.title("Révisions")
    st.header("Liste des mots déjà rencontrés :")
    cursor.execute("""
    SELECT DISTINCT word FROM quiz_words 
    INNER JOIN results ON quiz_words.result_id = results.id
    WHERE email = ?
    """, (st.session_state.user_email,))
    words = cursor.fetchall()
    if words:
        st.write(", ".join(word[0] for word in words))
    else:
        st.info("Aucun mot enregistré pour le moment.")

    if st.button("Retour au tableau de bord"):
        st.session_state.page = 2
