import importlib
import datetime as dt
import os

from esida import app, params, db
from flask import render_template, make_response, abort, request, redirect, url_for, send_from_directory
import markdown
from slugify import slugify

from dbconf import get_engine
from esida.models import Region, District, Signal

import pandas as pd

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'images/favicon.ico',mimetype='image/vnd.microsoft.icon')

@app.route("/")
def index():
    districts = District.query.all()
    return render_template('table.html', shapes=districts)

@app.route("/map")
def map():

    engine = get_engine()

    shapes=[]
    regions=[]
    meteostat=[]
    tza_hfr=[]
    tza_hfr_categories=[]
    with engine.connect() as con:
        rs = con.execute('SELECT id, name, ST_AsGeoJSON(geometry) AS geojson FROM district')
        for row in rs:
            shapes.append(dict(row))

        rs = con.execute('SELECT id, name, ST_AsGeoJSON(geometry) AS geojson FROM region')
        for row in rs:
            regions.append(dict(row))

        rs = con.execute('SELECT id, meteostat_id, name, ST_AsGeoJSON(geometry) AS geojson, (SELECT COUNT(*) FROM meteostat_data WHERE meteostat_station_id = meteostat_stations.id) as count FROM meteostat_stations')
        for row in rs:
            meteostat.append(dict(row))

        rs = con.execute('SELECT t."ID", t."Facility Name", t."Facility Type", t."Latitude", t."Longitude" FROM tza_hfr_healthfacilities t')
        for row in rs:
            tza_hfr.append(dict(row))

        rs = con.execute('SELECT t."Facility Type", COUNT(*) as count FROM tza_hfr_healthfacilities t WHERE t."Facility Type" IS NOT NULL GROUP BY t."Facility Type" ORDER BY count DESC;')
        for row in rs:
            tza_hfr_categories.append(dict(row))



    return render_template('map.html', shapes=shapes, meteostat=meteostat, regions=regions, tza_hfr=tza_hfr, tza_hfr_categories=tza_hfr_categories)


@app.route("/shape/<int:shape_id>")
def shape(shape_id):
    shape = District.query.get(shape_id)
    return render_template('shape.html', shape=shape, params=params, data=_get_parameters_for_district(shape_id))

def _get_parameters_for_district(district_id) -> pd.DataFrame:
    dfs = []

    for p in params:
        pm = importlib.import_module('parameters.{}'.format(p))
        dfs.append(pm.download(int(district_id), get_engine()))

    df = dfs[0]
    for i in range(1, len(dfs)):
        df = df.merge(dfs[i], how='outer', on='year')

    df = df.sort_values(by=['year']).reset_index()

    return df


@app.route('/shape/<int:shape_id>/parameters')
def download_csv(shape_id):
    engine = get_engine()

    shape=None
    with engine.connect() as con:
        # well this not good style...
        rs = con.execute('SELECT id, name FROM district WHERE id={}'.format(int(shape_id)))
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
    pars = []
    for p in params:
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

    pm = importlib.import_module(f'parameters.{parameter_name}')
    docblock = pm.__doc__ or "*please add docstring to module*"

    # check meta data directory
    docfile = f"input/meta_data/{parameter_name}.md"
    if os.path.isfile(docfile):
        with open(docfile) as f:
            docblock = f.read()

    docmd = markdown.markdown(docblock, extensions=['tables'])
    docmd = docmd.replace('<table>', '<table class="table table-sm table-meta_data">')

    parameter = {
        'name': pm.__name__.split('.')[1],
        'description': pm.__doc__,
        'description_html': docmd,
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
