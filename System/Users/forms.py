from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, StringField, RadioField, IntegerField, DateTimeField
from wtforms.validators import DataRequired, EqualTo, Email
from wtforms import ValidationError
from System.error_pages import handlers
from datetime import datetime

from flask_login import current_user
from System.models import User


class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Surname', validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('pass_confirm', message='Passwords must '
                                                                                                     'match!')])
    pass_confirm = PasswordField('Confirm Password', validators=[DataRequired()])
    gender = RadioField('Gender', choices=[('M', 'Male'), ('F', 'Female')])
    submit = SubmitField('Register')

    # TODO this may cause a bug and is used to throw an error if the user has entered an email that exist already.
    def check_email(self,field):
        if User.query.filter_by(email=field.data).first():
            return handlers.error_409()


