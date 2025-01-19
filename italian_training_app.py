import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import sqlite3
from datetime import datetime
import random

# Télécharger les ressources NLTK
nltk.download('punkt_tab')

# Connexion à la base SQLite
conn = sqlite3.connect('quiz_results.db')
cursor = conn.cursor()

# Fonction pour initialiser la base de données
def initialize_db():
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
    CREATE TABLE IF NOT EXISTS scores (
        email TEXT,
        date TEXT,
        score INTEGER
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
        link TEXT
    )
    """)
    conn.commit()
    conn.close()






# Scraper l'article (récupérer uniquement le lien et la date)
def fetch_article_link():
    url = "https://www.lastampa.it/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Filtrer les liens contenant "/cronaca/" et vérifier s'ils ont une date et un ID d'article dans l'URL
    links = [a['href'] for a in soup.find_all('a', href=True) if '/cronaca/' in a['href'] and len(a['href'].split('/')) > 4]
    
    if links:
        # Prendre le premier lien trouvé
        article_link = links[0]
        
        # Si le lien est relatif, compléter avec l'URL de base
        if article_link.startswith("/"):
            article_link = f"https://www.lastampa.it{article_link}"
        
        return article_link
    return ""


# Sauvegarder ou récupérer le lien de l'article pour la date du jour
def get_daily_article_link():
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT link FROM daily_article WHERE date = ?", (today,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        link = fetch_article_link()
        cursor.execute("INSERT INTO daily_article (date, link) VALUES (?, ?)", (today, link))
        conn.commit()
        return link

# Scraper le contenu de l'article depuis son lien
def scrape_article_content(link):
    response = requests.get(link)
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Titre non trouvé"
    story_div = soup.find('div', class_='story__text')
    paragraphs = story_div.find_all('p') if story_div else []
    content = " ".join(p.get_text() for p in paragraphs)
    return title, content

# Traduire une phrase
def translate_sentence(sentence):
    return GoogleTranslator(source='it', target='fr').translate(sentence)

# Vérifier si l'user a déjà passé le test aujourd'hui
def has_taken_test_today(email):
    """
    Vérifie si un utilisateur a déjà passé le test aujourd'hui.
    :param email: Email de l'utilisateur.
    :return: True si le test a été passé aujourd'hui, False sinon.
    """
    connection = sqlite3.connect("quiz_results.db")
    cursor = connection.cursor()
    
    today = datetime.now().date().isoformat()

    # Rechercher si l'utilisateur a un score enregistré pour aujourd'hui
    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM scores 
        WHERE email = ? AND date = ?
        """, 
        (email, today)
    )
    result = cursor.fetchone()[0]

    connection.close()
    return result > 0

# Gestion des pages
st.set_page_config(layout="wide")
if 'page' not in st.session_state:
    st.session_state.page = 1
    st.session_state.article = None
    st.session_state.title = None
    st.session_state.translations = []
    st.session_state.link = None
    st.session_state.title_fr = None

initialize_db()
# PAGE 1: ACCUEIL
if st.session_state.page == 1:
    
    st.title("Bienvenue dans l'application d'apprentissage")
    email = st.text_input("Veuillez entrer votre adresse email pour continuer :")
    if st.button("Poursuivre vers l'application"):
        st.session_state.user_email = email
        st.session_state.link = get_daily_article_link()
        st.session_state.page = 2

# PAGE 2: DASHBOARD
elif st.session_state.page == 2:
    st.title("Dashboard")
    st.header(f"Bonjour, {st.session_state.user_email}")
    st.subheader("Votre progression :")
    st.info("Graphique des scores à ajouter ici.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Poursuivre vers l'article du jour"):
            st.session_state.page = 3
    with col2:
        if st.button("Révisions"):
            st.session_state.page = 4

# PAGE 3: ARTICLE DU JOUR
elif st.session_state.page == 3:
    # Scraping et initialisation si nécessaire
    if st.session_state.article is None:
        title, content = scrape_article_content(st.session_state.link)
        sentences = nltk.sent_tokenize(content)

        if not sentences:
            st.error("Le contenu de l'article n'a pas pu être chargé.")
        else:
            st.session_state.article = sentences
            st.session_state.title = title
            st.session_state.translations = [None] * len(sentences)
            st.session_state.title_fr = translate_sentence(title)

    # Affichage du titre et lien vers l'article
    st.title(st.session_state.title or "Titre non disponible")
    st.subheader(st.session_state.title_fr or "Traduction indisponible")
    st.markdown(f"[Lien vers l'article]({st.session_state.link})")

    # Affichage des phrases découpées sous forme de boutons
    if st.session_state.article:
        for idx, sentence in enumerate(st.session_state.article):
            cols = st.columns([2, 4])  # Colonne pour le bouton et pour la traduction
            with cols[0]:
                # Bouton pour afficher ou cacher la traduction
                if st.button(sentence, key=f"sentence_{idx}"):
                    if st.session_state.translations[idx] is None:
                        st.session_state.translations[idx] = translate_sentence(sentence)
                    else:
                        st.session_state.translations[idx] = None
            with cols[1]:
                # Affichage de la traduction si disponible
                translation = st.session_state.translations[idx]
                if translation:
                    st.markdown(
                        f"<p style='text-align:left; color: green;'>{translation}</p>",
                        unsafe_allow_html=True,
                    )
    else:
        st.warning("Aucune phrase à afficher pour cet article.")

   

    # Bouton pour accéder au quiz
    if st.button("Lancer le quiz"):
        st.session_state.page = 5

# PAGE 4: RÉVISIONS
# Vérifier si l'utilisateur a déjà pris le test aujourd'hui
if has_taken_test_today(st.session_state.user_email):
    st.warning("Vous avez déjà passé le test aujourd'hui. Revenez demain !")
    st.session_state.page = 2
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
        
# PAGE 5: QUIZZ
elif st.session_state.page == 5:
    # Vérification si l'utilisateur peut passer le quiz
    st.header("Quiz : Traduisez ces mots en français")
    if not st.session_state.user_email:
        st.warning("Veuillez entrer votre adresse email sur la page d'accueil pour accéder au quiz.")
        st.button("Retour à l'accueil", on_click=lambda: setattr(st.session_state, "page", 1))
    elif has_taken_test_today(st.session_state.user_email):
        st.warning("Vous avez déjà passé le test aujourd'hui. Revenez demain !")
        st.button("Retour à la page 2", on_click=lambda: setattr(st.session_state, "page", 2))
    else:
        # Initialisation du quiz
        if not st.session_state.quiz_started:
            article_text = " ".join(st.session_state.article or [])
            st.session_state.quiz_words = extract_random_words(article_text, 10)
            st.session_state.quiz_answers = {word: "" for word in st.session_state.quiz_words}
            st.session_state.quiz_started = True
            st.session_state.quiz_submitted = False

        # Affichage des questions du quiz
        if not st.session_state.quiz_submitted:
            for word in st.session_state.quiz_words:
                st.session_state.quiz_answers[word] = st.text_input(
                    f"Traduction de '{word}'", key=f"answer_{word}"
                )

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

        # Affichage des résultats du quiz
        if st.session_state.quiz_submitted:
            st.success(f"Votre score : {st.session_state.score}/10")
            st.write("Réponses correctes :")
            for word, correct_answer in st.session_state.correct_answers.items():
                st.write(f"{word}: {correct_answer}")

            st.button("Retour au tableau de bord", on_click=lambda: setattr(st.session_state, "page", 2))

# Fermeture de la connexion à la base de données
conn.close()
