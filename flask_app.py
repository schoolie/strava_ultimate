
from flask import Flask, redirect, request, render_template

from bokeh.client import pull_session
from bokeh.embed import server_session
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
        (False, 'Fall 2018', '2018-09-22', '2018-12-21'),
        (False, 'Winter 2019', '2018-12-21', '2019-03-20'),
        (False, 'Spring 2019', '2019-03-20', '2019-06-21'),
    ]

    for write, name, start, end in seasons:

        if end is not None:
            year, month, day = [int(c) for c in end.split('-')]
            end_date = datetime(year=year, month=month, day=day)

            # year, month, day = [int(c) for c in end.split('-')]
            # end_date = datetime(year=year, month=month, day=day)
        else:
            end_date = datetime.today() ## next check is always True for All Time stats

        if end_date > datetime.today() - timedelta(days=2):
            print(name)
            games = handler.summary_stats(
                write_to_google=write,
                csv_name='{}.csv'.format(name),
                start_date=start,
                end_date=end
            )

    return 'summaries calculated'

# @app.route('/', methods=['GET'])
# def bkapp_page():
#     session = pull_session(url="http://localhost:5006/plot_app")
#     script = server_session(None, session.id, url='http://localhost:5006/plot_app')
#     return render_template("index.html", bokeh_script=script, template="Flask")

@app.route('/', methods=['GET'])
def bkapp_page():

    # pull a new session from a running Bokeh server
    with pull_session(url="http://localhost:5006/plot_app") as session:

        # session = pull_session(url="http://localhost:5006/plot_app")
        # update or customize that session
        # session.document.roots[0].children[1].title.text = "Special Sliders For A Specific User!"

        # generate a script to load the customized session
        script = server_session(session_id=session.id, url='http://localhost:5006/plot_app')

        # use the script in the rendered page
        return render_template("index3.html", plot_script=script, template="Flask")
