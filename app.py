
import os

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import transformers
from transformers import pipeline
from lime.lime_text import LimeTextExplainer
import numpy as np
from flask import Flask, request, redirect, render_template, url_for, session
from flask_session import Session
import logging
import random
from dotenv import load_dotenv
from spotify_utils import get_spotify_auth_url, handle_spotify_callback, get_spotify_client, get_music_recommendation, get_user_info, clear_spotify_session

# Load environment variables
load_dotenv()

# Create a Flask app
server = Flask(__name__)
server.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
server.config['SESSION_TYPE'] = 'filesystem'
Session(server)

# Create a Dash app with the Flask app as the server
app = dash.Dash(__name__, server=server)

# Define the classifier
classifier = pipeline("text-classification", model='bhadresh-savani/distilbert-base-uncased-emotion', top_k=None)

def predict_proba(sentences):
    if not isinstance(sentences, list):
        sentences = [sentences]
    model_outputs = [classifier([sentence], return_all_scores=True) for sentence in sentences]
    return np.array([[emotion['score'] for emotion in sorted(model_output[0], key=lambda x: x['label'])] for model_output in model_outputs])

# Create a LIME explainer with the class names
class_names = ['anger', 'fear', 'joy', 'love', 'sadness', 'surprise']
explainer = LimeTextExplainer(class_names=class_names)

# Define the welcome screen layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.H1('Welcome to The Journaling Application'),
    html.Div([
        html.Div([
            html.H2('Why do I need to login?', className='center-text'),
            html.P('To provide personalized recommendations based on both the user\'s emotional state and their preferences, the application integrates with the Spotify platform. This integration requires users to log in to their Spotify accounts. By logging in, the application gains access to the user\'s library on Spotify, enabling it to analyze the user\'s emotional state based on the journal entry provided and recommend music accordingly.', className='left-text'),
            html.H2('What happens to my data?', className='center-text'),
            html.P('It\'s important to note that the application does not access the user\'s private information on Spotify. Therefore, the recommendations provided are based on the emotional analysis of the journal entry and the user\'s preferences, without accessing any personal data from the user\'s Spotify account. Additionally, the data is not stored, and the authentication key used to access the Spotify account is a session key that expires after the user session ends.', className='left-text'),
            html.P('The data retrieved from the user\'s Spotify account is limited to the publicly available information in their library, and no access is granted to their private account details. User privacy and data security remain paramount, and the application ensures that all data handling complies with Spotify\'s policies and regulations regarding user data protection.', className='left-text'),
            html.P('If you\'re not comfortable feel free to close the application', className='b-text center-text'),
            html.Br(),
            html.P('Please click the button below to verify with Spotify.', className='p-text center-text'),
            html.Div([
                html.Button('Verify with Spotify', id='submit-button', n_clicks=0, className='submit-button'),
            ], className='input'),
        ], className='center-text'),
        dcc.Store(id='sp')
    ], className='container')
])

@server.route('/login')
def login():
    if 'access_token' in session:
        return redirect(url_for('home'))
    return redirect(get_spotify_auth_url())

@server.route('/callback')
def callback():
    try:
        if handle_spotify_callback(request.url):
            return redirect(url_for('analysis'))
        return redirect(url_for('login'))
    except Exception as e:
        logging.error(f"Error in callback: {str(e)}")
        return redirect(url_for('error_page'))

@server.route('/analysis', methods=['GET', 'POST'])
def analysis():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('login'))

    if request.method == 'POST':
        input_value = request.form.get('input_value')
        explanation, music_recommendation, top_emotion_display, explanation_type = update_output(input_value, sp)
        return render_template('results.html', explanation=explanation, music_recommendation=music_recommendation['items'], top_emotion=top_emotion_display, explanation_type=explanation_type)
    else:
        return render_template('analysis_form.html')

@server.route('/home')
def home():
    sp = get_spotify_client()
    if sp:
        user = get_user_info(sp)
        return render_template('index.html', user=user)
    return redirect(url_for('login'))

@server.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@server.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

def update_output(input_value, sp):
    if not input_value or not input_value.strip():
        return "Please enter some text in the journal.", "", "", ""

    probs = predict_proba([input_value])
    label_prob_pairs = list(zip(class_names, probs[0]))
    sorted_probs = sorted(label_prob_pairs, key=lambda x: x[1], reverse=True)
    top_emotion = sorted_probs[0][0]
    top_emotion_display = top_emotion
    top_emotion_index = class_names.index(top_emotion)

    music_recommendation = get_music_recommendation(sp, top_emotion)

    explanation_type = random.choice(['lime explanation', 'text explanation', ''])
    if explanation_type == 'lime explanation':
        exp = explainer.explain_instance(input_value, predict_proba, labels=[top_emotion_index], num_features=5, num_samples=200)
        explanation = exp.as_html()
    elif explanation_type == 'text explanation':
        explanation = get_text_explanation(top_emotion)
    else:
        explanation = ""

    clear_spotify_session()

    return explanation, music_recommendation, top_emotion_display, explanation_type

def get_text_explanation(emotion):
    explanations = {
        'anger': "It seems you're feeling angry. Based on your emotion, we recommend listening to some energetic music to help release tension and channel your emotions positively.",
        'fear': "It appears you're feeling fearful. To soothe your nerves, we suggest listening to calming music that can help alleviate anxiety and promote relaxation.",
        'joy': "You seem to be experiencing joy! How wonderful! For an extra boost of happiness, we recommend listening to upbeat and cheerful music that resonates with your mood.",
        'love': "It looks like you're in a loving mood. To celebrate the warmth of your emotions, we suggest indulging in some romantic music that reflects the beauty of love.",
        'sadness': "It appears you're feeling sad. During times of sadness, music can provide comfort and solace. We recommend listening to soothing melodies that match your mood.",
        'surprise': "You seem to be surprised! How exciting! To enhance the sense of wonder, we recommend exploring eclectic and diverse music that embraces the element of surprise."
    }
    return explanations.get(emotion, "We've analyzed your emotion and selected music that we think will resonate with your current mood.")

# Add a clientside callback
app.clientside_callback(
    """
    function(n_clicks, is_authenticated, sp_data) {
        if(n_clicks > 0 && !is_authenticated) {
            window.open('/login', '_self');
        }
        return window.location.href;
    }
    """,
    Output('url', 'href'),
    [Input('submit-button', 'n_clicks'), State('sp', 'data')]
)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run_server(debug=False, host='0.0.0.0', port=8080)