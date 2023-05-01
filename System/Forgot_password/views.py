from flask import render_template, url_for, flash, redirect, Blueprint, current_app
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from werkzeug.security import generate_password_hash
from .forms import ForgotPasswordForm, ResetPasswordForm
from System.models import User
from System.database import connect_db

forgotPassword = Blueprint('forgot_password', __name__)
restPassword = Blueprint('resetPassword', __name__)
mydb = connect_db()


# Generate a secure token
def generate_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=1800):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt=current_app.config['SECURITY_PASSWORD_SALT'], max_age=expiration)
    except:
        return False
    return email


# Send the email with the reset link
def send_reset_email(user, token):
    msg = Message("Password Reset Request",
                  sender=("Movie recommendation system", "josephomoregie1@gmail.com"),
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('resetPassword.reset_password', token=token, _external=True)}

If you did not request a password reset, please ignore this email.
'''
    mail = current_app.extensions['mail']
    mail.send(msg)


@forgotPassword.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        print("Form validated")  # Debugging print statement
        email = form.email.data
        print(f"Entered email: {email}")
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"User found: {user}")  # Debugging print statement
            token = generate_token(user.email)
            send_reset_email(user, token)
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('core.login'))
        else:
            flash('No account found with that email address.', 'warning')
            print("User not found")  # Debugging print statement
    else:
        print("Form not validated")  # Debugging print statement

    return render_template('forgot_password.html', form=form)


@restPassword.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = confirm_token(token)
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password.forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        if user:
            hashed_password = generate_password_hash(form.password.data)
            cursor = mydb.cursor()
            update_query = "UPDATE users SET password='{}' WHERE email='{}'".format(hashed_password, email)
            cursor.execute(update_query)
            mydb.commit()
            cursor.close()

            flash('Your password has been updated!', 'success')
            return redirect(url_for('core.login'))
        else:
            flash('An error occurred. Please try again later.', 'danger')
            return redirect(url_for('forgot_password.forgot_password'))

    return render_template('reset_password.html', form=form)
