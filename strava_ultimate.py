
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

strava_client = stravalib.client.Client(access_token=access_token)
athlete = strava_client.get_athlete()
print('athlete name %s, athlete id %s.' %(athlete.firstname, athlete.id))


# In[3]:

## Set up google sheets client, open worksheet
import pygsheets

gc = pygsheets.authorize(outh_file='client_secret.json', no_cache=True)

# Open spreadsheet and then workseet
sh = gc.open('Milburn Ultimate Scores')


# In[5]:

## Get last entry from Data Spreadsheet

wks = sh.worksheet_by_title('game_summaries')

dates_recorded = [datetime.strptime(d, '%Y-%m-%d') for d in wks.get_col(1) if d != '' and d != 'Date']
lap_start_date = max(dates_recorded) + timedelta(days=1)
# lap_start_date = dates_recorded[20]
lap_start_date
# from datetime import timedelta
# lap_start_date = lap_start_date - timedelta(days=2)


# In[6]:

runs = []
for activity in strava_client.get_activities(after=lap_start_date):
    if 'ltimate' in activity.name and activity.type == 'Run':
        a = strava_client.get_activity(activity.id)
        runs.append(a)


# In[7]:

def get_strava_description(activity, p=False):
    new_activity = strava_client.get_activity(activity.id)
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
        
    if p:
        print(new_activity.start_date)
        print(new_activity.description)
        print(team_score, opponent_score, color)
        
    return team_score, opponent_score, color


# In[24]:

## Functions
def extract_events(run):
    lap_nums = []
    start_times = []
    elapsed_times = []
    for l in run.laps:
        lap_nums.append(int(l['name'].split(' ')[-1]))
        start_times.append(datetime.strptime(l['start_date_local'], '%Y-%m-%dT%H:%M:%SZ'))
        elapsed_times.append(timedelta(seconds=l['elapsed_time']))

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


# In[28]:

games = []
for run in runs:
    team_wins, opponent_wins, color = get_strava_description(run, p=True)
    
    events = extract_events(run)

    ## Write points to gsheets
    point_df = pd.DataFrame(events, columns=['count', 'start_time', 'elapsed_time'])
    point_df['start_time'] = point_df['start_time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    point_df['elapsed_time'] = point_df['elapsed_time'].apply(lambda x: x.seconds)
    
    data = point_df.as_matrix().tolist()
    wks = sh.worksheet_by_title('raw_points')
    wks.insert_rows(2, values=data, number=len(data))

    for e in events:
        print(e)
    current_games = process_events(events)
    
    for g in current_games:
        g['my_color'] = color
        g['team_wins'] = team_wins
        g['opponent_wins'] = opponent_wins
        

    games = games + current_games
    


# In[26]:




# In[27]:




# In[29]:

df = pd.DataFrame(games).dropna()


# In[30]:

df['date'] = df.end_time.apply(lambda x: date(x.year, x.month, x.day))

df = df.set_index(['date', 'game_num'], drop=False)
df


# In[31]:

pdf = df


# In[32]:

pdf['white_wins'] = None
pdf['color_wins'] = None
pdf['white_point'] = None
pdf['color_point'] = None
pdf['game_winner'] = None


# In[33]:

for (date, game_num), row in pdf.iterrows():      
    
    if row.my_color == 'white':
        if row.win:
            pdf.loc[(date, game_num), 'game_winner'] = 'White'
        else:
            pdf.loc[(date, game_num), 'game_winner'] = 'Color'
        pdf.loc[(date, game_num), 'white_wins'] = pdf.loc[(date, game_num), 'team_wins']            
        pdf.loc[(date, game_num), 'color_wins'] = pdf.loc[(date, game_num), 'opponent_wins']            
        pdf.loc[(date, game_num), 'white_point'] = pdf.loc[(date, game_num), 'team_point']                
        pdf.loc[(date, game_num), 'color_point'] = pdf.loc[(date, game_num), 'opponent_point']

    else:
        if not row.win:
            pdf.loc[(date, game_num), 'game_winner'] = 'White'
        else:
            pdf.loc[(date, game_num), 'game_winner'] = 'Color'
        pdf.loc[(date, game_num), 'color_wins'] = pdf.loc[(date, game_num), 'team_wins']            
        pdf.loc[(date, game_num), 'white_wins'] = pdf.loc[(date, game_num), 'opponent_wins']    
        pdf.loc[(date, game_num), 'color_point'] = pdf.loc[(date, game_num), 'team_point']                
        pdf.loc[(date, game_num), 'white_point'] = pdf.loc[(date, game_num), 'opponent_point']


# In[34]:

pdf


# In[35]:

def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


# In[36]:

scores = []
for (date, game_num), game in pdf.iterrows():
    base_dict = dict(date=date, game_num=game_num, white_wins=game.white_wins, color_wins=game.color_wins, game_winner=game.game_winner)    
    scores.append(merge_two_dicts(base_dict, dict(team='white', team_score=game.white_point, my_score=game.my_point if game.my_color == 'white' else None)))
    scores.append(merge_two_dicts(base_dict, dict(team='color', team_score=game.color_point, my_score=game.my_point if game.my_color == 'colors' else None)))

score_df = pd.DataFrame(scores).set_index(['date', 'game_num', 'team'], drop=False)


# In[37]:

out_df = score_df[['date', 'white_wins', 'color_wins', 'game_num', 'game_winner', 'team', 'team_score', 'my_score']].sort_index(ascending=False, level=0).fillna(value='')
out_df['date'] = out_df['date'].apply(lambda x: x.strftime('%Y-%m-%d'))


# In[38]:

out_df


# In[39]:

data = out_df.as_matrix().tolist()
wks = sh.worksheet_by_title('game_summaries')
wks.insert_rows(2, values=data, number=len(data))


# In[ ]:




# In[ ]:



