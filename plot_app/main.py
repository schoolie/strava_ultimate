import pandas as pd
import numpy as np

from bokeh.plotting import figure, show
from bokeh.layouts import layout, widgetbox
from bokeh.models import ColumnDataSource, WheelZoomTool, PanTool, TapTool, HoverTool, ResetTool, Circle
from bokeh.models.widgets import Slider, Select, TextInput, DataTable, TableColumn, NumberFormatter
from bokeh.io import curdoc
from bokeh.palettes import Category20
from datetime import datetime

from bokeh.layouts import layout, widgetbox, Row, Column
from bokeh.models import Panel
from bokeh.models.widgets import Tabs

import os
import itertools

## Build widgets
data_combos = {
    'Total Games Played':              (['Game_Played', 'For', 'Sum'], '0'),
    'Total Wins':                      (['Game_Won', 'For', 'Sum'], '0'),
    'Cumulative Wins Minus Losses':    (['Game_Won', 'Delta', 'Sum'], '0'),
    'Weighted Wins Minus Losses':      (['Win_Value', 'Delta', 'Sum'], '0.00'),
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



class StatPanel(object):
    def __init__(self, csv_name, min_games_played=None):

        # csv_name = 'Summer 2018.csv'
        ## Load data, pivot
        df = pd.read_csv(os.path.join('plot_app', csv_name), index_col=[0,1,2,3,4])
        df = df.unstack(['data_field', 'data_type', 'stat']).sort_index(axis=1)

        all_player_names, data_fields, data_types, stats = [list(l) for l in df.columns.levels]

        dataset_name = csv_name[0:-4]

        games_played = df.fillna(method='ffill').reorder_levels([1,2,3,0], axis='columns').Game_Played.For.Sum.iloc[-1]
        max_games_played = games_played.max()

        if min_games_played is None:
            min_games_played = int(max_games_played / 2)

        games_played = games_played[games_played >= min_games_played]
        games_played = games_played.sort_values(ascending=False)

        player_names = list(games_played.index)

        combo_select = Select(title="Stat Type:", value='Win Percentage', options=list(data_combos.keys()))
        min_games_slider = Slider(title="Min Games Played", start=0, end=max_games_played, value=min_games_played, step=5)

        # controls = [min_games_slider, combo_select]
        # for control in controls:
        #     control.on_change('value', lambda attr, old, new: self.update())

        ## limit df to players that have played more than the minimum games_played
        df = df[player_names]
        win_percentages = df.fillna(method='ffill').reorder_levels([1,2,3,0], axis='columns').Game_Won.For.Avg.iloc[-1]

        shown_player_count = int(len(player_names) * 3 / 4)
        shown_players = list(win_percentages.sort_values(ascending=False).iloc[0:shown_player_count].index)
        blocked_players = list(win_percentages.sort_values(ascending=False).iloc[shown_player_count:-1].index)

        ##store to self
        self.df = df
        self.dataset_name = dataset_name
        self.combo_select = combo_select
        self.min_games_slider = min_games_slider
        self.source = None
        self.interp_source = None
        self.table_source = None

        self.games_played = games_played
        self.shown_players = shown_players
        self.blocked_players = blocked_players
        self.player_names = player_names

        self.min_games_slider.on_change('value', lambda attr, old, new: self.update())
        self.combo_select.on_change('value', lambda attr, old, new: self.update())

        self.circle_renderers = {}
        self.line_renderers = {}


    def update(self):

        ## Update table formatting
        try:
            format_string = data_combos[self.combo_select.value][1]
            self.table_columns[1].formatter=NumberFormatter(format=format_string)
        except AttributeError:
            pass

        df = self.df
        combo_select = self.combo_select
        shown_players = self.shown_players
        games_played = self.games_played

        ## Select correct level of data
        data_df = df.xs(data_combos[combo_select.value][0], level=['data_field', 'data_type', 'stat'], axis=1)

        ## Reformat for CDS
        data_df = data_df.reset_index()

        ## only keep last game from day
        # a = data_df.values
        # dates = np.unique(a[:, 0], return_counts=True)
        # last_game_levels = np.array([dates[0], dates[1] - 1]).T.tolist()
        #
        # last_game_names = ['Date', 'Game_Number']
        # last_game_index = pd.MultiIndex.from_tuples(last_game_levels, names=last_game_names)
        #
        # red_df = data_df.set_index(['Date', 'Game_Number']).reindex(last_game_index).reset_index()

        red_df = data_df.groupby('Date').last().reset_index()
        red_df['Date_String'] = red_df.Date
        red_df['Date'] = pd.to_datetime(red_df.Date)

        ## Interpolate
        interp_df = red_df.interpolate()

        ## Build Data for data_table
        table_df = interp_df.iloc[:,2:].iloc[-1:]
        table_df = table_df[shown_players].T
        table_df['games_played'] = games_played

        table_df = table_df.reset_index()
        table_df.columns = ['name', 'data', 'games_played']
        table_df = table_df.sort_values('data', ascending=False)

        # Filter data table
        game_cutoff = self.min_games_slider.value
        table_df = table_df[table_df.games_played >= game_cutoff]

        ## Update CDS
        if self.source is None:
            self.source = ColumnDataSource(red_df)
            self.interp_source = ColumnDataSource(interp_df)
            self.table_source = ColumnDataSource(table_df)

        else:
            self.source.data = self.source.from_df(red_df)
            self.interp_source.data = self.interp_source.from_df(interp_df)
            self.table_source.data = self.table_source.from_df(table_df)


        for name, count in self.games_played.iteritems():
            try:
                if name in self.shown_players:
                    self.circle_renderers[name].visible = (count >= self.min_games_slider.value)
                    self.line_renderers[name].visible = (count >= self.min_games_slider.value)
                else:                    
                    self.circle_renderers[name].visible = False
                    self.line_renderers[name].visible = False
                    
            except KeyError:
                print(name)

    def build_plot(self):

        ## Build tools
        wheel_zoom = WheelZoomTool()
        pan_tool = PanTool()

        tools = [wheel_zoom, pan_tool, ResetTool()]


        ## Build Figure
        colors = itertools.cycle(Category20[20])

        fig = figure(plot_width=1200, plot_height=600, tools=tools, x_axis_type='datetime')


        fig.toolbar.active_scroll = wheel_zoom
        fig.toolbar.active_drag = pan_tool


        for name in self.player_names:

            if name == 'White_Team':
                color = 'black'
                line_width = 4
                hover_line_width = 8
                line_dash = 'dotted'
            elif name == 'Color_Team':
                color = 'black'
                line_width = 4
                hover_line_width = 8
                line_dash = 'solid'
            else:
                color=next(colors)
                line_width = 2
                hover_line_width = 4
                line_dash = 'solid'

            if name in self.shown_players:
                if self.games_played[name] >= self.min_games_slider.value:
                    visible = True
                else:
                    visible = False
            else:
                visible = False

            circle = fig.circle(
                x='Date',
                y=name,
                source=self.source,
                name=name,
                legend='{} '.format(name),
                color=color,
                hover_color=color,
                size=8)


            line = fig.line(
                x='Date',
                y=name,
                source=self.interp_source,
                legend='{} '.format(name),
                color=color,
                hover_line_color=color,
                line_width=line_width,
                line_dash=line_dash)

            circle.visible = visible
            line.visible = visible

            circle.hover_glyph.size=20
            line.hover_glyph.line_width=hover_line_width

            self.circle_renderers[name] = circle
            self.line_renderers[name] = line

            hover_tool = HoverTool(
                tooltips = [
                    ("Player", name),
                    ("Date", "@Date_String"),
                    ("Value", "@{}".format(name)),
                ],
                # names=[name],
                renderers=[circle],
            )

            fig.add_tools(hover_tool)


        fig.legend.location = 'top_left'
        fig.legend.click_policy = 'hide'
        fig.legend.glyph_height = 10
        fig.legend.glyph_width = 10
        fig.legend.label_text_font_size = '8pt'

        fig.toolbar.logo = None
        fig.toolbar_location = None

        ## Build data table
        # table_source = ColumnDataSource(data=dict(index=[], name=[], data=[], games_played=[]))

        table_columns = [
        TableColumn(field="name", title="Player"),
        TableColumn(field="data", title="Stat", formatter=NumberFormatter(format=data_combos[self.combo_select.value][1])),]

        self.table_columns = table_columns
        data_table = DataTable(
            source=self.table_source,
            columns=self.table_columns,
            fit_columns=True,
            sortable=True,
            index_position=None,
            width=250,
            height=600)

        self.fig = fig
        self.data_table = data_table


## Find csv files
csv_names = []
for name in os.listdir('plot_app/'):
    if '.csv' in name:
        csv_names.append(name)


## Build Panels
panel_handlers = []
for csv_name in csv_names:
    if csv_name == 'All Time.csv':
        min_games_played = 20
    else:
        min_games_played = None

    panel = StatPanel(csv_name, min_games_played=min_games_played)
    panel.update()
    panel.build_plot()

    panel_handlers.append(panel)


panels = []
for panel_handler in panel_handlers:
    panel = Panel(title=panel_handler.dataset_name,
               child=Row(
                    Column(panel_handler.combo_select, panel_handler.min_games_slider, panel_handler.data_table),
                    Column(panel_handler.fig)
               ))

    panels.append(panel)

tabs = Tabs(tabs=panels)

curdoc().add_root(tabs)
curdoc().title = "Stats"
