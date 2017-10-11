
# coding: utf-8

# In[1]:

import stravalib
import logging
from xml.dom import minidom
import dateutil
import numpy as np

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


# In[47]:

class Dummy(object):
    pass

self = Dummy()

filename = 'activity_2088811850.tcx'   
       
    
    
doc = minidom.parse(filename)
doc.normalize()
self.tcx = doc.documentElement   

points = []

lap_starts = []
for lap in self.tcx.getElementsByTagName('Lap'):
    lap_starts.append(lap.attributes.items()[0][1])
    
lap_starts = [datetime.datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.000Z') for t in lap_starts]
lap_starts = lap_starts[1:] # Drop first lap (start of day)


#     for track in lap.getElementsByTagName('Track'):
#         for trackpoint in track.getElementsByTagName('Trackpoint'):     

#             _pos = trackpoint.getElementsByTagName('Position') or None
#             if _pos:
#                 _lat = _pos[0].getElementsByTagName('LatitudeDegrees')
#                 _lon = _pos[0].getElementsByTagName('LongitudeDegrees')
#             else:
#                 _lat = None
#                 _lon = None

#             _time = trackpoint.getElementsByTagName('Time')
#             _dist = trackpoint.getElementsByTagName('DistanceMeters') or None
#             _alt = trackpoint.getElementsByTagName('AltitudeMeters') or None

#             _hr_cont = trackpoint.getElementsByTagName('HeartRateBpm') or None
#             if _hr_cont:
#                 _hr = _hr_cont[0].getElementsByTagName('Value') or None
#             else:
#                 _hr = None

#             _cad = trackpoint.getElementsByTagName('Cadence') or None



#             _point = {'lat': xml_to_float(_lat),
#                       'lon': xml_to_float(_lon),
#                       'time': xml_to_time(_time),
#                       'alt':  xml_to_float(_alt),
#                       'hr':   xml_to_float(_hr),
#                       'cad':  xml_to_float(_cad),
#                       'dist': xml_to_float(_dist),
#                      }
#             points.append(_point)

# self.points = points
# # self.activity_type = self.tcx.getElementsByTagName('Activity')[0].attributes.getNamedItem('Sport')
# self.activity_type = 'Biking'


# In[49]:

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

events


# In[50]:

events


# In[55]:

event_lookup = [
    '',
    'team_point',
    'opponent_point',
    'my_point',
    'game',
]


# In[56]:

games = []

base_game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0}
game = base_game
for event in events:
    game['end_time'] = event[1]

    event_type = event_lookup[event[0]]
    if event_type == 'game':
        games.append(game)
        game = {'my_point': 0, 'team_point': 0, 'opponent_point': 0}
        
    elif event_type == 'my_point':
        game[event_type] += 1
        game['team_point'] += 1
    else:
        game[event_type] += 1

games.append(game)
games


# In[57]:

import pandas as pd


# In[58]:

pd.DataFrame(games)


# In[ ]:



