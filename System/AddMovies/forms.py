from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError, NumberRange


def validate_year(form, field):
    current_year = datetime.now().year
    if field.data < 1888 or field.data > current_year:
        raise ValidationError('Invalid year. Please enter a valid year.')


class AddMovieForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=255)])
    year = IntegerField('Year', validators=[DataRequired(), validate_year])
    description = TextAreaField('Description', validators=[DataRequired()])
    genre = SelectField('Genre', coerce=int, validators=[DataRequired()])
    initial_rating = IntegerField('Initial Rating', validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField('Submit')
