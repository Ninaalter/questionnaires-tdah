# -*- coding: utf-8 -*-
"""
Application de questionnaires TDAH - Méthode Plasticine
Version scientifiquement validée avec ASRS v1.1
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os

st.set_page_config(
    page_title="Questionnaire TDAH - ASRS v1.1",
    page_icon="🧠",
    layout="centered"
)

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ Fichier config.json introuvable !")
        return None

def connect_to_gsheet():
    try:
        if 'gsheet_credentials' in st.secrets:
            credentials_dict = dict(st.secrets['gsheet_credentials'])
        else:
            st.warning("⚠️ Pas de connexion Google Sheets configurée.")
            return None
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
        client = gspread.authorize(credentials)
        sheet_url = st.secrets.get('gsheet_url', '')
        if sheet_url:
            return client.open_by_url(sheet_url)
        else:
            st.warning("⚠️ URL Google Sheet non configurée.")
            return None
    except Exception as e:
        st.warning(f"⚠️ Erreur de connexion Google Sheets: {str(e)}")
        return None

def save_to_gsheet(spreadsheet, worksheet_name, data):
    try:
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="50")
            worksheet.append_row(list(data.keys()))
        worksheet.append_row(list(data.values()))
        return True
    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
        return False

def calculer_score_asrs(responses, config):
    seuils_a = config.get('seuils_partie_a', [2, 3, 2, 2, 3, 3])
    score_partie_a = 0
    items_positifs_a = 0
    for i in range(6):
        score_i = responses.get(f'Q{i+1}', 0)
        score_partie_a += score_i
        if score_i >= seuils_a[i]:
            items_positifs_a += 1
    score_partie_b = 0
    items_positifs_b = 0
    for i in range(6, 18):
        score_i = responses.get(f'Q{i+1}', 0)
        score_partie_b += score_i
        if score_i >= 3:
            items_positifs_b += 1
    score_total = score_partie_a + score_partie_b
    return {
        'score_total': score_total,
        'score_max': 72,
        'score_partie_a': score_partie_a,
        'score_partie_b': score_partie_b,
        'items_positifs_a': items_positifs_a,
        'items_positifs_b': items_positifs_b,
        'screening_positif': items_positifs_a >= 4
    }

def show_consent_form(config):
    st.title("📋 Consentement éclairé")
    st.markdown(config['consentement']['texte'])
    with st.form("consent_form"):
        st.subheader("Vos informations")
        email = st.text_input("Email (optionnel, pour recevoir les résultats)")
        age = st.number_input("Âge", min_value=5, max_value=100, value=25)
        genre = st.selectbox("Genre", ["Femme", "Homme"])
        st.markdown("---")
        consent = st.checkbox("✅ J'ai lu et j'accepte les conditions ci-dessus")
        submitted = st.form_submit_button("Continuer vers le questionnaire")
        if submitted:
            if not consent:
                st.error("❌ Vous devez accepter le consentement pour continuer")
            else:
                st.session_state['consented'] = True
                st.session_state['email'] = email
                st.session_state['age'] = age
                st.session_state['genre'] = genre
                st.session_state['consent_date'] = datetime.now().isoformat()
                st.success("✅ Consentement enregistré !")
                st.rerun()

def show_questionnaire(config, questionnaire_type):
    if questionnaire_type == "pre":
        title = "📝 Questionnaire PRÉ-intervention - ASRS v1.1"
        subtitle = "Évaluation AVANT de commencer la méthode"
        questions = config['questionnaire_pre']['questions']
    elif questionnaire_type == "post":
        title = "📝 Questionnaire POST-intervention - ASRS v1.1"
        subtitle = "Évaluation APRÈS avoir suivi la méthode"
        questions = config['questionnaire_post']['questions']
    else:
        title = "📝 Questionnaire rétrospectif - ASRS v1.1"
        subtitle = "Pour les personnes ayant déjà suivi la méthode"
        questions = config['questionnaire_retrospectif']['questions']
    st.title(title)
    st.caption(subtitle)
    st.info("📌 **Important** : Répondez en pensant aux 6 derniers mois.")
    echelle = config['echelle_likert']

    with st.form("questionnaire_form"):
        responses = {}
        st.markdown("### Questions 1 à 6")
        for i in range(6):
            st.markdown(f"**{i+1}. {questions[i]}**")
            responses[f"Q{i+1}"] = st.radio(f"q{i+1}", range(len(echelle)),
                format_func=lambda x: echelle[x], key=f"q_{i+1}", label_visibility="collapsed")
            responses[f"Q{i+1}_text"] = questions[i]
        st.markdown("---")
        st.markdown("### Questions 7 à 18")
        for i in range(6, 18):
            st.markdown(f"**{i+1}. {questions[i]}**")
            responses[f"Q{i+1}"] = st.radio(f"q{i+1}", range(len(echelle)),
                format_func=lambda x: echelle[x], key=f"q_{i+1}", label_visibility="collapsed")
            responses[f"Q{i+1}_text"] = questions[i]
        if questionnaire_type in ["post", "retrospectif"]:
            st.markdown("---")
            satisfaction = st.slider("Niveau de satisfaction global", 0, 10, 5)
            responses['satisfaction'] = satisfaction
            if questionnaire_type == "retrospectif":
                responses['amelioration_percue'] = st.select_slider(
                    "Par rapport à AVANT la méthode, mes symptômes se sont...",
                    options=["Beaucoup aggravés", "Un peu aggravés", "Pas changés",
                             "Un peu améliorés", "Beaucoup améliorés"])
            responses['commentaires'] = st.text_area("Commentaires libres (optionnel)")
        submitted = st.form_submit_button("📨 Envoyer les réponses")
        if submitted:
            scores = calculer_score_asrs(responses, config)
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'type_questionnaire': questionnaire_type,
                'email': st.session_state.get('email', ''),
                'age': st.session_state.get('age', ''),
                'genre': st.session_state.get('genre', ''),
                **{k: v for k, v in scores.items()},
                'score_pourcentage': round((scores['score_total'] / 72) * 100, 1)
            }
            save_data.update(responses)
            spreadsheet = connect_to_gsheet()
            if spreadsheet:
                save_to_gsheet(spreadsheet, questionnaire_type.upper(), save_data)
                st.success("✅ Réponses enregistrées !")
            st.metric("Score total", f"{scores['score_total']}/72")
            if scores['screening_positif']:
                st.warning(f"Symptômes marqués ({scores['items_positifs_a']}/6 items Partie A)")
            else:
                st.success(f"Symptômes légers à modérés ({scores['items_positifs_a']}/6 items Partie A)")


# ─── Questionnaire Profil Atypique - Betty Rossitto ───

QUESTIONS_PROFIL_ATYPIQUE = [
    "À quelle fréquence avez-vous l'impression d'être présente physiquement, mais absente mentalement ?",
    "À quelle fréquence vous arrive-t-il de vous sentir coupée de vous-même, comme si votre esprit se déconnectait ?",
    "À quelle fréquence avez-vous le sentiment d'être en décalage avec les autres, sans vraiment savoir pourquoi ?",
    "À quelle fréquence vous arrive-t-il d'observer les interactions sociales sans les comprendre spontanément ?",
    "À quelle fréquence ressentez-vous le besoin de réfléchir à ce que vous devez dire ou faire pour être « comme il faut » ?",
    "À quelle fréquence les interactions sociales vous demandent-elles beaucoup d'énergie, même lorsqu'elles semblent simples ?",
    "À quelle fréquence ressentez-vous un besoin important de calme, de solitude ou de retrait pour récupérer ?",
    "À quelle fréquence avez-vous du mal à savoir par quoi commencer lorsque plusieurs choses sont à faire ?",
    "À quelle fréquence restez-vous bloquée face à une tâche, même si vous savez qu'elle est importante ?",
    "À quelle fréquence faites-vous des listes ou des plannings sans réussir à les suivre réellement ?",
    "À quelle fréquence avez-vous l'impression de mal gérer votre temps au quotidien ?",
    "À quelle fréquence vous arrive-t-il de sous-estimer le temps nécessaire pour vous préparer ou arriver à un rendez-vous ?",
    "À quelle fréquence êtes-vous distraite par une information ou une action secondaire, au point d'oublier ce que vous étiez en train de faire ?",
    "À quelle fréquence perdez-vous le fil de votre pensée ou de votre action lorsque vous êtes interrompue ?",
    "À quelle fréquence ressentez-vous un brouillard mental, une sensation de flou ou de confusion intérieure ?",
    "À quelle fréquence avez-vous du mal à établir des priorités claires dans votre quotidien ?",
    "À quelle fréquence vous arrive-t-il de vous sentir submergée lorsque plusieurs sollicitations arrivent en même temps ?",
    "À quelle fréquence vous arrive-t-il de « bloquer » ou de ne plus savoir quoi faire dans certaines situations ?",
    "À quelle fréquence avez-vous l'impression de vivre à côté de votre vie, sans parvenir à passer à l'action comme vous le souhaiteriez ?",
    "À quelle fréquence ressentez-vous que vous faites beaucoup d'efforts pour paraître normale ou adaptée aux autres ?",
    "À quelle fréquence certaines remarques ou émotions provoquent-elles chez vous une coupure, un vide ou un silence mental ?",
    "À quelle fréquence avez-vous le sentiment que, même en comprenant vos difficultés, vous n'arrivez pas à les changer ?",
]

ECHELLE_PROFIL = ["Pas du tout", "Rarement", "Parfois", "Souvent", "Très souvent"]


def afficher_analyse_profil_atypique(score_total):
    """Affiche l'analyse détaillée du score Profil Atypique selon les niveaux de Betty Rossitto."""
    score_max = 88
    pct = round((score_total / score_max) * 100, 1)

    st.markdown("---")
    st.markdown("### 📊 Analyse de votre profil")
    st.markdown(f"**Score total : {score_total} / {score_max}** ({pct}%)")
    st.progress(score_total / score_max)

    if score_total <= 29:
        st.success("""
### 🟢 Profil stable (0 à 29)

**Votre fonctionnement est globalement fluide.**

Les difficultés existent mais restent ponctuelles.
Vous parvenez à vous organiser et à passer à l'action.
Le décalage ou le brouillard ne prennent pas le dessus.

**Ce que ça veut dire :**
Vous avez des ajustements à faire, mais votre structure interne est déjà présente.
""")
    elif score_total <= 59:
        st.warning("""
### 🟠 Profil en tension (30 à 59)

**Votre fonctionnement demande beaucoup d'efforts.**

Vous compensez en permanence.
Vous savez ce qu'il faut faire… mais vous n'y arrivez pas toujours.
Le brouillard mental et la surcharge apparaissent régulièrement.

**Ce que ça veut dire :**
Vous êtes dans une adaptation permanente.
Cela fonctionne… mais au prix d'une fatigue importante.
""")
    else:
        st.error("""
### 🔴 Profil en surcharge (60 à 88)

**Votre fonctionnement est en difficulté profonde.**

Brouillard mental fréquent.
Difficulté à passer à l'action.
Sentiment de décalage important.
Freeze, confusion, perte de repères.

**Ce que ça veut dire :**
Votre système ne manque pas de capacités.
Il manque de structure interne pour fonctionner.
""")


def show_questionnaire_profil_atypique():
    st.title("📝 Questionnaire Profil Atypique")
    st.caption("Questionnaire développé par Betty Rossitto — contact : bethisabea.rossitto@gmail.com")
    st.info("📌 Répondez en pensant à votre quotidien habituel. Il n'y a pas de bonnes ou mauvaises réponses.")

    with st.form("questionnaire_profil_atypique"):
        responses = {}
        for i, question in enumerate(QUESTIONS_PROFIL_ATYPIQUE):
            st.markdown(f"**{i+1}. {question}**")
            responses[f"PA_Q{i+1}"] = st.radio(
                f"pa_q{i+1}", range(len(ECHELLE_PROFIL)),
                format_func=lambda x: ECHELLE_PROFIL[x],
                key=f"pa_{i+1}", label_visibility="collapsed")
            responses[f"PA_Q{i+1}_text"] = question
        submitted = st.form_submit_button("📨 Envoyer les réponses")

        if submitted:
            score_total = sum(responses[f"PA_Q{i+1}"] for i in range(len(QUESTIONS_PROFIL_ATYPIQUE)))
            score_max = len(QUESTIONS_PROFIL_ATYPIQUE) * 4
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'type_questionnaire': 'profil_atypique',
                'email': st.session_state.get('email', ''),
                'age': st.session_state.get('age', ''),
                'genre': st.session_state.get('genre', ''),
                'score_total': score_total,
                'score_max': score_max,
                'score_pourcentage': round((score_total / score_max) * 100, 1)
            }
            save_data.update(responses)
            spreadsheet = connect_to_gsheet()
            if spreadsheet:
                save_to_gsheet(spreadsheet, "PROFIL_ATYPIQUE", save_data)
                st.success("✅ Réponses enregistrées !")
            afficher_analyse_profil_atypique(score_total)


def main():
    config = load_config()
    if not config:
        st.stop()
    st.sidebar.title("🧠 Navigation")
    if 'consented' not in st.session_state:
        st.session_state['consented'] = False
    if not st.session_state['consented']:
        page = "Consentement"
    else:
        page = st.sidebar.radio(
            "Choisissez votre questionnaire :",
            [
                "Consentement",
                "PRÉ-intervention (nouveaux clients)",
                "POST-intervention (après la méthode)",
                "Rétrospectif (anciens clients)",
                "Profil Atypique (Betty Rossitto)",
            ]
        )
    if page == "Consentement" or not st.session_state['consented']:
        show_consent_form(config)
    elif page == "PRÉ-intervention (nouveaux clients)":
        show_questionnaire(config, "pre")
    elif page == "POST-intervention (après la méthode)":
        show_questionnaire(config, "post")
    elif page == "Rétrospectif (anciens clients)":
        show_questionnaire(config, "retrospectif")
    elif page == "Profil Atypique (Betty Rossitto)":
        show_questionnaire_profil_atypique()
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 Méthode d'intégration multisensorielle")
    st.sidebar.caption("Version 1.0 - 2025")

if __name__ == "__main__":
    main()
