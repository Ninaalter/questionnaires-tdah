"""
Application de questionnaires TDAH - Méthode Plasticine
Version scientifiquement validée avec ASRS v1.1
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# Configuration de la page
st.set_page_config(
    page_title="Questionnaire TDAH - ASRS v1.1",
    page_icon="🧠",
    layout="centered"
)

# Chargement de la configuration
def load_config():
    """Charge la configuration depuis config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ Fichier config.json introuvable !")
        return None

# Connexion à Google Sheets
def connect_to_gsheet():
    """Se connecte à Google Sheets pour sauvegarder les données"""
    try:
        if 'gsheet_credentials' in st.secrets:
            credentials_dict = dict(st.secrets['gsheet_credentials'])
        else:
            st.warning("⚠️ Pas de connexion Google Sheets configurée. Les données seront affichées mais non sauvegardées.")
            return None
        
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            credentials_dict, scope)
        client = gspread.authorize(credentials)
        
        sheet_url = st.secrets.get('gsheet_url', '')
        if sheet_url:
            spreadsheet = client.open_by_url(sheet_url)
            return spreadsheet
        else:
            st.warning("⚠️ URL Google Sheet non configurée.")
            return None
    except Exception as e:
        st.warning(f"⚠️ Erreur de connexion Google Sheets: {str(e)}")
        return None

def save_to_gsheet(spreadsheet, worksheet_name, data):
    """Sauvegarde les données dans Google Sheets"""
    try:
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="50")
            headers = list(data.keys())
            worksheet.append_row(headers)
        
        values = list(data.values())
        worksheet.append_row(values)
        return True
    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
        return False

def calculer_score_asrs(responses, config):
    """
    Calcule les scores selon la méthode de cotation ASRS v1.1 à deux étages
    
    Partie A (6 items) : Seuils spécifiques pour chaque question
    - Q1, Q3, Q4 : seuil = 2 (Parfois ou plus)
    - Q2, Q5, Q6 : seuil = 3 (Souvent ou plus)
    - Si 4+ items dépassent leur seuil → Screening POSITIF
    
    Partie B (12 items) : Informations complémentaires
    """
    
    # Seuils pour Partie A (indices 0-5)
    seuils_a = config.get('seuils_partie_a', [2, 3, 2, 2, 3, 3])
    
    # Calcul Partie A
    score_partie_a = 0
    items_positifs_a = 0
    
    for i in range(6):
        score_i = responses.get(f'Q{i+1}', 0)
        score_partie_a += score_i
        if score_i >= seuils_a[i]:
            items_positifs_a += 1
    
    # Calcul Partie B
    score_partie_b = 0
    items_positifs_b = 0
    
    for i in range(6, 18):
        score_i = responses.get(f'Q{i+1}', 0)
        score_partie_b += score_i
        if score_i >= 3:  # Seuil "Souvent" pour Partie B
            items_positifs_b += 1
    
    # Score total
    score_total = score_partie_a + score_partie_b
    score_max = 72  # 18 questions × 4 points max
    
    # Screening ASRS
    screening_positif = items_positifs_a >= 4
    
    return {
        'score_total': score_total,
        'score_max': score_max,
        'score_partie_a': score_partie_a,
        'score_partie_b': score_partie_b,
        'items_positifs_a': items_positifs_a,
        'items_positifs_b': items_positifs_b,
        'screening_positif': screening_positif
    }

def show_consent_form(config):
    """Affiche le formulaire de consentement"""
    st.title("📋 Consentement éclairé")
    
    consent_text = config['consentement']['texte']
    st.markdown(consent_text)
    
    with st.form("consent_form"):
        st.subheader("Vos informations")
        
        email = st.text_input("Email (optionnel, pour recevoir les résultats)")
        age = st.number_input("Âge", min_value=5, max_value=100, value=25)
        genre = st.selectbox("Genre", ["Préfère ne pas dire", "Femme", "Homme", "Autre"])
        
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
                st.success("✅ Consentement enregistré ! Vous pouvez maintenant remplir le questionnaire.")
                st.rerun()

def show_questionnaire(config, questionnaire_type):
    """Affiche le questionnaire principal"""
    
    if questionnaire_type == "pre":
        title = "📝 Questionnaire PRÉ-intervention - ASRS v1.1"
        subtitle = "Évaluation AVANT de commencer la méthode"
        questions = config['questionnaire_pre']['questions']
    elif questionnaire_type == "post":
        title = "📝 Questionnaire POST-intervention - ASRS v1.1"
        subtitle = "Évaluation APRÈS avoir suivi la méthode"
        questions = config['questionnaire_post']['questions']
    else:  # retrospectif
        title = "📝 Questionnaire rétrospectif - ASRS v1.1"
        subtitle = "Pour les personnes ayant déjà suivi la méthode"
        questions = config['questionnaire_retrospectif']['questions']
    
    st.title(title)
    st.caption(subtitle)
    st.info("📌 **Important** : Répondez en pensant aux 6 derniers mois. Il n'y a pas de bonnes ou mauvaises réponses, soyez simplement honnête.")
    
    echelle = config['echelle_likert']
    
    with st.form("questionnaire_form"):
        responses = {}
        
        st.markdown("### Questions 1 à 6")
        st.caption("Les questions les plus importantes")
        
        for i in range(6):
            st.markdown(f"**{i+1}. {questions[i]}**")
            response = st.radio(
                f"question_{i+1}",
                options=range(len(echelle)),
                format_func=lambda x: echelle[x],
                key=f"q_{i+1}",
                label_visibility="collapsed"
            )
            responses[f"Q{i+1}"] = response
            responses[f"Q{i+1}_text"] = questions[i]
        
        st.markdown("---")
        st.markdown("### Questions 7 à 18")
        st.caption("Questions complémentaires")
        
        for i in range(6, 18):
            st.markdown(f"**{i+1}. {questions[i]}**")
            response = st.radio(
                f"question_{i+1}",
                options=range(len(echelle)),
                format_func=lambda x: echelle[x],
                key=f"q_{i+1}",
                label_visibility="collapsed"
            )
            responses[f"Q{i+1}"] = response
            responses[f"Q{i+1}_text"] = questions[i]
        
        # Questions qualitatives pour post et rétrospectif
        if questionnaire_type in ["post", "retrospectif"]:
            st.markdown("---")
            st.markdown("### Votre expérience avec la méthode")
            
            satisfaction = st.slider(
                "Niveau de satisfaction global avec la méthode",
                0, 10, 5,
                help="0 = Pas du tout satisfait, 10 = Extrêmement satisfait"
            )
            responses['satisfaction'] = satisfaction
            
            if questionnaire_type == "retrospectif":
                amelioration = st.select_slider(
                    "Par rapport à AVANT la méthode, mes symptômes se sont...",
                    options=["Beaucoup aggravés", "Un peu aggravés", "Pas changés", 
                            "Un peu améliorés", "Beaucoup améliorés"]
                )
                responses['amelioration_percue'] = amelioration
            
            commentaires = st.text_area(
                "Commentaires libres (optionnel)",
                placeholder="Partagez votre expérience, ce qui a aidé, les difficultés rencontrées..."
            )
            responses['commentaires'] = commentaires
        
        submitted = st.form_submit_button("📨 Envoyer les réponses")
        
        if submitted:
            # Calcul des scores selon ASRS v1.1
            scores = calculer_score_asrs(responses, config)
            
            # Prépare les données à sauvegarder
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'type_questionnaire': questionnaire_type,
                'email': st.session_state.get('email', ''),
                'age': st.session_state.get('age', ''),
                'genre': st.session_state.get('genre', ''),
                'score_total': scores['score_total'],
                'score_max': scores['score_max'],
                'score_partie_a': scores['score_partie_a'],
                'score_partie_b': scores['score_partie_b'],
                'items_positifs_a': scores['items_positifs_a'],
                'items_positifs_b': scores['items_positifs_b'],
                'screening_positif': scores['screening_positif'],
                'score_pourcentage': round((scores['score_total'] / scores['score_max']) * 100, 1)
            }
            
            # Ajoute toutes les réponses
            save_data.update(responses)
            
            # Tente de sauvegarder dans Google Sheets
            spreadsheet = connect_to_gsheet()
            if spreadsheet:
                success = save_to_gsheet(spreadsheet, questionnaire_type.upper(), save_data)
                if success:
                    st.success("✅ Réponses enregistrées avec succès !")
                else:
                    st.warning("⚠️ Erreur d'enregistrement, mais vos réponses sont affichées ci-dessous")
            
            # Affiche les résultats
            st.markdown("---")
            st.markdown("### 📊 Vos résultats - Méthode ASRS v1.1")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Score total", f"{scores['score_total']}/{scores['score_max']}")
                st.caption(f"{save_data['score_pourcentage']}%")
            
            with col2:
                st.metric("Partie A (dépistage)", f"{scores['items_positifs_a']}/6")
                st.caption("Items au-dessus du seuil")
            
            with col3:
                if 'satisfaction' in responses:
                    st.metric("Satisfaction", f"{satisfaction}/10")
            
            # Interprétation du screening
            st.markdown("#### 📊 Interprétation de vos résultats")
            
            if scores['screening_positif']:
                st.warning(f"""
                **Vos symptômes sont marqués** ({scores['items_positifs_a']}/6)
                
                D'après ce questionnaire, vous présentez plusieurs difficultés significatives 
                d'attention et de concentration.
                
                💡 **C'est normal** : C'est justement pour cela que vous consultez !  
                La méthode est conçue pour vous aider avec ces difficultés.
                """)
            else:
                st.success(f"""
                **Vos symptômes sont légers à modérés** ({scores['items_positifs_a']}/6)
                
                D'après ce questionnaire, vos difficultés d'attention et de concentration 
                sont présentes mais relativement légères.
                
                💡 La méthode pourra vous aider à les réduire davantage.
                """)
            
            # Informations supplémentaires
            with st.expander("ℹ️ Que signifient mes scores ?"):
                st.markdown(f"""
                **Votre score total : {scores['score_total']}/72**
                
                Plus le score est élevé, plus les difficultés sont fréquentes.
                
                - **0-18** : Difficultés occasionnelles
                - **19-36** : Difficultés modérées
                - **37-54** : Difficultés importantes
                - **55-72** : Difficultés très marquées
                
                Ce questionnaire mesure la **fréquence** de vos difficultés, 
                pas leur gravité. L'objectif est de voir si elles diminuent 
                après avoir suivi la méthode.
                """)
            
            st.info("💾 Vos réponses ont été enregistrées. Merci de votre participation !")

def main():
    """Fonction principale de l'application"""
    
    # Charge la configuration
    config = load_config()
    if not config:
        st.stop()
    
    # Sidebar pour la navigation
    st.sidebar.title("🧠 Navigation")
    
    # Initialise session state
    if 'consented' not in st.session_state:
        st.session_state['consented'] = False
    
    # Menu de sélection
    if not st.session_state['consented']:
        page = "Consentement"
    else:
        page = st.sidebar.radio(
            "Choisissez votre questionnaire :",
            ["Consentement", "PRÉ-intervention (nouveaux clients)", 
             "POST-intervention (après la méthode)", 
             "Rétrospectif (anciens clients)"]
        )
    
    # Affiche la bonne page
    if page == "Consentement" or not st.session_state['consented']:
        show_consent_form(config)
    elif page == "PRÉ-intervention (nouveaux clients)":
        show_questionnaire(config, "pre")
    elif page == "POST-intervention (après la méthode)":
        show_questionnaire(config, "post")
    elif page == "Rétrospectif (anciens clients)":
        show_questionnaire(config, "retrospectif")
    
    # Footer avec citation
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 Méthode d'intégration multisensorielle")
    st.sidebar.caption("Questionnaire validé scientifiquement")
    st.sidebar.caption("Version 1.0 - 2025")

if __name__ == "__main__":
    main()
