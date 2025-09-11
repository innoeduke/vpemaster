import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'b0535810ca7b08299f43e9e7898d06fd'

# Configure the database connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://shltmc:SHLTMC_leadership_D8@shltmc.mysql.pythonanywhere-services.com/shltmc$Education'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle' : 280}

db = SQLAlchemy(app)

# Import models and routes to ensure they are registered with the app
from vpemaster import models, routes
