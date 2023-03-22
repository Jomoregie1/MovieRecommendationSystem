import mysql.connector
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView


# login manager instance created
login_manager = LoginManager()

# app config --------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'

# Database setup -----------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/movierecommendation'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
Migrate(app, db)

# initializes the flask-login extension and associates it with my application
login_manager.init_app(app)

# sets the view that users will be redirected to when they attempt to access a protected page and are not authenticated.
login_manager.login_view = 'core.login'

# Admin setup ------------------------------
# from System.models import Reading
app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'
admin = Admin(app, template_mode='bootstrap3')
# admin.add_view(ModelView(Reading, db.session))

# adding blueprints -----------------------------------
from System.Core.views import core
from System.error_pages.handlers import error_pages

app.register_blueprint(core)
app.register_blueprint(error_pages)
from System.Users.views import user
app.register_blueprint(user)
from System.Chatbot.views import bot
app.register_blueprint(bot)

# Connect to the database
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)
cursor = mydb.cursor()
mydb.commit()
cursor.close()
mydb.close()
