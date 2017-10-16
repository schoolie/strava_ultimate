
# coding: utf-8

# In[13]:

import stravalib
import logging
from xml.dom import minidom
import dateutil
import numpy as np
import os

logger = logging.getLogger()
logger.setLevel(logging.ERROR)


# In[2]:

#Global Variables - put your data in the file 'client.secret' and separate the fields with a comma!
client = stravalib.client.Client()
access_token = 'e3ccedc91fceef32077fbb31fc44676446d14bdd'

client.access_token = access_token
athlete = client.get_athlete()


# In[3]:

auth_url= client.authorization_url(client_id=19435, redirect_uri='http://localhost:8282/authorized', approval_prompt=u'auto', scope='view_private,write', state=None)
from IPython.core.display import display, HTML
display(HTML("""<a href="{}">{}</a>""".format(auth_url,auth_url)))


# In[4]:

code = '6d057263b427852b0489af26e921f8fd25a78852'
access_token = client.exchange_code_for_token(client_id=19435, client_secret='45b776d5beceeb34c290b8a56bf9829d6d4ea5d7', code=code)


# In[5]:

client = stravalib.client.Client(access_token=access_token)
athlete = client.get_athlete()
print('athlete name %s, athlete id %s.' %(athlete.firstname, athlete.id))


# In[6]:

import datetime
lap_start_date = datetime.datetime(2017, 9, 28)
lap_start_date


# In[7]:

runs = []
for activity in client.get_activities(after=lap_start_date):
    if 'ltimate' in activity.name and activity.type == 'Run':
        print(activity.name, activity.type, activity.start_date)
        runs.append(activity)


# In[8]:

for run in runs:
    print(run)
    for lap in runs[1].laps:
        print(lap.elapsed_time)


# In[9]:

lap


# In[10]:


def xml_to_float(element):
    if element is not None:
        return float(element[0].firstChild.data)
    else:
        return np.nan
        
def xml_to_time(element):
    if element is not None:
        return datetime.datetime.strptime(element[0].firstChild.data, '%Y-%m-%dT%H:%M:%S.%fZ')
#         return dateutil.parser.parse(element[0].firstChild.data)
    else:
        return np.nan


# In[12]:

event_lookup = [
    '',
    'team_point',
    'opponent_point',
    'my_point',
    'game',
]


# In[17]:

class Dummy(object):
    pass

self = Dummy()

# filename = 'activity_2088811850.tcx'   
filename = 'activity_2101180747.tcx'   
       
    

games = []


for filename in os.listdir():
    if '.tcx' in filename:

        game_num = 0
    
        doc = minidom.parse(filename)
        doc.normalize()
        self.tcx = doc.documentElement   

        points = []

        lap_starts = []
        for lap in self.tcx.getElementsByTagName('Lap'):
            lap_starts.append(lap.attributes.items()[0][1])

        lap_starts = [datetime.datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.000Z') for t in lap_starts]
        lap_starts = lap_starts[1:] # Drop first lap (start of day)

        press_delta = datetime.timedelta(0,2)

        presses = 1

        events = []

        for n in range(len(lap_starts) - 1):


            time = lap_starts[n]

            dt = lap_starts[n+1] - lap_starts[n]

            # print(presses, time, dt, dt > press_delta)


            if dt > press_delta:
                events.append([presses, time])
                presses = 1

            else:        
                presses += 1

        events.append([presses, time])


        base_game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0, 'game_num': 0}
        game = base_game
        for event in events:
            game['end_time'] = event[1]

            event_type = event_lookup[event[0]]
            if event_type == 'game':
                games.append(game)                
                game_num += 1
                game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0, 'game_num': game_num}
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

games


# In[18]:

import pandas as pd


# In[20]:

df = pd.DataFrame(games)


# In[23]:

df['date'] = df.end_time.apply(lambda x: datetime.date(x.year, x.month, x.day))


# In[28]:

df.set_index(['date', 'game_num']).unstack('game_num').reorder_levels([1,0], axis=1).sort_index(axis=1)

