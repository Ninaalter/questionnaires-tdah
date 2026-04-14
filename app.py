"""
Application de questionnaires TDAH - Methode Plasticine
Version scientifiquement validee avec ASRS v1.1
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
        st.error("Fichier config.json introuvable !")
        return None

def connect_to_gsheet():
    try:
        if 'gsheet_credentials' in st.secrets:
            credentials_dict = dict(st.secrets['gsheet_credentials'])
        else:
            st.warning("Pas de connexion Google Sheets configuree.")
            return None
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
        client = gspread.authorize(credentials)
        sheet_url = st.secrets.get('gsheet_url', '')
        if sheet_url:
            return client.open_by_url(sheet_url)
        else:
            st.warning("URL Google Sheet non configuree.")
            return None
    except Exception as e:
        st.warning(f"Erreur de connexion Google Sheets: {str(e)}")
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
        st.error(f"Erreur lors de la sauvegarde: {str(e)}")
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
    st.title("Consentement eclaire")
    st.markdown(config['consentement']['texte'])
    with st.form("consent_form"):
        st.subheader("Vos informations")
        email = st.text_input("Email (optionnel, pour recevoir les resultats)")
        age = st.number_input("Age", min_value=5, max_value=100, value=25)
        # MODIF Betty Rossitto : 2 genres uniquement
        genre = st.selectbox("Genre", ["Femme", "Homme"])
        st.markdown("---")
        consent = st.checkbox("J'ai lu et j'accepte les conditions ci-dessus")
        submitted = st.form_submit_button("Continuer vers le questionnaire")
        if submitted:
            if not consent:
                st.error("Vous devez accepter le consentement pour continuer")
            else:
                st.session_state['consented'] = True
                st.session_state['email'] = email
                st.session_state['age'] = age
                st.session_state['genre'] = genre
                st.session_state['consent_date'] = datetime.now().isoformat()
                st.success("Consentement enregistre !")
                st.rerun()

def show_questionnaire(config, questionnaire_type):
    if questionnaire_type == "pre":
        title = "Questionnaire PRE-intervention - ASRS v1.1"
        subtitle = "Evaluation AVANT de commencer la methode"
        questions = config['questionnaire_pre']['questions']
    elif questionnaire_type == "post":
        title = "Questionnaire POST-intervention - ASRS v1.1"
        subtitle = "Evaluation APRES avoir suivi la methode"
        questions = config['questionnaire_post']['questions']
    else:
        title = "Questionnaire retrospectif - ASRS v1.1"
        subtitle = "Pour les personnes ayant deja suivi la methode"
        questions = config['questionnaire_retrospectif']['questions']
    st.title(title)
    st.caption(subtitle)
    st.info("Important : Repondez en pensant aux 6 derniers mois.")
    echelle = config['echelle_likert']

    with st.form("questionnaire_form"):
        responses = {}
        st.markdown("### Questions 1 a 6")
        for i in range(6):
            st.markdown(f"**{i+1}. {questions[i]}**")
            responses[f"Q{i+1}"] = st.radio(f"q{i+1}", range(len(echelle)),
                format_func=lambda x: echelle[x], key=f"q_{i+1}", label_visibility="collapsed")
            responses[f"Q{i+1}_text"] = questions[i]
        st.markdown("---")
        st.markdown("### Questions 7 a 18")
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
                    "Par rapport a AVANT la methode, mes symptomes se sont...",
                    options=["Beaucoup aggraves", "Un peu aggraves", "Pas changes",
                             "Un peu ameliores", "Beaucoup ameliores"])
            responses['commentaires'] = st.text_area("Commentaires libres (optionnel)")
        submitted = st.form_submit_button("Envoyer les reponses")
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
                st.success("Reponses enregistrees !")
            st.metric("Score total", f"{scores['score_total']}/72")
            if scores['screening_positif']:
                st.warning(f"Symptomes marques ({scores['items_positifs_a']}/6 items Partie A)")
            else:
                st.success(f"Symptomes legers a moderes ({scores['items_positifs_a']}/6 items Partie A)")


# ─── Questionnaire Profil Atypique - ajout Betty Rossitto ───

QUESTIONS_PROFIL_ATYPIQUE = [
    "A quelle frequence avez-vous l'impression d'etre presente physiquement, mais absente mentalement ?",
    "A quelle frequence vous arrive-t-il de vous sentir coupee de vous-meme, comme si votre esprit se deconnectait ?",
    "A quelle frequence avez-vous le sentiment d'etre en decalage avec les autres, sans vraiment savoir pourquoi ?",
    "A quelle frequence vous arrive-t-il d'observer les interactions sociales sans les comprendre spontanement ?",
    "A quelle frequence ressentez-vous le besoin de reflechir a ce que vous devez dire ou faire pour etre comme il faut ?",
    "A quelle frequence les interactions sociales vous demandent-elles beaucoup d'energie, meme lorsqu'elles semblent simples ?",
    "A quelle frequence ressentez-vous un besoin important de calme, de solitude ou de retrait pour recuperer ?",
    "A quelle frequence avez-vous du mal a savoir par quoi commencer lorsque plusieurs choses sont a faire ?",
    "A quelle frequence restez-vous bloquee face a une tache, meme si vous savez qu'elle est importante ?",
    "A quelle frequence faites-vous des listes ou des plannings sans reussir a les suivre reellement ?",
    "A quelle frequence avez-vous l'impression de mal gerer votre temps au quotidien ?",
    "A quelle frequence vous arrive-t-il de sous-estimer le temps necessaire pour vous preparer ou arriver a un rendez-vous ?",
    "A quelle frequence etes-vous distraite par une information ou une action secondaire, au point d'oublier ce que vous etiez en train de faire ?",
    "A quelle frequence perdez-vous le fil de votre pensee ou de votre action lorsque vous etes interrompue ?",
    "A quelle frequence ressentez-vous un brouillard mental, une sensation de flou ou de confusion interieure ?",
    "A quelle frequence avez-vous du mal a etablir des priorites claires dans votre quotidien ?",
    "A quelle frequence vous arrive-t-il de vous sentir submergee lorsque plusieurs sollicitations arrivent en meme temps ?",
    "A quelle frequence vous arrive-t-il de bloquer ou de ne plus savoir quoi faire dans certaines situations ?",
    "A quelle frequence avez-vous l'impression de vivre a cote de votre vie, sans parvenir a passer a l'action comme vous le souhaiteriez ?",
    "A quelle frequence ressentez-vous que vous faites beaucoup d'efforts pour paraitre normale ou adaptee aux autres ?",
    "A quelle frequence certaines remarques ou emotions provoquent-elles chez vous une coupure, un vide ou un silence mental ?",
    "A quelle frequence avez-vous le sentiment que, meme en comprenant vos difficultes, vous n'arrivez pas a les changer ?",
]

ECHELLE_PROFIL = ["Pas du tout", "Rarement", "Parfois", "Souvent", "Tres souvent"]


def show_questionnaire_profil_atypique():
    st.title("Questionnaire Profil Atypique")
    st.caption("Questionnaire developpe par Betty Rossitto - contact : bethisabea.rossitto@gmail.com")
    st.info("Repondez en pensant a votre quotidien habituel.")
    with st.form("questionnaire_profil_atypique"):
        responses = {}
        for i, question in enumerate(QUESTIONS_PROFIL_ATYPIQUE):
            st.markdown(f"**{i+1}. {question}**")
            responses[f"PA_Q{i+1}"] = st.radio(
                f"pa_q{i+1}", range(len(ECHELLE_PROFIL)),
                format_func=lambda x: ECHELLE_PROFIL[x],
                key=f"pa_{i+1}", label_visibility="collapsed")
            responses[f"PA_Q{i+1}_text"] = question
        submitted = st.form_submit_button("Envoyer les reponses")
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
                st.success("Reponses enregistrees !")
            st.metric("Score total", f"{score_total}/{score_max}")


def main():
    config = load_config()
    if not config:
        st.stop()
    st.sidebar.title("Navigation")
    if 'consented' not in st.session_state:
        st.session_state['consented'] = False
    if not st.session_state['consented']:
        page = "Consentement"
    else:
        page = st.sidebar.radio(
            "Choisissez votre questionnaire :",
            [
                "Consentement",
                "PRE-intervention (nouveaux clients)",
                "POST-intervention (apres la methode)",
                "Retrospectif (anciens clients)",
                "Profil Atypique (Betty Rossitto)",
            ]
        )
    if page == "Consentement" or not st.session_state['consented']:
        show_consent_form(config)
    elif page == "PRE-intervention (nouveaux clients)":
        show_questionnaire(config, "pre")
    elif page == "POST-intervention (apres la methode)":
        show_questionnaire(config, "post")
    elif page == "Retrospectif (anciens clients)":
        show_questionnaire(config, "retrospectif")
    elif page == "Profil Atypique (Betty Rossitto)":
        show_questionnaire_profil_atypique()
    st.sidebar.markdown("---")
    st.sidebar.caption("Methode d'integration multisensorielle")
    st.sidebar.caption("Version 1.0 - 2025")

if __name__ == "__main__":
    main()
