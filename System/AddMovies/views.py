import pandas as pd
from flask import render_template, redirect, url_for, Blueprint
from flask_login import current_user, login_required
from .forms import AddMovieForm
from System.database import connect_db
from System.decorators import non_admin_required

mydb = connect_db()
addMovie = Blueprint('addMovie', __name__)


def genre_ids():
    try:
        query = """select  name, genre_id from genres;"""
        genres_df = pd.read_sql_query(query, con=mydb)
        genres = list(genres_df[['genre_id', 'name']].itertuples(index=False, name=None))
        filtered_genres = [(genre_id, name) for genre_id, name in genres if name != '(no genres listed)']
        return filtered_genres
    except Exception as e:
        print("Error fetching genres", e)
        return []


def add_movie_to_pending(title, year, description, genre_id, user_id, initial_rating):
    cursor = mydb.cursor()
    try:
        query = """INSERT INTO pending_movies (title, year, description, genre_id, userId, initial_rating, is_approved)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(query, (title, year, description, genre_id, user_id, initial_rating, False))
        mydb.commit()

    except Exception as e:
        print(f"Error adding movie to the database: {e}")
    finally:
        if mydb.is_connected():
            cursor.close()


@addMovie.route('/add_movie', methods=['GET', 'POST'])
@non_admin_required
@login_required
def add_movie():
    form = AddMovieForm()
    genres = genre_ids()
    form.genre.choices = genres
    if form.validate_on_submit():
        title = form.title.data
        year = form.year.data
        description = form.description.data
        genre_id = form.genre.data
        user_id = current_user.get_id()
        initial_rating = form.initial_rating.data
        add_movie_to_pending(title, year, description, genre_id, user_id, initial_rating)
        return redirect(url_for('addMovie.movie_submitted'))
    return render_template('add_movie.html', form=form)


@addMovie.route('/movie_submitted')
@non_admin_required
@login_required
def movie_submitted():
    user_id = current_user.get_id()
    cursor = mydb.cursor()
    try:
        query = """SELECT pm.id, pm.title, pm.year, pm.description, g.name, pm.status, pm.initial_rating
                   FROM pending_movies pm
                   JOIN genres g ON pm.genre_id = g.genre_id
                   WHERE pm.userId = %s"""
        cursor.execute(query, (user_id,))
        submitted_movies = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching submitted movies: {e}")
        submitted_movies = []
    finally:
        if mydb.is_connected():
            cursor.close()

    return render_template('movie_submitted.html', movies=submitted_movies)
