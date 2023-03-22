from System import db, login_manager, app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

with app.app_context():
    db.Model.metadata.reflect(db.engine)


    @login_manager.user_loader
    def load_user(email):
        return User.query.get(email)


    class User(db.Model, UserMixin):
        __table__ = db.Model.metadata.tables['users']
        __table_args__ = {
            'autoload': True,
            'autoload_with': db.engine,
            'extend_existing': True,
            'column_prefix': '',
        }

        def __init__(self, first_name, last_name, age, gender, email, password):
            self.email = email
            self.first_name = first_name
            self.last_name = last_name
            self.age = age
            self.gender = gender
            self.password = generate_password_hash(password)

        def check_user(self, password):
            return check_password_hash(self.password, password)

        def get_id(self):
            return self.userId

        def __str__(self):
            return f'Id of user: {self.userId}'


    class Admin(db.Model, UserMixin):
        __table__ = db.Model.metadata.tables['admin']

        def __init__(self, email, password):
            self.email = email
            self.password_hash = generate_password_hash(password)

        def __str__(self):
            return f'Admin {self.email}.'

        def get_id(self):
            return self.email

        def check_admin(self, password):
            """Check if provided password matches admin's password."""


    class Statement(db.Model):
        __tablename__ = 'statement'  # Make sure the table name matches your existing table name
        id = db.Column(db.Integer, primary_key=True)
        text = db.Column(db.String(500))
        search_text = db.Column(db.String(500))
        conversation = db.Column(db.String(100))
        created_at = db.Column(db.DateTime)
        in_response_to = db.Column(db.String(500))
        search_in_response_to = db.Column(db.String(500))
        persona = db.Column(db.String(100))