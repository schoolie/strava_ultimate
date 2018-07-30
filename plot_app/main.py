import pandas as pd

from bokeh.plotting import figure
from bokeh.layouts import layout, widgetbox
from bokeh.models import ColumnDataSource, Div, WheelZoomTool, PanTool, HoverTool
from bokeh.models.widgets import Slider, Select, TextInput
from bokeh.io import curdoc
from bokeh.palettes import Category20
from datetime import datetime

import itertools

df = pd.read_csv('plot_data.csv', index_col=[0,1,2,3,4])

df = df.unstack(['data_field', 'data_type', 'stat']).sort_index(axis=1)

df.Brian.dropna(axis=0).shape
df.Brad.dropna(axis=0).shape

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

for player in all_player_names:
    color=next(colors)
    source = ColumnDataSource(data=dict(name=[], date=[], date_fmt=[], data=[]))
    circle = p.circle(x="date", y="data", source=source, size=7, color=color, hover_color=color, name=player, legend=player)
    line = p.line(x="date", y="data", source=source, color=color, hover_line_color=color, legend=player)
    circle.hover_glyph.size=20
    line.hover_glyph.line_width=4


    plot_objects[player] = dict(source=source, circle=circle, line=line)



min_games_slider = Slider(title="Min Games Played", start=0, end=df.shape[0], value=70, step=10)
# data_field_select = Select(title="Data Field:", value='Game_Won', options=data_fields)
# data_type_select = Select(title="Data Type:", value='Delta', options=data_types)
# stat_select = Select(title="Stat Type:", value='Sum', options=stats)

data_combos = {
    'Total Wins':                  ['Game_Won', 'For', 'Sum'],
    'Cumulative Wins Minus Losses':['Game_Won', 'Delta', 'Sum'],
    'Win Percentage':              ['Game_Won', 'For', 'Avg'],

    'Total Points For':            ['Team_Score', 'For', 'Sum'],
    'Cumulative Points +/-':       ['Team_Score', 'Delta', 'Sum'],
    'Avg Points For Per Game':     ['Team_Score', 'For', 'Avg'],
    'Avg Points +/- Per Game':     ['Team_Score', 'Delta', 'Avg'],
    'Avg Points Against Per Game': ['Team_Score', 'Against', 'Avg'],

}

combo_select = Select(title="Stat Type:", value='Win Percentage', options=list(data_combos.keys()))


# Create Column Data Source that will be used by the plot




def select_stats():
    # data_df = df.xs([data_field_select.value, data_type_select.value, stat_select.value], level=['data_field', 'data_type', 'stat'], axis=1)
    data_df = df.xs(data_combos[combo_select.value], level=['data_field', 'data_type', 'stat'], axis=1)

    min_games = min_games_slider.value

    selected_players = []
    for player, games in game_counts.items():
        if games > min_games:
            selected_players.append(player)

    return data_df, selected_players



def update():
    pdf, selected_players = select_stats()

    circles = []

    for player in all_player_names:

        # player = 'Brian'
        player_pdf = pdf[player].dropna(axis=0)

        stat_type = data_combos[combo_select.value][2]
        if stat_type == 'Avg':
            player_pdf = player_pdf.groupby('Date').mean()

        elif stat_type == 'Raw':
            player_pdf = player_pdf.groupby('Date').sum()

        elif stat_type == 'Sum':
            player_pdf = player_pdf.groupby('Date').max()


        player_pdf = player_pdf.reset_index()[['Date', player]]
        player_pdf.columns = ['date', 'data']
        player_pdf['date_fmt'] = player_pdf['date']
        player_pdf['date'] = player_pdf['date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))

        player_pdf['name'] = player

        plot_objects[player]['source'].data = dict(
            name=player_pdf.name,
            date=player_pdf.date,
            date_fmt=player_pdf.date_fmt,
            data=player_pdf.data,
        )

        if player in selected_players:
            plot_objects[player]['circle'].visible = True
            plot_objects[player]['line'].visible = True
        else:
            plot_objects[player]['circle'].visible = False
            plot_objects[player]['line'].visible = False


# controls = [min_games_slider, data_field_select, data_type_select, stat_select] #, boxoffice, genre, min_year, max_year, oscars, director, cast, x_axis, y_axis]
controls = [min_games_slider, combo_select] #, boxoffice, genre, min_year, max_year, oscars, director, cast, x_axis, y_axis]

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

p.add_tools(wheel_zoom, pan_tool, hover_tool)

p.toolbar.active_scroll = wheel_zoom
p.toolbar.active_drag = pan_tool


inputs = widgetbox(*controls, sizing_mode=sizing_mode)
l = layout([
    [],
    [inputs, p]], sizing_mode=sizing_mode)

update()  # initial load of the data

curdoc().add_root(l)
curdoc().title = "Stats"
