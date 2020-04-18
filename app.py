from flask import Flask, request, jsonify, Response
from flask_cors import *
from flask_sqlalchemy import SQLAlchemy
from summarize import Summarize
from predictor import predict1
import json
import os
import datetime
from multiprocessing.pool import ThreadPool
from extractTicker import stock_graph
from news_scraper import scraper
from app_helper import pre, valid_time


app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class QueryModel(db.Model):

    id = db.Column(db.Integer, primary_key = True)
    query_ = db.Column(db.String(90), nullable = False, unique = True)
    list_predicted = db.Column(db.String(200), nullable = False)
    news_score = db.Column(db.Float)
    time = db.Column(db.DateTime, default=datetime.datetime.now())


@app.route('/news', methods=['GET'])
def sentiment_analyzer():
    '''
    Returns the change in value in interval of days.
    '''
    query = request.args.get('query', type=str)

    if query is None:
        return Response("{'Message': 'Send query in get query'}", status=404,
                        mimetype='application/json')

    item = QueryModel.query.filter_by(query_=query).first()
    if item is not None:
        if valid_time(item.time):
            return json.dumps({"predict": eval(item.list_predicted)})

    query = query.replace("%20", " ")
    list_predicted = {}
    news_score = predict1(query).final_pred

    pool = ThreadPool(processes=4)
    inter1 = pool.apply_async(pre, (1, news_score))
    inter7 = pool.apply_async(pre, (7, news_score))
    inter15 = pool.apply_async(pre, (15, news_score))
    inter30 = pool.apply_async(pre, (30, news_score))

    list_predicted["1"] = inter1.get()
    list_predicted["7"] = inter7.get()
    list_predicted["15"] = inter15.get()
    list_predicted["30"] = inter30.get()

    if item is None:
        item = QueryModel(query_=query, list_predicted=str(list_predicted),
                          news_score=news_score, time=datetime.datetime.now())
        db.session.add(item)

    item.list_predicted = str(list_predicted)
    item.news_score = news_score
    db.session.commit()

    return json.dumps({"predict": list_predicted})


@app.route('/stock-graph', methods=['GET'])
def graph():

    query = request.args.get('query', type=str)

    if query is None:
        return Response("{'Message': 'Send query in get query'}", status=404,
                        mimetype='application/json')

    query = query.replace("%20", " ")
    try:
        list_predicted = eval(QueryModel.query.filter_by(query_=query).first().list_predicted)

    except Exception as e:
        return Response("{'message': 'invalid query'}", status=404)

    graph_pre = [list_predicted["1"],
                 list_predicted["7"],
                 list_predicted["15"],
                 list_predicted["30"]]

    try:
        return stock_graph(query,
                           graph_pre).graph()
    except Exception as e:
        return Response("{'message': 'ticker not found'}", status=404)



@app.route('/get-summary', methods=["GET"])
def get_summary():

    query = request.args.get('query', type=str)

    if query is None:
        return Response("{'Message': 'Send query in get query'}", status=404,
                        mimetype='application/json')
    query = query.replace("%20", " ")
    news = scraper(query).get_title()
    pointers = 3
    return jsonify(Summarize(news, pointers).generate_summary())


if __name__ == '__main__':
    db.create_all() # pragma: no cover
    app.run(debug=True) # pragma: no cover
