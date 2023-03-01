from flask import Blueprint, render_template

error_pages = Blueprint('error_pages', __name__)


@error_pages.app_errorhandler(409)
def error_409():
    return render_template('error_pages/409.html'), 409
