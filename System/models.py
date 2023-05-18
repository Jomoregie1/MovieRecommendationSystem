from System import db, login_manager, app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.mysql import JSON
import json

with app.app_context():
    db.Model.metadata.reflect(db.engine)


    @login_manager.user_loader
    def load_user(email):
        user = User.query.get(email)
        if user is None:
            user = Admin.query.get(email)
            if user is not None:
                user.is_admin = True
        else:
            user.is_admin = False
        return user


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
            self._is_admin = False

        def check_user(self, password):
            return check_password_hash(self.password, password)

        def get_id(self):
            return self.userId

        @property
        def is_admin(self):
            return getattr(self, '_is_admin', False)

        @is_admin.setter
        def is_admin(self, value):
            self._is_admin = value

        def __str__(self):
            return f'Id of user: {self.userId}'


    class Admin(db.Model, UserMixin):
        __tablename__ = 'admin'
        __table_args__ = {'extend_existing': True}

        email = db.Column(db.String(64), primary_key=True)
        password = db.Column(db.String(128))

        def __init__(self, email, password):
            self.email = email
            self.password = generate_password_hash(password)
            self._is_admin = True

        @property
        def is_admin(self):
            return self._is_admin

        @is_admin.setter
        def is_admin(self, value):
            self._is_admin = value

        def __str__(self):
            return f'Admin {self.email}.'

        def get_id(self):
            return self.email

        def check_admin(self, password):
            """Check if provided password matches admin's password."""
            return check_password_hash(self.password, password)


    def create_admin_account(email, password):
        """Create initial admin account with provided email and password."""
        if Admin.query.filter_by(email=email).first():
            return
        admin = Admin(email=email, password=password)
        db.session.add(admin)
        db.session.commit()


    # Creates an admin
    create_admin_account(email='admin@admin.com', password='admin')


    class Statement(db.Model):
        __tablename__ = 'statement'
        id = db.Column(db.Integer, primary_key=True)
        text = db.Column(db.String(500))
        search_text = db.Column(db.String(500))
        conversation = db.Column(db.String(100))
        created_at = db.Column(db.DateTime)
        in_response_to = db.Column(db.String(500))
        search_in_response_to = db.Column(db.String(500))
        persona = db.Column(db.String(100))
        meta = db.Column(JSON)

        @property
        def meta_dict(self):
            if isinstance(self.meta, str):
                return json.loads(self.meta)
            return self.meta or {}

        @meta_dict.setter
        def meta_dict(self, value):
            if isinstance(value, dict):
                self.meta = json.dumps(value)
            else:
                self.meta = value
