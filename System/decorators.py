from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def non_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            flash("You don't have permission to access this page.", 'warning')
            return redirect(url_for('pending_movies.index'))
        return f(*args, **kwargs)

    return decorated_function
