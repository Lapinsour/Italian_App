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
import seaborn as sns
import matplotlib.pyplot as plt

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
def save_results(email, score, words, correct_answers):
    date_today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO results (email, score, date) VALUES (?, ?, ?)", (email, score, date_today))
    result_id = cursor.lastrowid

    for word in words:
        correct_translation = correct_answers.get(word, "")
        # Enregistrement des mots et des traductions avec le résultat Vrai/Faux
        correct = "Vrai" if correct_translation.lower() == user_answer.lower() else "Faux"
        cursor.execute("INSERT INTO librairie_mots (result_id, word, correct) VALUES (?, ?, ?)", (result_id, word, correct))

    conn.commit()




# Extraction de 20 mots aléatoires sans majuscules et stopwords, avec élimination des doublons
def extract_random_words(text, n=20):
    # Téléchargement des stopwords si nécessaire
    nltk.download('punkt')
    nltk.download('stopwords')

    stop_words_it = set(stopwords.words('italian'))
    words = word_tokenize(text.lower())

    # Filtrer les mots qui sont alphabétiques et non-stopwords
    words = [word for word in words if word.isalpha() and word not in stop_words_it]
    
    # Utiliser un set pour enlever les doublons
    unique_words = list(set(words))
    
    # Si le nombre de mots uniques est inférieur à n, retourner tous les mots uniques
    return random.sample(unique_words, n) if len(unique_words) >= n else unique_words


# Initialisation de la session state
if 'translations' not in st.session_state:
    st.session_state.translations = {}
    st.session_state.article = None
    st.session_state.title = ""
    st.session_state.link = ""
    st.session_state.librairie_mots = []
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
    st.subheader("Exerce-toi")
    # Lancer le quiz
    if st.button('Commencer le test') and st.session_state.user_email:
        if has_taken_test_today(st.session_state.user_email):
            st.warning("Vous avez déjà passé le test aujourd'hui. Revenez demain !")
        else:
            article_text = " ".join(st.session_state.article)
            st.session_state.librairie_mots = extract_random_words(article_text, 20)
            st.session_state.quiz_answers = {word: "" for word in st.session_state.librairie_mots}
            st.session_state.quiz_started = True
            st.session_state.quiz_submitted = False

# Quiz : traduire les mots
if st.session_state.quiz_started and not st.session_state.quiz_submitted:
    st.header("Quiz : Traduisez ces mots en français")
    for word in st.session_state.librairie_mots:
        st.session_state.quiz_answers[word] = st.text_input(f"Traduction de '{word}'", key=f"answer_{word}")

    if st.button('Résultats du test'):
        score = 0
        correct_answers = {}
        result_id = 1  # Exemple de récupération d'un ID de résultat. Adaptez-le selon votre logique.
        
        for word, user_answer in st.session_state.quiz_answers.items():
            correct_translation = translate_sentence(word).lower()
            correct_answers[word] = correct_translation
            
            # Déterminez si la réponse est correcte
            correct = "Vrai" if user_answer.strip().lower() == correct_translation else "Faux"
            
            # Insertion dans la base de données
            cursor.execute("""
            INSERT INTO librairie_mots (result_id, word, correct, correct_translation)
            VALUES (?, ?, ?, ?)
            """, (result_id, word, correct, correct_translation))
            
            if correct == "Vrai":
                score += 1
    
        st.session_state.score = score
        st.session_state.correct_answers = correct_answers
        st.session_state.quiz_submitted = True

        # Enregistrement des résultats
        save_results(st.session_state.user_email, score, st.session_state.librairie_mots, st.session_state.correct_answers)


# Résultats
if st.session_state.quiz_submitted:
    st.success(f"Votre score : {st.session_state.score}/20")
    st.subheader("Corrections :")
    for word, correct_translation in st.session_state.correct_answers.items():
        user_answer = st.session_state.quiz_answers[word]
        if user_answer.strip().lower() == correct_translation:
            st.markdown(f"✅ **{word}** : {correct_translation}")
        else:
            st.markdown(f"❌ **{word}** : {correct_translation} (Votre réponse : {user_answer})")




# Ajouter un bouton "Librairie" pour afficher ou masquer la liste des mots et leur traduction
if 'show_librairie' not in st.session_state:
    st.session_state.show_librairie = False  # Initialiser l'état du tableau

if st.button("Librairie"):
    # Alterner l'état d'affichage du tableau
    st.session_state.show_librairie = not st.session_state.show_librairie

# Afficher ou masquer le tableau en fonction de l'état
if st.session_state.show_librairie:
    # Récupérer les mots et leur traduction depuis la base de données
    cursor.execute("SELECT word, correct_translation FROM librairie_mots ORDER BY word")
    words = cursor.fetchall()

    # Convertir les résultats en DataFrame pour un affichage plus propre
    df_librairie = pd.DataFrame(words, columns=["Mot", "Traduction"])

    # Affichage du tableau des mots et traductions
    st.subheader("Librairie de mots et leurs traductions")
    st.dataframe(df_librairie)


# Initialiser l'état du tableau dans st.session_state
if 'show_history' not in st.session_state:
    st.session_state.show_history = False  # Initialiser à False, c'est-à-dire masqué au départ

# Affichage de l'historique
if st.button("Voir mon historique"):
    # Alterner l'état d'affichage du tableau
    st.session_state.show_history = not st.session_state.show_history

# Afficher l'historique si l'état est True
if st.session_state.show_history:
    # Récupérer les résultats de l'utilisateur depuis la base de données
    cursor.execute("SELECT date, score FROM results WHERE email = ?", (st.session_state.user_email,))
    results = cursor.fetchall()

    # Convertir les résultats en DataFrame    
    df = pd.DataFrame(results, columns=["Date", "Score"])

    # Trier par date
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")     

    # Création du graphique lineplot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["Date"], df["Score"], marker='o')
    ax.set_title("Évolution de vos scores au quiz")
    ax.set_ylim(0, 20)

    # Affichage du graphique dans Streamlit
    st.pyplot(fig)

