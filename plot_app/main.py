import pandas as pd

from bokeh.plotting import figure
from bokeh.layouts import layout, widgetbox
from bokeh.models import ColumnDataSource, Div, WheelZoomTool, PanTool, HoverTool, ResetTool
from bokeh.models.widgets import Slider, Select, TextInput
from bokeh.io import curdoc
from bokeh.palettes import Category20
from datetime import datetime

import itertools

df = pd.read_csv('plot_data.csv', index_col=[0,1,2,3,4])

df = df.unstack(['data_field', 'data_type', 'stat']).sort_index(axis=1)

## get column labels for all levels of df
all_player_names, data_fields, data_types, stats = [list(l) for l in df.columns.levels]


p = figure(plot_height=800, plot_width=1200, title="", x_axis_type='datetime', tools='')

plot_objects = {}
colors = itertools.cycle(Category20[20])

game_counts = {}

for player in all_player_names:
    game_counts[player] = df[player].dropna(axis=0).shape[0]

## Reorder df based on number of games played
all_player_names = list(pd.Series(game_counts).sort_values(ascending=False).index)
df = df[all_player_names]

blocked_players = df.xs(['Game_Won', 'For', 'Avg'], level=['data_field', 'data_type', 'stat'], axis=1).fillna(method='ffill').iloc[-1,:].sort_values().index[0:20]
shown_player_names = [n for n in all_player_names if n not in blocked_players]
df = df[shown_player_names]


for player in shown_player_names:
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

    source = ColumnDataSource(data=dict(name=[], date=[], game_number=[], date_fmt=[], data=[]))
    circle = p.circle(x="date", y="data", source=source, color=color, hover_color=color, name=player, legend=player, size=5)
    line   =   p.line(x="date", y="data", source=source, color=color, hover_line_color=color, legend=player, line_width=line_width, line_dash=line_dash)
    circle.hover_glyph.size=20
    line.hover_glyph.line_width=hover_line_width


    plot_objects[player] = dict(source=source, circle=circle, line=line)


## Build widgets
data_combos = {
    'Total Games Played':          ['Game_Played', 'For', 'Sum'],
    'Total Wins':                  ['Game_Won', 'For', 'Sum'],
    'Cumulative Wins Minus Losses':['Game_Won', 'Delta', 'Sum'],
    'Win Percentage':              ['Game_Won', 'For', 'Avg'],

    'Total Points For':            ['Team_Score', 'For', 'Sum'],
    'Cumulative Points +/-':       ['Team_Score', 'Delta', 'Sum'],
    'Avg Points For Per Game':     ['Team_Score', 'For', 'Avg'],
    'Avg Points +/- Per Game':     ['Team_Score', 'Delta', 'Avg'],
    'Avg Points Against Per Game': ['Team_Score', 'Against', 'Avg'],

    'Avg Points/Game Over Last 6 Matches': ['Team_Score', 'For', 'Rolling_Avg'],
    'Points +/- Over Last 6 Matches': ['Team_Score', 'Delta', 'Rolling_Sum'],
    'Wins in Last 6 Matches': ['Game_Won', 'For', 'Rolling_Sum'],   }

combo_select = Select(title="Stat Type:", value='Win Percentage', options=list(data_combos.keys()))
min_games_slider = Slider(title="Min Games Played", start=0, end=df.shape[0], value=50, step=10)




def select_stats():
    """Function to select appropriate subset of data based on widget inputs"""

    data_df = df.xs(data_combos[combo_select.value], level=['data_field', 'data_type', 'stat'], axis=1)

    min_games = min_games_slider.value

    selected_players = []
    for player, games in game_counts.items():
        if games > min_games:
            selected_players.append(player)

    return data_df, selected_players



def update():
    """Updates plot when widget inputs change"""

    pdf, selected_players = select_stats()

    circles = []

    data_min = None
    data_max = None

    for player in shown_player_names:

        # player = 'Brian'
        player_pdf = pdf[player].dropna(axis=0)

        stat_type = data_combos[combo_select.value][2]

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
        plot_objects[player]['source'].data = dict(
            name=player_pdf.name,
            date=player_pdf.date + player_pdf.game_number * pd.Timedelta(hours=8), ## stagger markers for individual games
            game_number=player_pdf.game_number + 1,
            date_fmt=player_pdf.date_fmt,
            data=player_pdf.data,        )

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
            plot_objects[player]['circle'].visible = True
            plot_objects[player]['line'].visible = True
        else:
            plot_objects[player]['circle'].visible = False
            plot_objects[player]['line'].visible = False

    ## Update bounds when parameter changes
    # from bokeh.models import Range1d
    # p.y_range = Range1d(start=data_min, end=data_max)
    # p.update(y_range=Range1d(start=data_min, end=data_max))
    # p.y_range.bounds = (data_min, data_max)

controls = [min_games_slider, combo_select]

for control in controls:
    control.on_change('value', lambda attr, old, new: update())

sizing_mode = 'fixed'  # 'scale_width' also looks nice with this example

p.legend.location = 'top_left'
p.legend.click_policy = 'hide'
p.legend.glyph_height = 10
p.legend.glyph_width = 10
p.legend.label_text_font_size = '8pt'

wheel_zoom = WheelZoomTool()
pan_tool = PanTool()
hover_tool = HoverTool(
    tooltips = [
        ("Player", '@name'),
        ("Date", "@date_fmt"),
        ("Value", "@data"),
    ]
)


p.add_tools(wheel_zoom, pan_tool, hover_tool, ResetTool())

p.toolbar.active_scroll = wheel_zoom
p.toolbar.active_drag = pan_tool


inputs = widgetbox(*controls, sizing_mode=sizing_mode)
l = layout([
    [],
    [inputs, p]], sizing_mode=sizing_mode)

update()  # initial load of the data

curdoc().add_root(l)
curdoc().title = "Stats"
