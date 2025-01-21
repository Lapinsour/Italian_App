import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import re
import sqlite3
from datetime import datetime
import random
import pandas as pd
import matplotlib.pyplot as plt

# Télécharger les ressources NLTK
nltk.download('punkt')
nltk.download('stopwords')
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

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
CREATE TABLE IF NOT EXISTS librairie_mots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER,
    word TEXT,
    correct TEXT,
    correct_translation TEXT,
    FOREIGN KEY (result_id) REFERENCES results(id)
)
""")

conn.commit()

# Fonction pour récupérer le poème
def fetch_poem():
    url = "https://www.wikipoesia.it/wiki/%27A_Mamma_(La_Mamma)"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Récupérer le titre
    title = soup.find('h1', class_='firstHeading').get_text(strip=True)

    # Récupérer le contenu du poème
    content_div = soup.find('div', class_='mw-parser-output')
    if content_div:
        paragraphs = content_div.find_all('p', recursive=False)
        content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        if content:
            return title, url, content

    return "Poème non trouvé.", "", ""

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
def save_results(email, score, words, correct_answers):
    date_today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO results (email, score, date) VALUES (?, ?, ?)", (email, score, date_today))
    result_id = cursor.lastrowid

    for word, correct_translation in correct_answers.items():
        correct = "Vrai" if correct_translation.lower() == words[word].strip().lower() else "Faux"
        cursor.execute("INSERT INTO librairie_mots (result_id, word, correct, correct_translation) VALUES (?, ?, ?, ?)",
                       (result_id, word, correct, correct_translation))

    conn.commit()

# Extraction de mots aléatoires
def extract_random_words(text, n=20):
    stop_words_it = set(stopwords.words('italian'))
    words = word_tokenize(text.lower())

    # Filtrer les mots alphabétiques non-stopwords
    words = [word for word in words if word.isalpha() and word not in stop_words_it]
    unique_words = list(set(words))
    return random.sample(unique_words, min(n, len(unique_words)))

# Initialisation de la session state
if 'state' not in st.session_state:
    st.session_state.state = {
        'translations': {},
        'article': None,
        'title': "",
        'link': "",
        'librairie_mots': [],
        'quiz_answers': {},
        'quiz_started': False,
        'quiz_submitted': False,
        'score': 0,
        'correct_answers': {},
    }

# Authentification par email
email = st.text_input("Entrez votre adresse email pour commencer :")

# Chargement d'un nouvel article
if st.button("Charger un nouvel article"):
    title, url, content = fetch_poem()
    if content:
        st.session_state.state['article'] = split_into_sentences(content)
        st.session_state.state['title'] = title
        st.session_state.state['link'] = url

# Affichage de l'article
if st.session_state.state['article']:
    st.title(st.session_state.state['title'])
    st.markdown(f"[Lien vers l'article]({st.session_state.state['link']})")

    for idx, sentence in enumerate(st.session_state.state['article']):
        translation = st.session_state.state['translations'].get(idx, None)
        cols = st.columns([2, 4])
        with cols[0]:
            if st.button(sentence, key=f"sentence_{idx}"):
                if translation is None:
                    st.session_state.state['translations'][idx] = translate_sentence(sentence)
                else:
                    st.session_state.state['translations'][idx] = None
        with cols[1]:
            if translation:
                st.markdown(f"<p style='color: green;'>{translation}</p>", unsafe_allow_html=True)

# Quiz
if st.button("Commencer le test") and email:
    if has_taken_test_today(email):
        st.warning("Vous avez déjà passé le test aujourd'hui. Revenez demain !")
    else:
        article_text = " ".join(st.session_state.state['article'])
        st.session_state.state['librairie_mots'] = extract_random_words(article_text, 20)
        st.session_state.state['quiz_answers'] = {word: "" for word in st.session_state.state['librairie_mots']}
        st.session_state.state['quiz_started'] = True

if st.session_state.state['quiz_started']:
    st.header("Quiz : Traduisez ces mots en français")
    for word in st.session_state.state['librairie_mots']:
        st.session_state.state['quiz_answers'][word] = st.text_input(f"Traduction de '{word}'", key=f"answer_{word}")

    if st.button("Résultats du test"):
        score = 0
        correct_answers = {}
        for word, user_answer in st.session_state.state['quiz_answers'].items():
            correct_translation = translate_sentence(word).lower()
            correct_answers[word] = correct_translation
            if user_answer.strip().lower() == correct_translation:
                score += 1

        st.session_state.state['score'] = score
        st.session_state.state['correct_answers'] = correct_answers
        st.session_state.state['quiz_submitted'] = True

        save_results(email, score, st.session_state.state['librairie_mots'], correct_answers)

if st.session_state.state['quiz_submitted']:
    st.success(f"Votre score : {st.session_state.state['score']}/20")
    st.subheader("Corrections :")
    for word, correct_translation in st.session_state.state['correct_answers'].items():
        user_answer = st.session_state.state['quiz_answers'][word]
        if user_answer.strip().lower() == correct_translation:
            st.markdown(f"✅ **{word}** : {correct_translation}")
        else:
            st.markdown(f"❌ **{word}** : {correct_translation} (Votre réponse : {user_answer})")
