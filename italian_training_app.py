import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import re
import sqlite3
from datetime import datetime
import random

# Télécharger les ressources NLTK
nltk.download('punkt_tab')
nltk.download('stopwords')
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

# Connexion à la base de données SQLite
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

conn.commit()

# Fonction pour récupérer un article de La Stampa
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

# Fonction pour découper le texte en phrases
def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?,]) +', text)
    return sentences

# Fonction de traduction d'une phrase
def translate_sentence(sentence):
    return GoogleTranslator(source='it', target='fr').translate(sentence)

# Vérifie si l'utilisateur a déjà passé le test aujourd'hui
def has_taken_test_today(email):
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM results WHERE email = ? AND date = ?", (email, today))
    return cursor.fetchone() is not None

# Sauvegarde des résultats du test
def save_results(email, score, words):
    date_today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO results (email, score, date) VALUES (?, ?, ?)", (email, score, date_today))
    result_id = cursor.lastrowid

    for word in words:
        cursor.execute("INSERT INTO quiz_words (result_id, word) VALUES (?, ?)", (result_id, word))

    conn.commit()

# Extraction de 10 mots aléatoires sans majuscules et stopwords
def extract_random_words(text, n=10):
    stop_words_it = set(stopwords.words('italian'))
    words = word_tokenize(text.lower())
    words = [word for word in words if word.isalpha() and word not in stop_words_it]
    return random.sample(words, n) if len(words) >= n else words

# Initialisation de la session state
if 'translations' not in st.session_state:
    st.session_state.translations = {}
    st.session_state.article = None
    st.session_state.title = ""
    st.session_state.link = ""
    st.session_state.quiz_words = []
    st.session_state.quiz_answers = {}
    st.session_state.quiz_started = False
    st.session_state.quiz_submitted = False
    st.session_state.score = 0
    st.session_state.correct_answers = {}

# Authentification par email
st.session_state.user_email = st.text_input("Entrez votre adresse email pour commencer :", key="email")

# Chargement d'un nouvel article
if st.button("Charger un nouvel article"):
    title, link, article = fetch_article()
    title_fr = translate_sentence(title)
    sentences = split_into_sentences(article)
    st.session_state.article = sentences
    st.session_state.translations = {i: None for i in range(len(sentences))}
    st.session_state.title = title
    st.session_state.title_fr = title_fr
    st.session_state.link = link

# Affichage de l'article
if st.session_state.article:
    st.title(st.session_state.title)
    st.subheader(st.session_state.title_fr)
    st.markdown(f"[Lien vers l'article]({st.session_state.link})")

    for idx, sentence in enumerate(st.session_state.article):
        cols = st.columns([2, 4])
        with cols[0]:
            if st.button(sentence, key=f"sentence_{idx}"):
                if st.session_state.translations[idx] is None:
                    st.session_state.translations[idx] = translate_sentence(sentence)
                else:
                    st.session_state.translations[idx] = None
        with cols[1]:
            translation = st.session_state.translations[idx]
            if translation:
                st.markdown(f"<p style='text-align:left; color: green;'>{translation}</p>", unsafe_allow_html=True)

    # Lancer le quiz
    if st.button("Commencer le test") and st.session_state.user_email:
        if has_taken_test_today(st.session_state.user_email):
            st.warning("Vous avez déjà passé le test aujourd'hui. Revenez demain !")
        else:
            article_text = " ".join(st.session_state.article)
            st.session_state.quiz_words = extract_random_words(article_text, 10)
            st.session_state.quiz_answers = {word: "" for word in st.session_state.quiz_words}
            st.session_state.quiz_started = True
            st.session_state.quiz_submitted = False

# Quiz : traduire les mots
if st.session_state.quiz_started and not st.session_state.quiz_submitted:
    st.header("Quiz : Traduisez ces mots en français")
    for word in st.session_state.quiz_words:
        st.session_state.quiz_answers[word] = st.text_input(f"Traduction de '{word}'", key=f"answer_{word}")

    if st.button("Résultats du test"):
        score = 0
        correct_answers = {}
        for word, user_answer in st.session_state.quiz_answers.items():
            correct_translation = translate_sentence(word).lower()
            correct_answers[word] = correct_translation
            if user_answer.strip().lower() == correct_translation:
                score += 1

        st.session_state.score = score
        st.session_state.correct_answers = correct_answers
        st.session_state.quiz_submitted = True

        # Enregistrement des résultats
        save_results(st.session_state.user_email, score, st.session_state.quiz_words)

# Résultats
if st.session_state.quiz_submitted:
    st.success(f"Votre score : {st.session_state.score}/10")
    st.subheader("Corrections :")
    for word, correct_translation in st.session_state.correct_answers.items():
        user_answer = st.session_state.quiz_answers[word]
        if user_answer.strip().lower() == correct_translation:
            st.markdown(f"✅ **{word}** : {correct_translation}")
        else:
            st.markdown(f"❌ **{word}** : {correct_translation} (Votre réponse : {user_answer})")
