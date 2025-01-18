import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import nltk
import re
import random
from nltk.corpus import stopwords

# Télécharger les ressources nécessaires
nltk.download('punkt_tab')
nltk.download('stopwords')

from nltk.tokenize import word_tokenize, sent_tokenize

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
    return "Aucun article trouvé.", "", "", ""

# Fonction pour découper le texte en phrases
def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?,]) +', text)
    return sentences

# Fonction de traduction d'une phrase
def translate_sentence(sentence):
    return GoogleTranslator(source='it', target='fr').translate(sentence)

# Fonction pour extraire des mots aléatoires de l'article (hors stopwords et noms propres)
def extract_random_words(text, n=10):
    stop_words_it = set(stopwords.words('italian'))
    words = word_tokenize(text, language='italian')
    # Exclure les stopwords et les mots commençant par une majuscule
    filtered_words = [word.lower() for word in words if word.isalpha() and word.lower() not in stop_words_it and not word[0].isupper()]
    return random.sample(filtered_words, min(n, len(filtered_words)))

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

# Bouton pour charger un nouvel article
if st.button("Charger un nouvel article"):
    title, link, article = fetch_article()
    title_fr = translate_sentence(title)
    sentences = split_into_sentences(article)
    st.session_state.article = sentences
    st.session_state.translations = {i: None for i in range(len(sentences))}
    st.session_state.title = title
    st.session_state.title_fr = title_fr
    st.session_state.link = link
    st.session_state.quiz_started = False
    st.session_state.quiz_submitted = False
    st.session_state.score = 0
    st.session_state.correct_answers = {}

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

    # Bouton pour commencer le test
    if st.button("Commencer le test") and not st.session_state.quiz_started:
        article_text = " ".join(st.session_state.article)
        st.session_state.quiz_words = extract_random_words(article_text, 10)
        st.session_state.quiz_answers = {word: "" for word in st.session_state.quiz_words}
        st.session_state.quiz_started = True
        st.session_state.quiz_submitted = False
        st.session_state.score = 0
        st.session_state.correct_answers = {}

    # Affichage du test
    if st.session_state.quiz_started:
        st.subheader("Test de vocabulaire : Traduisez les mots suivants en français")
        for word in st.session_state.quiz_words:
            st.session_state.quiz_answers[word] = st.text_input(f"Traduction de : **{word}**", key=f"answer_{word}")

        # Bouton pour soumettre les réponses
        if st.button("Résultats du test") and not st.session_state.quiz_submitted:
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

        # Affichage détaillé des résultats
        if st.session_state.quiz_submitted:
            st.success(f"Votre score : {st.session_state.score}/10")

            st.subheader("Détail des réponses :")
            for word, correct_translation in st.session_state.correct_answers.items():
                user_answer = st.session_state.quiz_answers[word].strip().lower()
                if user_answer == correct_translation:
                    st.markdown(f"✅ **{word}** → {correct_translation}", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"❌ **{word}** → Votre réponse : *{user_answer}* | **Bonne réponse :** {correct_translation}",
                        unsafe_allow_html=True
                    )