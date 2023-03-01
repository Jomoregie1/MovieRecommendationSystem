from flask import render_template, request, Blueprint, url_for, flash, redirect
from flask_login import login_user, logout_user
from System import db
from System.models import User, Admin
from System.Core.forms import LoginForm
from flask_login import current_user

core = Blueprint('core', __name__)


@core.route('/')
def index():
    # checks if the user is logged in, if not returns them to the login page.
    if not current_user.is_authenticated:
        flash('Please login')
        return redirect(url_for('core.login'))

    return render_template('index.html')


@core.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        admin = Admin.query.filter_by(email=email).first()
        if admin is None:
            user = User.query.filter_by(email=email).first()
            if user is not None and user.check_user(password=form.password.data):
                login_user(user)
                flash('Successfully logged in!')
                return redirect(url_for('core.index'))
            else:
                flash('Sorry, we did not recognise either your username or password ')
        else:
            if admin.check_admin(password=form.password.data):
                login_user(admin)
                flash('Successfully logged in!')
                return redirect(url_for('admin.index'))
            else:
                flash('Sorry, we did not recognise either your username or password ')
    return render_template('login.html', form=form)


@core.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out!')
    return redirect(url_for("core.login"))
