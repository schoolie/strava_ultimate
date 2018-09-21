import pandas as pd

from bokeh.plotting import figure
from bokeh.layouts import layout, widgetbox
from bokeh.models import ColumnDataSource, Div, WheelZoomTool, PanTool, HoverTool, ResetTool
from bokeh.models.widgets import Slider, Select, TextInput, DataTable, TableColumn, NumberFormatter
from bokeh.io import curdoc
from bokeh.palettes import Category20
from datetime import datetime

import os
import itertools

## Build widgets
data_combos = {
    'Total Games Played':              (['Game_Played', 'For', 'Sum'], '0'),
    'Total Wins':                      (['Game_Won', 'For', 'Sum'], '0'),
    'Cumulative Wins Minus Losses':    (['Game_Won', 'Delta', 'Sum'], '0'),
    'Win Percentage':                  (['Game_Won', 'For', 'Avg'], '0.0%'),

    'Total Points For':                (['Team_Score', 'For', 'Sum'], '0'),
    'Cumulative Points +/-':           (['Team_Score', 'Delta', 'Sum'], '0'),
    'Avg Points For Per Game':         (['Team_Score', 'For', 'Avg'], '0.00'),
    'Avg Points +/- Per Game':         (['Team_Score', 'Delta', 'Avg'], '0.00'),
    'Avg Points Against Per Game':     (['Team_Score', 'Against', 'Avg'], '0.00'),

    'Avg Points/Game Over Last 6 Matches': (['Team_Score', 'For', 'Rolling_Avg'], '0.00'),
    'Win % Over Last 6 Matches':       (['Game_Won', 'For', 'Rolling_Avg'], '0.0%'),

    'Team Points Over Last 6 Matches': (['Team_Score', 'For', 'Rolling_Sum'], '0'),
    'Points +/- Over Last 6 Matches':  (['Team_Score', 'Delta', 'Rolling_Sum'], '0'),
    'Wins +/- Over Last 6 Matches':    (['Game_Won', 'Delta', 'Rolling_Sum'], '0'),

    'Wins in Last 6 Matches':          (['Game_Won', 'For', 'Rolling_Sum'], '0'),   }
data_combos = data_combos

combo_select = Select(title="Stat Type:", value='Win Percentage', options=list(data_combos.keys()))
min_games_slider = Slider(title="Min Games Played", start=0, end=300, value=50, step=20)

datafiles = []
for name in os.listdir('plot_app/'):
    if '.csv' in name:
        datafiles.append(name)


dataset_select = Select(title="Stat Period:", value='All Time', options=[d.split('.')[0] for d in datafiles])


table_source = ColumnDataSource(data=dict(index=[], name=[], data=[]))


table_columns = [
        TableColumn(field="name", title="Player"),
        TableColumn(field="data", title="Stat", formatter=NumberFormatter(format=data_combos[combo_select.value][1])),
    ]

data_table = DataTable(
    source=table_source,
    columns=table_columns,
    fit_columns=True,
    sortable=True,
    index_position=None,
    width=250,
    height=600)



class Plotter(object):

    def __init__(self):
        self.plot_objects = {}

        self.plot = figure(plot_height=800, plot_width=1200, title="", x_axis_type='datetime', tools='')

        wheel_zoom = WheelZoomTool()
        pan_tool = PanTool()
        hover_tool = HoverTool(
            tooltips = [
                ("Player", '@name'),
                ("Date", "@date_fmt"),
                ("Value", "@data"),
            ]
        )

        self.plot.add_tools(wheel_zoom, pan_tool, hover_tool, ResetTool())

        self.plot.toolbar.active_scroll = wheel_zoom
        self.plot.toolbar.active_drag = pan_tool

    def load_csv(self):

        csv_name = dataset_select.value + '.csv'
        print('loading {}'.format(csv_name))
        self.df = pd.read_csv(os.path.join('plot_app', csv_name), index_col=[0,1,2,3,4])

        self.df = self.df.unstack(['data_field', 'data_type', 'stat']).sort_index(axis=1)

        ## get column labels for all levels of df
        all_player_names, data_fields, data_types, stats = [list(l) for l in self.df.columns.levels]

        # clear all curves before updating
        players_to_remove = []
        for player in self.plot_objects.keys():
            if player in all_player_names:
                ## Update data source
                self.plot_objects[player]['source'].data = dict(
                    name=[],
                    date=[],
                    game_number=[],
                    date_fmt=[],
                    data=[],
                )
            else:
                print(player, 'not in dataset')
                renderers = self.plot_objects[player]
                self.plot.renderers.remove(renderers['circle'])
                self.plot.renderers.remove(renderers['line'])

                for item in plotter.plot.legend[0].items:
                    if item.label['value'] == player:
                        plotter.plot.legend[0].items.remove(item)

                players_to_remove.append(player)

        for player in players_to_remove:
            del self.plot_objects[player]

        colors = itertools.cycle(Category20[20])

        game_counts = {}

        for player in all_player_names:
            game_counts[player] = self.df[player].sum(axis=0)['Game_Played']['For']['Raw']

        self.game_counts = game_counts

        max_games = pd.Series(game_counts).max()
        num_players = len(game_counts)



        ## Find players who have played > 25 games
        if not hasattr(self, 'frequent_player_names'):
            frequent_player_names = []
            for player, games in game_counts.items():
                # if games > max_games * 0.15:
                if games >= 25:
                    frequent_player_names.append(player)
                    self.frequent_player_names = frequent_player_names
        else:
            frequent_player_names = self.frequent_player_names



        ## Reorder df based on number of games played and win percentage
        blocked_players = self.df.xs(['Game_Won', 'For', 'Avg'], level=['data_field', 'data_type', 'stat'], axis=1).fillna(method='ffill').iloc[-1,:].sort_values().index[0:int(num_players/3)]
        blocked_players = [n for n in blocked_players if (n in frequent_player_names) and (n in all_player_names)]
        shown_players = [n for n in frequent_player_names if (n not in blocked_players) and (n in all_player_names)]

        shown_players = list(pd.Series(game_counts)[shown_players].sort_values(ascending=False).index)
        blocked_players = list(pd.Series(game_counts)[blocked_players].sort_values(ascending=False).index)
        all_player_names = shown_players + blocked_players

        self.blocked_players = blocked_players
        self.all_player_names = all_player_names

        self.df = self.df[all_player_names]
        print(self.df.shape)


        # Add curves that aren't in dataset yet
        for player in all_player_names:
            if player not in self.plot_objects.keys():
                if player == 'White_Team':
                    color = 'black'
                    line_width = 4
                    hover_line_width = 8
                    line_dash = 'dotted'
                elif player == 'Color_Team':
                    color = 'black'
                    line_width = 4
                    hover_line_width = 8
                    line_dash = 'solid'
                else:
                    color=next(colors)
                    line_width = 2
                    hover_line_width = 4
                    line_dash = 'solid'

                self.source = ColumnDataSource(data=dict(name=[], date=[], game_number=[], date_fmt=[], data=[]))
                circle = self.plot.circle(x="date", y="data", source=self.source, color=color, hover_color=color, name=player, legend=player, size=5)
                line   = self.plot.line(x="date", y="data", source=self.source, color=color, hover_line_color=color, legend=player, line_width=line_width, line_dash=line_dash)
                circle.hover_glyph.size=20
                line.hover_glyph.line_width=hover_line_width


                self.plot_objects[player] = dict(source=self.source, circle=circle, line=line)


        self.plot.legend.location = 'top_left'
        self.plot.legend.click_policy = 'hide'
        self.plot.legend.glyph_height = 10
        self.plot.legend.glyph_width = 10
        self.plot.legend.label_text_font_size = '8pt'

        ## update slider (triggers callback for update())
        min_games_slider.end = max_games
        if csv_name != 'All Time.csv':
            min_games_slider.value = int((max_games / 2))
        else:
            min_games_slider.value = 50


    def select_stats(self):
        """Function to select appropriate subset of data based on widget inputs"""

        data_df = self.df.xs(data_combos[combo_select.value][0], level=['data_field', 'data_type', 'stat'], axis=1)

        min_games = min_games_slider.value

        selected_players = []
        for player, games in self.game_counts.items():
            if (games > min_games) and (player not in self.blocked_players):
                selected_players.append(player)

        return data_df, selected_players


    def update(self):
        """Updates plot when widget inputs change"""

        table_columns[1].formatter=NumberFormatter(format=data_combos[combo_select.value][1])

        pdf, selected_players = self.select_stats()

        circles = []

        data_min = None
        data_max = None


        display_data = []

        for player in self.all_player_names:

            # player = 'Brian'
            player_pdf = pdf[player].dropna(axis=0)

            stat_type = data_combos[combo_select.value][0][2]

            ## reindex
            player_pdf = player_pdf.reset_index()[['Date', 'Game_Number', player]]
            player_pdf.columns = ['date', 'game_number', 'data']
            player_pdf['date_fmt'] = player_pdf['date']
            player_pdf['date'] = player_pdf['date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))


            ## only keep last game from day
            last_game_levels = list(player_pdf.groupby('date').max().reset_index()[['date', 'game_number']].itertuples(index=False))
            last_game_names = ['date', 'game_number']
            last_game_index = pd.MultiIndex.from_tuples(last_game_levels, names=last_game_names)
            player_pdf = player_pdf.set_index(['date', 'game_number']).reindex(last_game_index).reset_index()

            player_pdf['name'] = player

            ## Update data source
            self.plot_objects[player]['source'].data = dict(
                name=player_pdf.name,
                date=player_pdf.date + player_pdf.game_number * pd.Timedelta(hours=8), ## stagger markers for individual games
                game_number=player_pdf.game_number + 1,
                date_fmt=player_pdf.date_fmt,
                data=player_pdf.data,
            )



            ## Calc new y_axis range
            min_ = player_pdf.data.min()
            max_ = player_pdf.data.max()
            range_ = max_ - min_

            smin = min_ - range_ * 0.1
            smax = max_ + range_ * 0.1
            if data_min is not None:
                data_min = min(data_min, smin)
                data_max = max(data_max, smax)
            else:
                data_min = smin
                data_max = smax

            ## Update line visibility
            if player in selected_players:
                # store latest value for each player
                display_data.append([player, player_pdf.data.iloc[-1]])

                self.plot_objects[player]['circle'].visible = True
                self.plot_objects[player]['line'].visible = True
            else:
                self.plot_objects[player]['circle'].visible = False
                self.plot_objects[player]['line'].visible = False

        ## Update bounds when parameter changes
        # from bokeh.models import Range1d
        # self.plot.y_range = Range1d(start=data_min, end=data_max)
        # p.update(y_range=Range1d(start=data_min, end=data_max))
        # self.plot.y_range.bounds = (data_min, data_max)

        display_data = pd.DataFrame(display_data, columns=['name', 'data']).sort_values('data', ascending=False)
        display_data = display_data.to_dict('list')

        table_source.data = display_data

## %%

plotter = Plotter()
plotter.load_csv()

dir(plotter.plot)
dir(plotter.plot.legend)


dataset_select.on_change('value', lambda attr, old, new: plotter.load_csv())

controls = [min_games_slider, combo_select]
for control in controls:
    control.on_change('value', lambda attr, old, new: plotter.update())

controls = [dataset_select] + controls


sizing_mode = 'fixed'  # 'scale_width' also looks nice with this example

inputs = layout([
    widgetbox(*controls, sizing_mode=sizing_mode),
    data_table])

l = layout([
    [],
    [inputs, plotter.plot]], sizing_mode=sizing_mode)

plotter.update()  # initial load of the data

#  %break Plotter.update

curdoc().add_root(l)
curdoc().title = "Stats"
