import importlib

from esida import app, params
from flask import render_template, make_response, abort, request, redirect, url_for
import markdown
from slugify import slugify

from dbconf import get_engine
from esida.models import Signal

@app.route("/test")
def test():
    return str(params)

@app.route("/")
def index():
    engine = get_engine()

    shapes=[]
    meteostat=[]
    with engine.connect() as con:
        rs = con.execute('SELECT gid, region_nam as region, newdist20 AS name, ST_AsGeoJSON(geom) AS geojson, ST_AsText(geom) as wkt FROM districts')
        for row in rs:
            shapes.append(dict(row))

    return render_template('table.html', shapes=shapes)

@app.route("/map")
def map():

    engine = get_engine()

    shapes=[]
    regions=[]
    meteostat=[]
    with engine.connect() as con:
        rs = con.execute('SELECT gid, newdist20 AS name, ST_AsGeoJSON(geom) AS geojson FROM districts')
        for row in rs:
            shapes.append(dict(row))

        rs = con.execute('SELECT gid, region_nam AS name, ST_AsGeoJSON(geom) AS geojson FROM regions')
        for row in rs:
            regions.append(dict(row))

        rs = con.execute('SELECT id, meteostat_id, name, ST_AsGeoJSON(geometry) AS geojson, (SELECT COUNT(*) FROM meteostat_data WHERE meteostat_station_id = meteostat_stations.id) as count FROM meteostat_stations')
        for row in rs:
            meteostat.append(dict(row))

    return render_template('map.html', shapes=shapes, meteostat=meteostat, regions=regions)


@app.route("/shape/<int:shape_id>")
def shape(shape_id):
    engine = get_engine()

    shape=None
    with engine.connect() as con:
        # well this not good style...
        rs = con.execute('SELECT gid, newdist20 AS name, ST_AsGeoJSON(geom) AS geojson,  ST_AsText(geom) as wkt FROM districts WHERE gid={}'.format(int(shape_id)))
        shape = rs.fetchone()


    return render_template('shape.html', shape=shape)

@app.route('/shape/<int:shape_id>/parameters')
def download_csv(shape_id):
    engine = get_engine()

    shape=None
    with engine.connect() as con:
        # well this not good style...
        rs = con.execute('SELECT gid, newdist20 AS name, ST_AsGeoJSON(geom) AS geojson FROM districts WHERE gid={}'.format(int(shape_id)))
        shape = rs.fetchone()

    dfs = []

    for p in params:
        pm = importlib.import_module('parameters.{}'.format(p))
        dfs.append(pm.download(int(shape_id), engine))
        # dfs.append(pd.read_sql_query('SELECT year, value as {} FROM {} WHERE district_id={}'.format(p, p, int(shape_id)), con=engine))

    df = dfs[0]
    for i in range(1, len(dfs)):
        df = df.merge(dfs[i], how='outer', on='year')

    df = df.sort_values(by=['year'])

    filename="esida_{}.csv".format(slugify(shape['name']))

    resp = make_response(df.to_csv(index=False))
    resp.headers["Content-Disposition"] = "attachment; filename={}".format(filename)
    resp.headers["Content-Type"] = "text/csv"
    return resp


@app.route('/parameter')
def parameters():
    print(params)
    pars = []
    for p in params:
        print(p)
        pm = importlib.import_module('parameters.{}'.format(p))
        pars.append({
            'name': pm.__name__.split('.')[1],
            'description': pm.__doc__,
        })

    return render_template('parameters.html', parameters=pars)

@app.route("/parameter/<string:parameter_name>")
def parameter(parameter_name):

    if parameter_name not in params:
        abort(500)

    pm = importlib.import_module('parameters.{}'.format(parameter_name))
    parameter = {
        'name': pm.__name__.split('.')[1],
        'description': pm.__doc__,
        'description_html': markdown.markdown(pm.__doc__ or "*please add docstring to module*", extensions=['tables']),
    }

    return render_template('parameter.html', parameter=parameter)

@app.route('/signals')
def signals():
    signals = Signal.query.all()
    return render_template('signal/index.html', signals=signals)

@app.route('/signal', methods = ['POST', 'GET'])
def signal():

    if request.method == 'POST':

        signal = Signal(age=int(request.form['age']),
            report_date=dt.datetime.strptime(request.form['report_date'], '%Y-%m-%d').date(),
            sex=request.form['sex'],
            geometry='POINT({} {})'.format(request.form['lng'], request.form['lat'])
        )

        db.session.add(signal)
        db.session.commit()

        return redirect(url_for('signals'))

    return render_template('signal/create.html')



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)


