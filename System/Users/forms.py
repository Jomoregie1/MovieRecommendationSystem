from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, StringField, IntegerField, SelectField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError
from System.models import User


class RegistrationForm(FlaskForm):

    @staticmethod
    def check_email(field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('This email has already been used, please try again with another email.')

    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Surname', validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email(), check_email])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('pass_confirm', message='Passwords must '
                                                                                                     'match!')])
    pass_confirm = PasswordField('Confirm Password', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('', 'Select Gender'), ('M', 'Male'), ('F', 'Female')])
    submit = SubmitField('Register')
