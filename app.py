from flask import Flask, render_template, request, redirect, session, url_for
# from flask_sqlalchemy import SQLAlchemy
import datetime
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotipy.util as util
import pylast
import random
import json
import sys
import webbrowser
import uuid
from flask_session import Session
import os
import pandas as pd
from youtube_api import YouTubeDataAPI




#Spotify API STUFF
def authorize_spotify():
    
    auth_manager = SpotifyOAuth(scope=scope)
    token_info = auth_manager.get_cached_token()
    if not token_info:
        auth_url = auth_manager.get_authorize_url()



    # token = util.prompt_for_user_token(username = 'bbierman07', scope = scope)
    # auth_manager_in = SpotifyOAuth(client_id = client_id_in, client_secret = client_secret_in, redirect_uri = redirect_uri_in, scope=scope, username='jarrettbierman')
    # token = auth_manager_in.get_access_token()
    # sp = spotipy.Spotify(auth_manager=auth_manager_in)
    sp = spotipy.Spotify(auth=token)
    return sp

    print("Spotify has been authorized")


#LAST-FM-API-STUFF
def authorize_lastfm():
    API_KEY = '2296dec001d131f586bd715159105fb0'
    API_SECRET = '7f57826cbedd327ffee7f0ebcaf6c7b9'
    user_name = 'jarrettbierman'
    user_password = pylast.md5('Beerbottle711!')
    network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=user_name, password_hash=user_password)
    return network


#YOUTUBE API STUFF
def authorize_youtube():
    api_key = 'AIzaSyBhj5wg0cm1sETpB0sGyDN3sEWacnzZfRM'
    yt = YouTubeDataAPI(api_key)
    return yt



class Song:
    def __init__(self, name, artist, album, play_count, sound_clip):
        self.name = name
        self.artist = artist
        self.album = album
        self.play_count = play_count
        self.sound_clip = sound_clip

    def update_play_count(self, yt_api):
        search_query = self.name + " " + self.artist
        video_id = yt_api.search(q = search_query)[0]['video_id']
        view_count = yt_api.get_video_metadata(video_id)['video_view_count']
        self.play_count = view_count
        print("count updated")
        return self

class Playlist:
    def __init__(self, name, id): # playlist_object will be something like sp_id = sp.current_user_playlists()['items'][0]['id']  p_obj = sp.user_playlist_tracks(playlist_id = p_id)  
        self.id = id
        self.name = name
        self.songs = []

    def populate(self, sp):
        tracks = get_all_playlist_tracks(playlist_id_in=self.id, sp = sp)
        for song in tracks:
            temp_name = song['track']['name']
            temp_artist = song['track']['artists'][0]['name']
            temp_album = song['track']['album']['name']
            temp_play_count = 0
            temp_clip = song['track']['preview_url']
            self.songs.append(Song(temp_name, temp_artist, temp_album, temp_play_count, temp_clip))
        
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)

def get_all_playlist_tracks(playlist_id_in, sp):
    results = sp.user_playlist_tracks(playlist_id = playlist_id_in)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def create_playlists(sp):
    lists = sp.current_user_playlists()['items']
    ret_pls = []
    for playlist in lists:
        ret_pls.append(Playlist(playlist['name'], playlist['id']))
    return ret_pls

def playlist_to_id(pls, id):
    for pl in pls:
        if(pl.id == id):
            return pl
    return None

def create_playlist(sp, id):
    pl = sp.playlist(id)
    return Playlist(pl['name'], pl['id'])

client_id = '379b15e111a14089ae41a384d0db80a2'
client_secret = 'f487fb0030f640eabf35f5ceefffe427'
# redirect_uri = 'https://playlistbattle.herokuapp.com'
redirect_uri = 'http://localhost:8000'
scope = "user-library-read playlist-read-private playlist-read-collaborative"

#CREATE SERVER
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)


caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)

# helper function for managing thhe cache folder
def session_cache_path():
    return caches_folder + session.get('uuid')

#THE ACTUAL SERVER PART
@app.route('/')
def index():
    if not session.get('uuid'):
        # Step 1. Visitor is unknown, give random ID
        session['uuid'] = str(uuid.uuid4())

    auth_manager = spotipy.oauth2.SpotifyOAuth(scope='user-library-read playlist-read-private playlist-read-collaborative',
                                                client_id = client_id,
                                                client_secret = client_secret,
                                                redirect_uri = redirect_uri,
                                                cache_path=session_cache_path(), 
                                                show_dialog=True)
    if request.args.get("code"):
        # Step 3. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')
    
    if not auth_manager.get_cached_token():
        # Step 2. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return render_template("index.html", auth_url = auth_url)
        # return f'<h2><a href="{auth_url}">Sign in</a></h2>'
    
    # Step 4. Signed in, display data
    sp = spotipy.Spotify(auth_manager=auth_manager)
    playlists = create_playlists(sp)
    access_token = auth_manager.get_access_token()['access_token']
    return redirect(url_for('choose', access_token = access_token))
    # return render_template('choose.html', playlists = playlists, name = sp.me()['display_name'])


    

@app.route('/choose/<access_token>', methods = ['GET', 'POST'])
def choose(access_token): 
    sp = spotipy.Spotify(auth = access_token)
    score = -1
    playlists = create_playlists(sp)
    seed = int(round(time.time() * 1000))
    print(f"Your seed is {seed}")
    return render_template('choose.html', playlists = playlists, name = sp.me()['display_name'], access_token = access_token, seed = seed)

@app.route('/game/<access_token>/<pl_id>/<int:seed>/<int:song_counter>/<int:score>/<int:pl_made>', methods = ['GET', 'POST'])
def game(access_token, pl_id, song_counter, score, pl_made, seed):
    yt_api = authorize_youtube()
    sp = spotipy.Spotify(auth = access_token)
    if pl_id == 'none':
        pl_id = request.form.get('action')
    chosen_playlist = create_playlist(sp, pl_id)
    chosen_playlist.populate(sp)
    random.Random(seed).shuffle(chosen_playlist.songs)
    # shuffle playlist the same way
    song1 = chosen_playlist.songs[song_counter].update_play_count(yt_api)
    song2 = chosen_playlist.songs[song_counter+1].update_play_count(yt_api)
    # song_counter += 1
    # score += 1
    return render_template('game.html', playlist = chosen_playlist, song1 = song1, song2 = song2, pl_id = pl_id,
        score = score, song_counter = song_counter, access_token = access_token, seed = seed)

@app.route('/restart/<access_token>/<pl_id>', methods = ['GET', 'POST'])
def restart(access_token, pl_id):
    seed = int(round(time.time() * 1000))
    return redirect(f"/game/{access_token}/{pl_id}/{seed}/0/0/1")

@app.route('/sign_out')
def sign_out():
    os.remove(session_cache_path())
    try:
        # Remove the CACHE file (.cache-test) so that a new user can authorize.
        os.remove(session_cache_path())
    except OSError as e:
        print ("Error: %s - %s." % (e.filename, e.strerror))
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug = True, port = 8000)