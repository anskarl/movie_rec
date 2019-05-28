# -*- coding: utf-8 -*-

from app import app
from flask import jsonify


@app.route('/')
def hello():
    return jsonify(message="Welcome to MovieRec!")
