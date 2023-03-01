from flask import Blueprint, render_template, redirect, request, url_for, flash
from System import db
from System.models import User
from System.Users.forms import RegistrationForm
from flask_login import current_user

user = Blueprint('user', __name__)


@user.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm()

    if form.validate_on_submit():
        user_email = User.query.filter_by(email=form.email.data).first()
        if user_email:
            flash('Email already exists.')
            return redirect(url_for('user.signup'))

        user_profile = User(first_name=form.first_name.data,
                            last_name=form.last_name.data,
                            age=form.age.data,
                            email=form.email.data,
                            password=form.password.data,
                            gender=form.gender.data)

        db.session.add(user_profile)
        db.session.commit()
        flash(f'Thanks {form.first_name.data}  {form.last_name.data}, for registering')
        return redirect(url_for('core.login'))
    else:
        print(form.errors)

    return render_template('register.html', form=form)
