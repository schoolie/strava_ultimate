
# coding: utf-8

# In[1]:

import stravalib
import logging
from xml.dom import minidom
import dateutil
import numpy as np
import pandas as pd

import os

from datetime import datetime, timedelta, date


logger = logging.getLogger()
logger.setLevel(logging.ERROR)


# In[2]:

#### Setting up strava API client

#Global Variables - put your data in the file 'client.secret' and separate the fields with a comma!
client = stravalib.client.Client()
access_token = 'e3ccedc91fceef32077fbb31fc44676446d14bdd'

client.access_token = access_token
athlete = client.get_athlete()

## Enable accessing private activities
auth_url = client.authorization_url(client_id=19435, redirect_uri='http://localhost:8282/authorized', approval_prompt=u'auto', scope='view_private,write', state=None)
from IPython.core.display import display, HTML
display(HTML("""<a href="{}">{}</a>""".format(auth_url,auth_url)))

code = '6d057263b427852b0489af26e921f8fd25a78852'
access_token = client.exchange_code_for_token(client_id=19435, client_secret='45b776d5beceeb34c290b8a56bf9829d6d4ea5d7', code=code)

client = stravalib.client.Client(access_token=access_token)
athlete = client.get_athlete()
print('athlete name %s, athlete id %s.' %(athlete.firstname, athlete.id))


# In[3]:

### Setting up google sheets client -- old library
# import gspread
# from oauth2client.service_account import ServiceAccountCredentials


# # use creds to create a client to interact with the Google Drive API
# scope = ['https://spreadsheets.google.com/feeds']
# creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
# gspread_client = gspread.authorize(creds)
 


# In[4]:

## Set up google sheets client, open worksheet
import pygsheets

gc = pygsheets.authorize(outh_file='client_secret.json', no_cache=True)

# Open spreadsheet and then workseet
sh = gc.open('Milburn Ultimate Scores')
wks = sh.sheet1


# In[9]:

## Get last entry from Data Spreadsheet

dates_recorded = [datetime.strptime(d, '%Y-%m-%d') for d in wks.get_col(1) if d != '' and d != 'Date']
lap_start_date = max(dates_recorded) + timedelta(days=1)
dates_recorded, lap_start_date


# In[10]:

runs = []
for activity in client.get_activities(after=lap_start_date):
    if 'ltimate' in activity.name and activity.type == 'Run':
        runs.append(activity)


# In[15]:

def get_strava_description(activity):
    new_activity = client.get_activity(activity.id)
    try:
        scores, color = new_activity.description.split(' ')
        try:
            team_score, opponent_score = scores.split('-')
        except ValueError:
            team_score, opponent_score, color = None, None, None     
    except ValueError:
        scores = None
        team_score, opponent_score, color = None, None, None           

    try:
        color = color.lower()
    except AttributeError:
        color = None
        
    return team_score, opponent_score, color


# In[16]:

def extract_events(run):
    lap_nums = []
    start_times = []
    elapsed_times = []
    for l in run.laps:
        lap_nums.append(int(l.name.split(' ')[-1]))
        start_times.append(l.start_date_local)
        elapsed_times.append(l.elapsed_time)

    lap_nums = np.array(lap_nums)
    
    events = []
    for n, s, e in zip(np.diff(lap_nums), start_times, elapsed_times):
        events.append([n, s, e])
    
    return (events)
        
def process_events(events):
    
    event_lookup = [
        '',
        'team_point',
        'opponent_point',
        'my_point',
        'game',
        'game'
    ]
    
    games = []
    game_num = 0
    added = False

    base_game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0, 'game_num': 0, 'events':[], 'start_time':None, 'end_time':None}
    game = base_game

    for event in events:
        if game['start_time'] is None:
            game['start_time'] = event[1]

        game['end_time'] = event[1] + event[2]

        event_type = event_lookup[event[0]]
        game['events'].append((event_type, event[1], event[2]))


        if event_type == 'game':
            games.append(game)
            game_num += 1
            game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0, 'game_num': game_num, 'events':[], 'start_time':None, 'end_time':None}
            added = True

        elif event_type == 'my_point':
            game[event_type] += 1
            game['team_point'] += 1
            added = False

        else:
            game[event_type] += 1
            added = False


    if not added:
        games.append(game)
    
    
    ## Assign game winners
    for game in games:
        if game['team_point'] > game['opponent_point']:
            game['win'] = True
        else:
            game['win'] = False
            
    return games


# In[ ]:

games = []
for run in runs:
    team_score, opponent_score, color = get_strava_description(run)
    print(run.start_date_local, get_strava_description(run))
    events = extract_events(run)
    current_games = process_events(events)
    for g in current_games:
        g['my_color'] = color

    games = games + current_games
    


# In[ ]:

df = pd.DataFrame(games)
df['date'] = df.end_time.apply(lambda x: date(x.year, x.month, x.day))

df = df.set_index(['date', 'game_num'], drop=False)
df


# In[10]:

pdf = df


# In[11]:

pdf['white_wins'] = None
pdf['color_wins'] = None
pdf['white_point'] = None
pdf['color_point'] = None
pdf['game_winner'] = None


# In[12]:

for (date, game_num), row in pdf.iterrows():      
    
    if 'white' in row.my_color:
        if row.win:
            pdf.loc[(date, game_num), 'game_winner'] = 'White'
        else:
            pdf.loc[(date, game_num), 'game_winner'] = 'Color'
        pdf.loc[(date, game_num), 'white_wins'] = team_score                
        pdf.loc[(date, game_num), 'color_wins'] = opponent_score   
        pdf.loc[(date, game_num), 'white_point'] = pdf.loc[(date, game_num), 'team_point']                
        pdf.loc[(date, game_num), 'color_point'] = pdf.loc[(date, game_num), 'opponent_point']

    else:
        if not row.win:
            pdf.loc[(date, game_num), 'game_winner'] = 'White'
        else:
            pdf.loc[(date, game_num), 'game_winner'] = 'Color'
        pdf.loc[(date, game_num), 'color_wins'] = team_score                
        pdf.loc[(date, game_num), 'white_wins'] = opponent_score   
        pdf.loc[(date, game_num), 'color_point'] = pdf.loc[(date, game_num), 'team_point']                
        pdf.loc[(date, game_num), 'white_point'] = pdf.loc[(date, game_num), 'opponent_point']


# In[13]:

pdf


# In[40]:

out_df = pdf[['white_wins', 'color_wins', 'game_num', 'game_winner']].copy()


# In[50]:

def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


# In[ ]:




# In[57]:

scores = []
for (date, game_num), game in pdf.iterrows():
    base_dict = dict(date=date, game_num=game_num, white_wins=game.white_wins, color_wins=game.color_wins, game_winner=game.game_winner)    
    scores.append(merge_two_dicts(base_dict, dict(team='white', team_score=game.white_point, my_score=game.my_point if game.my_color == 'white' else None)))
    scores.append(merge_two_dicts(base_dict, dict(team='color', team_score=game.color_point, my_score=game.my_point if game.my_color == 'colors' else None)))

score_df = pd.DataFrame(scores).set_index(['date', 'game_num', 'team'], drop=False)


# In[63]:

out_matrix = score_df[['date', 'white_wins', 'color_wins', 'game_num', 'game_winner', 'team_score', 'my_score']].sort_index(ascending=False, level=0).as_matrix()


# In[65]:

out_matrix.shape


# In[69]:

sheet.insert_row(out_matrix[0,:], 3)


# In[ ]:



