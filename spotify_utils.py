import os
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import session, redirect, url_for
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

# Spotify OAuth setup
sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope='user-library-read'
)

def get_spotify_auth_url():
    """Generate the Spotify authorization URL."""
    return sp_oauth.get_authorize_url()

def handle_spotify_callback(url):
    """Handle the Spotify OAuth callback."""
    code = sp_oauth.parse_response_code(url)
    if code:
        try:
            token_info = sp_oauth.get_access_token(code)
            session['access_token'] = token_info['access_token']
            session['refresh_token'] = token_info['refresh_token']
            session['expires_at'] = token_info['expires_at']
            return True
        except Exception as e:
            logging.error(f"Error in Spotify callback: {str(e)}")
    return False

def get_spotify_client():
    """Get a Spotify client, refreshing the token if necessary."""
    if 'access_token' not in session:
        return None
    
    if time.time() > session.get('expires_at', 0):
        try:
            token_info = sp_oauth.refresh_access_token(session.get('refresh_token'))
            session['access_token'] = token_info['access_token']
            session['expires_at'] = token_info['expires_at']
        except Exception as e:
            logging.error(f"Error refreshing Spotify token: {str(e)}")
            return None

    return spotipy.Spotify(auth=session['access_token'])

def get_music_recommendation(sp, emotion):
    """Get music recommendations based on the detected emotion."""
    search_queries = {
        'anger': "angry mix",
        'fear': "soothing mix",
        'joy': "feel good happy mix",
        'love': "love song mix",
        'sadness': "sad crying mix",
        'surprise': "feel good upbeat mix"
    }
    
    search_query = search_queries.get(emotion, "feel good mix")
    
    try:
        playlist_results = sp.search(q=search_query, type='playlist', limit=1)
        playlist_id = playlist_results['playlists']['items'][0]['id']
        results = sp.playlist_tracks(playlist_id, limit=5)
        return results
    except Exception as e:
        logging.error(f"Error getting music recommendation: {str(e)}")
        return None

def get_user_info(sp):
    """Get the current user's Spotify profile information."""
    try:
        return sp.current_user()
    except Exception as e:
        logging.error(f"Error getting user info: {str(e)}")
        return None

def clear_spotify_session():
    """Clear Spotify-related data from the session."""
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    session.pop('expires_at', None)