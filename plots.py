import pandas as pd

from bokeh.plotting import figure
from bokeh.layouts import layout, widgetbox
from bokeh.models import ColumnDataSource, Div
from bokeh.models.widgets import Slider, Select, TextInput
from bokeh.io import curdoc

df = pd.read_csv('plot_data.csv', index_col=[0,1,2,3,4])

df = df.unstack(['data_field', 'data_type', 'stat']).sort_index(axis=1)

df.head()
df.Brian.dropna(axis=0)

min_games_played = Slider(title="Min Games Played", start=0, end=500, value=0, step=5)
stat = Select(title="Genre", value="All",
               options=open(join(dirname(__file__), 'genres.txt')).read().split())
