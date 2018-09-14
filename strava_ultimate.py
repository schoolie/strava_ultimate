
# coding: utf-8

# In[1]:

from flask import Flask, redirect, request, render_template
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
import itertools
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
    def __init__(self, load_strava=True):

        if load_strava:
            #### Setting up strava API client
            ## Read Strava secret file

            strava_client = stravalib.client.Client()

            ## check if strava auth code has been stored yet
            if not os.path.exists('strava_secrets.json'):
                print('No Strava credentials stored')

                host_url = os.environ['HOST_URL']

                authorize_url = strava_client.authorization_url(
                    client_id=19435,
                    redirect_uri='{}/strava_auth'.format(host_url)
                )

                self.strava_auth_url = authorize_url

                return


            with open('strava_secrets.json') as json_data:
                strava_secrets = json.load(json_data)

            ## Enable accessing private activities
            code = strava_secrets['auth_code']
            access_token = strava_client.exchange_code_for_token(client_id=19435, client_secret=os.environ['STRAVA_CLIENT_SECRET'], code=code)
            strava_client = stravalib.client.Client(access_token=access_token)
            athlete = strava_client.get_athlete()
            # print('athlete name %s, athlete id %s.' %(athlete.firstname, athlete.id

            self.athlete = athlete
            self.strava_client = strava_client

        ## Set up google sheets client, open worksheet

        # - Opens browser window, produces sheets.googleapis.com-python.json ... need to figure out how to productionize?
        gc = pygsheets.authorize(outh_file='gsheet_secret.json', no_cache=False, outh_nonlocal=True)

        # Open spreadsheet and then workseet
        wkb = gc.open('Milburn Ultimate Scores')


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

            point_df['date'] = point_df['start_time'].apply(lambda x: x.strftime('%Y-%m-%d'))
            point_df['start_time'] = point_df['start_time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
            point_df['elapsed_time'] = point_df['elapsed_time'].apply(lambda x: x.seconds)


            data = point_df[['date', 'count', 'start_time']].sort_index(ascending=False).as_matrix().tolist()
            all_data = all_data + data

        return all_data

    def get_last_raw_entry(self, debug_days=0):
        """
        Get last entry from Raw Point Spreadsheet
        """

        wks = self.wkb.worksheet_by_title('raw_points')

        dates = wks.get_col(3)
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

        return len(raw_points)

    ## Get last entry from Data Spreadsheet
    def raw_to_summary(self, debug_days=0, write_out=True):

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
        col_names = all_values[1][1:3]

        # read values, discard formulas
        val_lists = all_values[3:]
        val_lists = [v[1:3] for v in val_lists]

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

        ## Remove large timedeltas between days
        processed_raw_points.loc[processed_raw_points['Elapsed Time'] > timedelta(days=1), 'Elapsed Time'] = timedelta(seconds=0)

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

        if out_data is not None:
            if write_out:
                wks = self.wkb.worksheet_by_title('game_summaries')
                wks.insert_rows(2, values=out_data.tolist(), number=len(out_data.tolist()))


            return out_df.game_num.max() + 1

        else:
            return 0

    def read_scoreboard(self):

        ## Get date column from summary sheet
        game_sheet = self.wkb.worksheet_by_title('game_summaries')
        dates = game_sheet.get_col(1)
        headings = game_sheet.get_row(2)

        dates_recorded = [datetime.strptime(d, '%Y-%m-%d') for d in dates if d != '' and d != 'Date']

        for n, d in enumerate(dates_recorded):
            if d > datetime(year=2017, month=12, day=21):
                last_row = n + 2 + 1
        last_row

        for n, h in enumerate(headings):
            if len(h) > 0:
                try:
                    int(h)  ## Skip number columns at right
                except ValueError:
                    last_col = n + 1
        last_col

        # get all game values
        columns = game_sheet.get_values((2, 1), (2, last_col))[0]
        all_values  = game_sheet.get_values((3, 1), (last_row, last_col))

        clean_columns = []
        for c in columns:
            clean_columns.append(c.replace(' ', '_').replace('(', '_').replace(')', '_'))

        player_names = clean_columns[7:]

        df = pd.DataFrame(all_values, columns=clean_columns)

        df = df.set_index(['Date', 'Game_Number', 'Team']).unstack('Team')
        df['Wins', 'white'] = df.White_Wins.white
        df['Wins', 'color'] = df.Color_Wins.color
        df = df.drop(['White_Wins', 'Color_Wins'], axis=1)
        df = df.sort_index(ascending=False)
        df = df.stack('Team')

        # Count players on each team
        player_counts = (df[player_names] != "").sum(axis=1).unstack('Team').sort_index(ascending=False)
        df['player_count'] = player_counts.stack('Team')

        ## Create boolean column for wins
        tdf = df.unstack('Team')
        tdf.loc[:,('Game_Won', 'color')] = tdf['Winner']['color'] == 'Color'
        tdf.loc[:,('Game_Won', 'white')] = tdf['Winner']['white'] == 'White'

        # Create numerical win tracking
        tdf.loc[:,('Win_Value_Multiplier', 'color')] = 1
        tdf.loc[:,('Win_Value_Multiplier', 'white')] = 1

        tdf.loc[tdf.Team_Score.max(axis=1) < 5, 'Win_Value_Multiplier'] = 0.6


        df = tdf.stack('Team')
        df['Win_Value'] = df.Game_Won.astype(int) * df.Win_Value_Multiplier


        temp = (df[player_names] != '') * 1

        temp_df = df.copy()
        temp_df[player_names] = temp[player_names]
        pdf = temp_df[player_names + ['Game_Won', 'Win_Value']].astype(float).groupby(['Date', 'Team']).sum()

        match_df = pdf.unstack('Team')

        match_df.loc[:,('Match_Won_Weighted', 'color')] = match_df['Win_Value']['color'] > match_df['Win_Value']['white']
        match_df.loc[:,('Match_Won_Weighted', 'white')] = match_df['Win_Value']['white'] > match_df['Win_Value']['color']

        match_df.loc[:,('Match_Tied_Weighted', 'color')] = match_df['Win_Value']['color'] == match_df['Win_Value']['white']
        match_df.loc[:,('Match_Tied_Weighted', 'white')] = match_df['Win_Value']['white'] == match_df['Win_Value']['color']

        match_df.loc[:,('Match_Won', 'color')] = match_df['Win_Value']['color'] > match_df['Win_Value']['white']
        match_df.loc[:,('Match_Won', 'white')] = match_df['Win_Value']['white'] > match_df['Win_Value']['color']

        match_df.loc[:,('Match_Tied', 'color')] = match_df['Win_Value']['color'] == match_df['Win_Value']['white']
        match_df.loc[:,('Match_Tied', 'white')] = match_df['Win_Value']['white'] == match_df['Win_Value']['color']

        match_df = match_df.stack('Team') ### numerical wins tallied

        return df, match_df, player_names

    def get_player_scoreboards(self, game_scoreboard, match_scoreboard, name):

        filt_index = game_scoreboard[game_scoreboard[name] != ''].index

        ### create game_scoreboard of games played by player
        new_index = filt_index

        # create new team labels that include both teams
        team_labels = [0,1] * int(new_index.labels[0].shape[0])

        new_labels = []
        # duplicate date and game_num labels to match new team labels
        for n in range(2):
            temp = new_index.labels[n]
            new = []
            for t in temp:
                new.append(t)
                new.append(t)

            new_labels.append(new)

        new_labels.append(team_labels)

        new_index = pd.MultiIndex(levels=new_index.levels, labels=new_labels, names=new_index.names)


        ### create df of matches played by player
        new_match_index = filt_index

        # create new team labels that include both teams

        new_match_labels = [[], []]
        # duplicate date and game_num labels to match new team labels
        for date, game_num, team in zip(*new_index.labels):
            if game_num == 0:
                new_match_labels[0].append(date)
                new_match_labels[1].append(team)

        new_match_index = pd.MultiIndex(
            levels=[filt_index.levels[0], filt_index.levels[2]],
            labels=new_match_labels,
            names=[filt_index.names[0], filt_index.names[2]],)


        player_df = game_scoreboard.reindex(index=new_index)
        player_match_df = match_scoreboard.reindex(index=new_match_index)

        return player_df, player_match_df

    def summary_stats(self, start_date=None, end_date=None, write_to_google=True, csv_name='All Time.csv'):

        # Get data from drive, format
        game_scoreboard, match_scoreboard, player_names = self.read_scoreboard()

        if start_date is not None:
            game_scoreboard = game_scoreboard.loc[start_date:, :]
        if end_date is not None:
            game_scoreboard = game_scoreboard.loc[:end_date, :]

        game_scoreboard

        player_stats = {}
        plot_data = {}

        columns = ['White_Team', 'Color_Team'] + list(game_scoreboard.columns)
        game_scoreboard['White_Team'] = ''
        game_scoreboard['Color_Team'] = ''
        game_scoreboard = game_scoreboard[columns]
        game_scoreboard.loc[(slice(None), slice(None), ['white']), 'White_Team'] = 'x'
        game_scoreboard.loc[(slice(None), slice(None), ['color']), 'Color_Team'] = 'x'

        game_scoreboard.head()

        for name in ['White_Team', 'Color_Team'] + player_names:
            print(name)
            
            player_game_scoreboard, player_match_scoreboard = self.get_player_scoreboards(game_scoreboard, match_scoreboard, name)

            games_played = (player_game_scoreboard[name] != '').sum()

            if games_played > 0:

                games_won = np.all([player_game_scoreboard[name] != '', player_game_scoreboard['Game_Won']], axis=0).sum()
                games_lost = np.all([player_game_scoreboard[name] != '', ~player_game_scoreboard['Game_Won']], axis=0).sum()
                win_pct = games_won / games_played * 100

                games_color = (player_game_scoreboard.xs('color', level=2)[name] != '').sum()
                games_white = (player_game_scoreboard.xs('white', level=2)[name] != '').sum()
                pct_color = games_color / games_played * 100
                pct_white = games_white / games_played * 100

                team_score_for = player_game_scoreboard['Team_Score'][player_game_scoreboard[name] != ''].astype(int).sum()
                team_score_against = player_game_scoreboard['Team_Score'][player_game_scoreboard[name] == ''].astype(int).sum()



                ## Calc scores for and against
                team_score_for = player_game_scoreboard['Team_Score'][player_game_scoreboard[name] != ''].astype(int).sum()
                team_score_against = player_game_scoreboard['Team_Score'][player_game_scoreboard[name] == ''].astype(int).sum()
                team_plus_minus = team_score_for - team_score_against

                if player_match_scoreboard.shape[0] > 0 and name not in ['White_Team', 'Color_Team']:  # make sure player has played at least one complete match

                    ## Calc total matches played
                    player_match_wins = player_match_scoreboard[[name, 'Match_Won', 'Match_Won_Weighted', 'Match_Tied', 'Match_Tied_Weighted']].unstack('Team')
                    consistent_team = ~np.all(player_match_wins[name] != 0, axis=1)

                    color_matches_won = np.all([player_match_wins[name]['color'] != 0, player_match_wins['Match_Won']['color'], consistent_team], axis=0).sum()
                    white_matches_won = np.all([player_match_wins[name]['white'] != 0, player_match_wins['Match_Won']['white'], consistent_team], axis=0).sum()
                    total_matches_won = color_matches_won + white_matches_won

                    color_matches_tied = np.all([player_match_wins[name]['color'] != 0, player_match_wins['Match_Tied']['color'], consistent_team], axis=0).sum()
                    white_matches_tied = np.all([player_match_wins[name]['white'] != 0, player_match_wins['Match_Tied']['white'], consistent_team], axis=0).sum()
                    total_matches_tied = color_matches_tied + white_matches_tied

                    days_played = consistent_team.shape[0]
                    matches_played = consistent_team.sum()

                    total_matches_lost = matches_played - total_matches_won - total_matches_tied

                    match_win_percent = total_matches_won / matches_played * 100

                else:
                    days_played = 0
                    matches_played = 0
                    total_matches_won = 0
                    total_matches_lost = 0
                    total_matches_tied = 0
                    match_win_percent = 0

                player_stats[name] = [
                    games_played,
                    games_won,
                    games_lost,
                    win_pct,
                    games_color,
                    games_white,
                    pct_color,
                    pct_white,
                    team_score_for,
                    team_score_against,
                    team_plus_minus,
                    days_played,
                    matches_played,
                    total_matches_won,
                    total_matches_tied,
                    total_matches_lost,
                    match_win_percent,]

                # game_count = player_game_scoreboard.reset_index().set_index(['Date', 'Team'])[['Game_Number']].groupby('Date').max()
                # game_count['Game_Count'] = game_count.Game_Number.astype(int) + 1
                # game_count
                numerical = player_game_scoreboard[['Team_Score','Game_Won','Win_Value']]

                numerical_team = numerical[player_game_scoreboard[name] != ''].astype(float).reset_index('Team').drop('Team', axis=1)
                numerical_opponent = numerical[player_game_scoreboard[name] == ''].astype(float).reset_index('Team').drop('Team', axis=1)

                numerical_team['Players_Team'] = 1
                numerical_team['Game_Played'] = 1
                numerical_opponent['Players_Team'] = 0
                numerical_opponent['Game_Played'] = 0

                player_numerical = pd.concat([numerical_team, numerical_opponent]).set_index('Players_Team', append=True).sort_index()

                def cummean(data):
                    return np.cumsum(data) / np.cumsum(np.ones(data.shape))

                def passthrough(data):
                    return data

                def rollingmean(data):
                    data = for_data
                    temp = data.reset_index('Game_Number') ## get date index without game number
                    out = data.groupby('Date').mean().rolling(6).mean().reindex(temp.index) # groupby date, rolling average, expand to match dates from original
                    out = pd.DataFrame(out)  # convert from pd.Series

                    out['Game_Number'] = temp.Game_Number   ## add Game_Number info back to df
                    out = out.set_index('Game_Number', append=True)  ## set index back to original

                    return out.iloc[:,0]   ## return as pd.Series

                def rollingsum(data):

                    temp = data.reset_index('Game_Number') ## get date index without game number
                    out = data.groupby('Date').sum().rolling(6).sum().reindex(temp.index) # groupby date, rolling average, expand to match dates from original
                    out = pd.DataFrame(out)  # convert from pd.Series

                    out['Game_Number'] = temp.Game_Number   ## add Game_Number info back to df
                    out = out.set_index('Game_Number', append=True)  ## set index back to original

                    return out.iloc[:,0]   ## return as pd.Series

                data_stats = {}
                for data_field in ['Team_Score', 'Game_Played', 'Game_Won', 'Win_Value']:

                    for_data = player_numerical[data_field].xs(1, level='Players_Team')
                    against_data = player_numerical[data_field].xs(0, level='Players_Team')
                    delta_data = for_data - against_data

                    for_stats = {}
                    against_stats = {}
                    delta_stats = {}

                    for stat, func in zip(
                        ['Sum', 'Avg', 'Raw', 'Rolling_Avg', 'Rolling_Sum'],
                        [np.cumsum, cummean, passthrough, rollingmean, rollingsum]):

                        for_stats[stat] = func(for_data)
                        against_stats[stat] = func(against_data)
                        delta_stats[stat] = func(delta_data)

                    data_stats[data_field] = dict(Delta=delta_stats, For=for_stats, Against=against_stats)

                plot_data[name] = data_stats

        ### Format and write data for bokeh app
        reformed_plot_data = {}
        for name, data_stats in plot_data.items():
            for data_field, calc_data in data_stats.items():
                for data_type, stats in calc_data.items():
                    for stat, data in stats.items():
                        reformed_plot_data[(name, data_field, data_type, stat)] = data

        plot_data_df = pd.DataFrame(reformed_plot_data)
        plot_data_df.columns.names = ['name', 'data_field', 'data_type', 'stat']

        ### Write to csv for bokeh app
        plot_data_df.stack(['data_field', 'data_type', 'stat']).to_csv(csv_name)

        param_names = [
            'Games Played',
            'Games Won',
            'Games Lost',
            'Win Percent',
            'Games Color',
            'Games White',
            'Percent Color',
            'Percent White',
            'Score For',
            'Score Against',
            'Score +/-',
            'Days Played',
            'Matches Played',
            'Matches Won',
            'Matches Tied',
            'Matches Lost',
            'Match Win %']

        stats_df = pd.DataFrame(player_stats, index=param_names)
        stats_df = stats_df[['White_Team', 'Color_Team'] + player_names]
        stats_df = stats_df.T.sort_values('Games Played', ascending=False)

        ## Replace losers with blanks :)
        blank = ''
        stats_df.loc[stats_df['Win Percent'] < 50, 'Win Percent'] = blank
        stats_df.loc[stats_df['Match Win %'] < 50, 'Match Win %'] = blank
        stats_df.loc[stats_df['Score +/-'] < 0, 'Score +/-'] = blank

        if write_to_google:
            ## Write data to spreadsheet
            wks = self.wkb.worksheet_by_title('summary_stats')
            wks.update_cells('B3', [[x] for x in stats_df.index.tolist()])
            wks.update_cells('C3', stats_df.as_matrix().tolist())
            wks.update_cells('C2', [stats_df.columns.tolist()])


## %%

### Define Flask app and routes

app = Flask(__name__)

@app.route('/strava_auth')
def store_strava_credentials():

    code = request.args.get('code')

    with open('strava_secrets.json', 'w') as outfile:
        json.dump(dict(auth_code=code), outfile)

    return(render_template('links.html'))

@app.route('/strava_to_gsheet', defaults={'debug_days': 0})
@app.route('/strava_to_gsheet/<debug_days>')
def strava_to_gsheet(debug_days=0):

    handler = Handler()
    # Check if strava credentials are stored, get if necessary
    if hasattr(handler, 'strava_auth_url'):
        return redirect(handler.strava_auth_url)

    debug_days = int(debug_days)
    points = handler.strava_to_gsheet(debug_days=debug_days)

    return '{} points found'.format(points)


@app.route('/raw_to_summary', defaults={'debug_days': 0})
@app.route('/raw_to_summary/<debug_days>')
def raw_to_summary(debug_days=0):

    handler = Handler()
    # Check if strava credentials are stored, get if necessary
    if hasattr(handler, 'strava_auth_url'):
        return redirect(handler.strava_auth_url)

    debug_days = int(debug_days)
    games = handler.raw_to_summary(debug_days=debug_days)

    return '{} games found'.format(games)

@app.route('/summary_stats')
def summary_stats():

    handler = Handler(load_strava=False)

    seasons = [
        (True, 'All Time', None, None),
        (False, 'Spring 2018', '2018-03-20', '2018-06-20'),
        (False, 'Summer 2018', '2018-06-21', '2018-09-22'),
    ]

    for write, name, start, end in seasons:
        games = handler.summary_stats(
            write_to_google=write,
            csv_name='{}.csv'.format(name),
            start_date=start,
            end_date=end
        )

    return 'summaries calculated'
summary_stats()

if __name__ == "__main__":
    fire.Fire(Handler)
