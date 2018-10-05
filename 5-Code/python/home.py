# -*- coding: utf-8 -*-
from __future__ import division
#from flask import Flask, make_response, render_template, request, url_for, jsonify;
from flask import Flask, make_response, request, jsonify;
from flask_sqlalchemy import SQLAlchemy
from backports import csv;
import re;
import pickle;
from googletrans import Translator;
import io;
import jwt;
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from nltk.stem.isri import ISRIStemmer
from stemming.porter2 import stem
from functools import wraps;
import requests;
# encoding=utf8 
import sys 
reload(sys) 
sys.setdefaultencoding('utf8')
#import datetime;
#import json;
#import urllib2;
#from lxml import html;
#import string;
#import time;
#import random;
#import base64;


# Initialize the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisissecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
db = SQLAlchemy(app)
app.config['JSON_AS_ASCII'] = False
          
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(80))

# In[1]:    
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message':'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return jsonify({'message':'Token is missing!'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/')
def home():
    return  "This is from Flask!!!"
    
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data['username'] or not data['password']:
        return make_response('Could not verify1', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})

    user = User.query.filter_by(name=data['username']).first()

    if not user:
        return make_response('Could not verify2', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})

    if check_password_hash(user.password, data['password']):
        token = jwt.encode({'public_id' : user.public_id}, app.config['SECRET_KEY'])

        return jsonify({'token' : token.decode('UTF-8')})

    return make_response('Could not verify3', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})


@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    
    new_user = User(public_id=str(uuid.uuid4()), name=data['name'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message' : 'New user created!'})

# In[2]:
@app.route('/analyze', methods=['POST'])
@token_required
def utubeSent(current_user):
	# coding: utf-8
    uplimit = 0.3
    downlimit = 0.1
    
	#Add Arabic Lexicon words
    pos_words = []
    neg_words = []
    out = ''
    	
    with io.open('/var/www/SentimentAnalysis/SentimentAnalysisApp/NileULex2.csv', 'r', encoding='utf-8') as csvfile:
    #with io.open('NileULex2.csv', 'r', encoding='utf-8') as csvfile:
    	lexicon = csv.reader(csvfile)
    	for row in lexicon:
    		clas = row[1]
    		row = row[0].split()
    		if clas == '1':
    			for r in row:
    				pos_words.extend([r.strip()])
    		else:
    			for r in row:
    				neg_words.extend([r.strip()])
    	
    	#Add English Lexicon words
    with io.open('/var/www/SentimentAnalysis/SentimentAnalysisApp/Hu and Liu Lexicon.csv',  'r', encoding='latin-1') as csvfile:
    #with io.open('Hu and Liu Lexicon.csv',  'r', encoding='latin-1') as csvfile:
    	lexicon = csv.reader(csvfile)
    	for row in lexicon:
    		clas = row[1]
    		row = row[0].split()
    		if clas == '1':
    			for r in row:
    				pos_words.extend([r.strip()])
    		else:
    			for r in row:
    				neg_words.extend([r.strip()])
    	
    	#read negation words
    negation_words = []
    with io.open('/var/www/SentimentAnalysis/SentimentAnalysisApp/negation_words.txt', 'r', encoding='utf-8') as f:
    #with io.open('negation_words.txt', 'r', encoding='utf-8') as f:
    	negation_words = f.read().splitlines() 
    
    	
        #Read Word features from built model
    with open ('/var/www/SentimentAnalysis/SentimentAnalysisApp/english_features', 'rb') as fp:
    #with open ('english_features', 'rb') as fp:
         word_features_en = pickle.load(fp)
        
    with open ('/var/www/SentimentAnalysis/SentimentAnalysisApp/arabic_features', 'rb') as fp:
    #with open ('arabic_features', 'rb') as fp:
         word_features_ar = pickle.load(fp)
        
    	
    	#read stop words
    stop_words = []
    with io.open('/var/www/SentimentAnalysis/SentimentAnalysisApp/stop_words.txt', 'r', encoding='utf-8') as f:
    #with io.open('stop_words.txt', 'r', encoding='utf-8') as f:
        stop_words = f.read().splitlines() 
        
    word_features_ar2 = []
    word_features_en2 = []
    word_features_en_dict = {}
    word_features_ar_dict = {}
    counter = 0
    for w in word_features_ar:
        if not w in stop_words:
            word_features_ar2.append(w)
            word_features_ar_dict[w] = counter
            counter += 1
                
    counter = 0
    for w in word_features_en:
        if not w in stop_words:
            word_features_en2.append(w)
            word_features_en_dict[w] = counter
            counter += 1
    	
    	#Call DNN Classifier Model
    with open('/var/www/SentimentAnalysis/SentimentAnalysisApp/dnn_classifier_english.pkl', 'rb') as fid:
    #with open('dnn_classifier_english.pkl', 'rb') as fid:
        clf_en = pickle.load(fid)
    with open('/var/www/SentimentAnalysis/SentimentAnalysisApp/dnn_classifier_arabic.pkl', 'rb') as fid:
    #with open('dnn_classifier_arabic.pkl', 'rb') as fid:
        clf_ar = pickle.load(fid)
    	
    def get_features(comment, lan):
        words = list(comment)
        if lan == 'ar':
            st = ISRIStemmer()
            features = [0] * len(word_features_ar2)
            for w in words:
                w = st.stem(w)
                if w in word_features_ar_dict:
                    features[word_features_ar_dict[w]] = 1
        else:
            features = [0] * len(word_features_en2)
            for w in words:
                w = stem(w)
                if w in word_features_en_dict:
                    features[word_features_en_dict[w]] = 1
        return features
    	
    	#classify a comment
    def comm_classifier(comm, clf, src_features, lan):
        comm = comm.lower()
        sum_words = 1e-9
        cn_value = 0
        neg = 1
        counter = 0
        comm = comm.split()
            
        for w in comm:
            counter += 1
            if w in stop_words: #pass the stop words
                continue
            elif w in negation_words:
                neg *= -1
                counter = 0
                continue
    			
            if counter > 2:
                counter = 0
                neg = 1
    			
            pos = pos_words.count(w)
            negi = neg_words.count(w)
                
            if pos > 0 or negi > 0:
                sum_words += 1
    			
            if pos > negi:
                cn_value += (neg * (pos/(pos+negi)))
            elif negi > pos:
                cn_value += (neg * -(negi/(pos+negi)))
    		
            val = cn_value/sum_words
    		
            while 1:
                if val > uplimit:
                    val = 1
                    break
                elif val < -uplimit:
                    val = -1
                    break
                elif val > -downlimit and val < downlimit:
                    val = 0
                    break
                else:
                    ft = get_features(comm, lan)
                    import numpy as np                
                    ft = np.array(ft).reshape((1, len(ft)))
                    #return(ft.shape)
                    outt = clf.predict(ft)
                    val = int(outt[0])
        return val
    	# In[11]:
    #comms = ['elfilm w7sh gdn w tamsel zbala wana 3'ltan eny dy3t w2ty feh', 'الراجل ده بيقول كلام زي الفل', 'This man is saying very beautiful words']
    #comms = request.json['comments']
    comms = request.get_json(force=True)
    tot_pos = 0
    tot_neg = 0
    tot_neu = 0
    emoji_pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map symbols
                           u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           "]+", flags=re.UNICODE)
    #out += '<h3>Hello World</h3><br><br>'
    out2 = []
    counter = 0
    for comm in comms:
        #comm = comm.decode('utf-8').encode('utf-8')
        comm = emoji_pattern.sub(r'', comm)
        translator = Translator()
        try:
            lan = translator.detect(comm).lang
        except ValueError:
            continue
    		
        if lan == 'ar': #check if language is Franco and convert it to Arabic using Google Translate
            comm = translator.translate(comm, src='ar', dest='ar').text #Convert Franco to Arabic
            src_features = word_features_ar
            clf = clf_ar
            #Handwritten Rules
            comm = comm.replace('أ', 'ا')
            comm = comm.replace('إ', 'ا')
            comm = comm.replace('ى', 'ي')
            comm = comm.replace('ة', 'ه')
        elif lan == 'en':
            src_features = word_features_en
            clf = clf_en
            comm = comm.lower()
        else:
        	 continue
        out += 'comment text: ' + comm + '<br>'
        clas = comm_classifier(comm, clf, src_features, lan) #classify the comment
        if clas == 1:
            out += 'Classified as: <b>positive opinion</b><br><br>'
            tot_pos += 1
            #commClas[counter] = 1
        elif clas == 0:
            out += 'Classified as: <b>neutral opinion</b><br><br>'
            tot_neu += 1
        elif clas == -1:
            out += 'Classified as: <b>negative opinion</b><br><br>'
            tot_neg += 1
            #commClas[counter] = -1
        counter += 1
        out2.append({'Comment':comm, 'Class': clas})
    #return 'YES'
    return (jsonify({'comments':out2}))





if __name__ == "__main__":
    app.run()
    #app.run('localhost', 8080, debug=True)