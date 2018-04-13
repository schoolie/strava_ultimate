
# coding: utf-8

# In[1]:


import fire
import json
import stravalib
import pygsheets

import logging
from xml.dom import minidom
import dateutil
import numpy as np
import pandas as pd

import os

from datetime import datetime, timedelta, date


logger = logging.getLogger()
logger.setLevel(logging.ERROR)


def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z

def extract_events(run):
    lap_nums = []
    start_times = []
    elapsed_times = []
    for l in run.laps:
        try:
            lap_nums.append(int(l['name'].split(' ')[-1]))
            start_times.append(datetime.strptime(l['start_date_local'], '%Y-%m-%dT%H:%M:%SZ'))
            elapsed_times.append(timedelta(seconds=l['elapsed_time']))
        except TypeError:
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

class Handler(object):
    def __init__(self):
        #### Setting up strava API client
        ## Read Strava secret file
        with open('strava_secrets.json') as json_data:
            strava_secrets = json.load(json_data)

        strava_client = stravalib.client.Client()
        # access_token = strava_secrets['access_token']
        #
        # strava_client.access_token = access_token
        # athlete = strava_client.get_athlete()

        ## Enable accessing private activities


        code = strava_secrets['auth_code']
        access_token = strava_client.exchange_code_for_token(client_id=19435, client_secret='45b776d5beceeb34c290b8a56bf9829d6d4ea5d7', code=code)

        strava_client = stravalib.client.Client(access_token=access_token)
        athlete = strava_client.get_athlete()
        # print('athlete name %s, athlete id %s.' %(athlete.firstname, athlete.id

        ## Set up google sheets client, open worksheet

        # - Opens browser window, produces sheets.googleapis.com-python.json ... need to figure out how to productionize?
        gc = pygsheets.authorize(outh_file='gsheet_secret.json', no_cache=True)

        # Open spreadsheet and then workseet
        wkb = gc.open('Milburn Ultimate Scores')

        self.athlete = athlete
        self.strava_client = strava_client
        self.wkb = wkb

    def get_raw_points(self, start_date):
        """
        Compile raw points for export
        """

        all_data = []

        runs = []
        for activity in self.strava_client.get_activities(after=start_date):
            if 'ltimate' in activity.name and activity.type == 'Run':
                a = self.strava_client.get_activity(activity.id)
                runs.append(a)

        for run in reversed(runs):

            events = extract_events(run)

            point_df = pd.DataFrame(events, columns=['count', 'start_time', 'elapsed_time'])
            point_df['start_time'] = point_df['start_time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
            point_df['elapsed_time'] = point_df['elapsed_time'].apply(lambda x: x.seconds)

            data = point_df[['count', 'start_time']].sort_index(ascending=False).as_matrix().tolist()
            all_data = all_data + data

        return all_data

    def get_last_raw_entry(self, debug_days=0):
        """
        Get last entry from Raw Point Spreadsheet
        """

        wks = self.wkb.worksheet_by_title('raw_points')

        dates = wks.get_col(2)
        dates_recorded = [datetime.strptime(d, '%Y-%m-%d %H:%M:%S') for d in dates if d != '' and d != 'Start Time']
        start_date = max(dates_recorded) + timedelta(days=1) ## Go to day after last game

        ## back in time for debugging
        start_date = start_date - timedelta(days=debug_days)

        return start_date

    def write_raw_points(self, raw_points):

        ## Write raw points to gsheets`
        wks = self.wkb.worksheet_by_title('raw_points')
        wks.insert_rows(2, values=raw_points, number=len(raw_points))

    def get_strava_description(self, activity, p=False):
        new_activity = self.strava_client.get_activity(activity.id)
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

    def strava_to_gsheet(self, debug_days=0):
        """
        Gets last entry from raw points worksheet
        Reads strava data after latest entry (minus debug_days)
        Parses strava files, writes raw points to top of raw_points worksheet
        """

        # Find date of last entry
        start_date = self.get_last_raw_entry(debug_days=debug_days)

        print('Getting runs after:', start_date)

        # Get runs after start_date from Strava, extract points
        raw_points = self.get_raw_points(start_date)

        print('{} Points Found'.format(len(raw_points)))

        # Write to gsheets
        self.write_raw_points(raw_points)

    ## Get last entry from Data Spreadsheet
    def raw_to_summary(self, debug_days=0):

        ## Get date column from summary sheet
        summary_sheet = self.wkb.worksheet_by_title('game_summaries')
        dates = summary_sheet.get_col(1)

        dates_recorded = [datetime.strptime(d, '%Y-%m-%d') for d in dates if d != '' and d != 'Date']
        start_date = max(dates_recorded) + timedelta(days=1) - timedelta(days=debug_days)


        ## Read data from raw point spreadsheet, process
        raw_sheet = self.wkb.worksheet_by_title('raw_points')

        # get all raw values
        all_values  = raw_sheet.get_all_values()

        # read col names
        col_names = all_values[1][0:2]

        # read values, discard formulas
        val_lists = all_values[2:]
        val_lists = [v[0:2] for v in val_lists]

        # to DataFrame
        processed_raw_points = pd.DataFrame(val_lists, columns=col_names)

        # Convert columns to correct type
        processed_raw_points['Type'] = processed_raw_points['Type'].apply(lambda x: int(x))
        processed_raw_points['Start Time'] = processed_raw_points['Start Time'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
        processed_raw_points['Day'] = processed_raw_points['Start Time'].apply(lambda x: datetime(year=x.year, month=x.month, day=x.day))

        # Calc Elapsed Time
        processed_raw_points['Elapsed Time'] = processed_raw_points['Start Time'].diff(-1).shift(1)

        # Select dates after start_date, sort
        processed_raw_points = processed_raw_points[processed_raw_points['Start Time'] > start_date]
        processed_raw_points = processed_raw_points.sort_values('Start Time', ascending=True).reset_index()
        processed_raw_points['Elapsed Time'].fillna(0, inplace=True)

        out_data = None

        for day, gdf in processed_raw_points.groupby('Day'):
            print(day)

            activity_found = False

            activities = self.strava_client.get_activities(after=day, before=day+timedelta(days=1))
            for activity in activities:
                if 'ltimate' in activity.name and activity.type == 'Run':
                    team_wins, opponent_wins, color = self.get_strava_description(activity, p=False)
                    activity_found = True
                    print(activity, team_wins, opponent_wins, color)

            if not activity_found:
                team_wins, opponent_wins, color = None, None, None

            events = gdf[['Type', 'Start Time', 'Elapsed Time']].as_matrix().tolist()

            games = process_events(events)

            for g in games:
                g['my_color'] = color
                g['team_wins'] = team_wins
                g['opponent_wins'] = opponent_wins


            games
            df = pd.DataFrame(games).dropna(axis=0)

            df['date'] = df.end_time.apply(lambda x: datetime(x.year, x.month, x.day))
            df = df.set_index(['date', 'game_num'], drop=False)

            ## Convert to team based, not relative to my team
            pdf = df

            pdf['white_wins'] = None
            pdf['color_wins'] = None
            pdf['white_point'] = None
            pdf['color_point'] = None
            pdf['game_winner'] = None


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


            scores = []
            for (date, game_num), game in pdf.iterrows():
                base_dict = dict(date=date, end_time=game.end_time, game_num=game_num, game_winner=game.game_winner)
                scores.append(merge_two_dicts(base_dict, dict(team='white', total_wins=game.white_wins, team_score=game.white_point, my_score=game.my_point if game.my_color == 'white' else None)))
                scores.append(merge_two_dicts(base_dict, dict(team='color', total_wins=game.color_wins, team_score=game.color_point, my_score=game.my_point if game.my_color == 'colors' else None)))

            score_df = pd.DataFrame(scores).set_index(['date', 'game_num', 'team'], drop=False).sort_values('end_time', ascending=False)


            out_df = score_df[['date', 'game_num', 'game_winner', 'team', 'team_score', 'my_score']].fillna(value='').sort_values(['date', 'game_num'], ascending=False)
            out_df['date'] = out_df['date'].apply(lambda x: x.strftime('%Y-%m-%d'))

            data = out_df.as_matrix()

            # "Unstack total wins for output"
            temp = score_df.total_wins.unstack('team')
            total_wins_out = temp.append(temp).sort_index(level='game_num', ascending=False)
            total_wins_out = total_wins_out[['white', 'color']]

            # Insert total_wins in correct location in output data
            data = np.concatenate([data[:,0:1], total_wins_out, data[:,1:]], axis=1)

            if out_data is None:
                out_data = data
            else:
                out_data = np.concatenate([data, out_data], axis=0)

        # wks = self.wkb.worksheet_by_title('game_summaries')
        # wks.insert_rows(2, values=out_data.tolist(), number=len(out_data.tolist()))


        return processed_raw_points, gdf, games, pdf, score_df, out_df, total_wins_out, out_data

## %%


handler = Handler()
%break Handler.raw_to_summary
processed_raw_points, gdf, games, pdf, score_df, out_df, total_wins_out, out_data = handler.raw_to_summary(3)

out_df

gdf

score_df

new_cols = pd.Index(['white', 'color'], name='team')


temp = score_df.total_wins.unstack('team')
total_wins_out = temp.append(temp).sort_index(level='game_num', ascending=False)


data = np.array(data)
out_data = np.concatenate([data[:,0:2], temp, data[:,2:]], axis=1)
np.insert(data, 2, temp.as_matrix, axis=0)


if __name__ == "__main__":
    fire.Fire(Handler)
