from flask import render_template, Blueprint, url_for, flash, redirect
from flask_login import login_user, logout_user
from System.Chatbot.logicadapter import UserConversationLogicAdapter
from System.Chatbot.views import chatbot
from System.models import User, Admin
from System.Core.forms import LoginForm
from flask_login import current_user
from System.decorators import non_admin_required

core = Blueprint('core', __name__)


@core.route('/')
@non_admin_required
def index():
    # checks if the user is logged in, if not returns them to the login page.
    if not current_user.is_authenticated:
        flash('Please login', 'login_error')
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
                for adapter in chatbot.logic_adapters:
                    if isinstance(adapter, UserConversationLogicAdapter):
                        adapter.reset_first_interaction()
                        break
                return redirect(url_for('core.index'))
            else:
                flash('Sorry, we did not recognise either your username or password', 'login_error')
        else:
            if admin.check_admin(password=form.password.data):
                login_user(admin)
                return redirect(url_for('pending_movies.index'))
            else:
                flash('Sorry, we did not recognise either your username or password ', 'login_error')
    return render_template('login.html', form=form)


@core.route('/logout')
def logout():
    from System.Chatbot.views import reset_adapters
    # Reset the state for all the previous adapters before logging out the user
    reset_adapters(chatbot)

    logout_user()
    return redirect(url_for("core.login"))
