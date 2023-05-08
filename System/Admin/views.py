from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from System.database import connect_db
from flask_admin import AdminIndexView, expose


mydb = connect_db()


def get_pending_movies():
    cursor = mydb.cursor()
    try:
        query = """SELECT pm.id, pm.title, pm.year, pm.description, g.name, u.email, pm.status
                   FROM pending_movies pm
                   JOIN genres g ON pm.genre_id = g.genre_id
                   JOIN users u ON pm.userId = u.userId
                   WHERE pm.is_approved = FALSE"""
        cursor.execute(query)
        pending_movies = cursor.fetchall()
        print(pending_movies)
    except Exception as e:
        print(f"Error fetching pending movies: {e}")
        pending_movies = []
    finally:
        if mydb.is_connected():
            cursor.close()

    return pending_movies


def insert_approved_movie(movie_id):
    cursor = mydb.cursor()
    try:
        # Insert movie data into movies table
        query = """INSERT INTO movies (title, year)
                   SELECT title, year
                   FROM pending_movies
                   WHERE id = %s"""
        cursor.execute(query, (movie_id,))
        mydb.commit()

        # Get the generated movieId
        new_movie_id = cursor.lastrowid

        # Insert description data into descriptions table
        query = """INSERT INTO movie_description (movieId, description)
                   SELECT %s, description
                   FROM pending_movies
                   WHERE id = %s"""
        cursor.execute(query, (new_movie_id, movie_id))
        mydb.commit()

        # Insert movie and genre mapping into movie_genre table
        query = """INSERT INTO movie_genre (movieId, genre_id)
                   SELECT %s, genre_id
                   FROM pending_movies
                   WHERE id = %s"""
        cursor.execute(query, (new_movie_id, movie_id))
        mydb.commit()

        # Insert initial rating data into ratings table
        query = """INSERT INTO ratings (movieId, userId, ratings)
                   SELECT %s, user_id, initial_rating
                   FROM pending_movies
                   WHERE id = %s"""
        cursor.execute(query, (new_movie_id, movie_id))
        mydb.commit()

    except Exception as e:
        print(f"Error inserting approved movie: {e}")
    finally:
        if mydb.is_connected():
            cursor.close()


def approve_movie(movie_id):
    cursor = mydb.cursor()
    try:
        # Insert the approved movie into the movies table
        insert_approved_movie(movie_id)

        # Update the status of the approved movie in the pending_movies table
        query = """UPDATE pending_movies SET status = 'Approved' WHERE id = %s"""
        cursor.execute(query, (movie_id,))
        mydb.commit()
    except Exception as e:
        print(f"Error approving movie: {e}")
    finally:
        if mydb.is_connected():
            cursor.close()


def decline_movie(movie_id):
    cursor = mydb.cursor()
    try:
        query = """UPDATE pending_movies SET status = 'Rejected' WHERE id = %s"""
        cursor.execute(query, (movie_id,))
        mydb.commit()
    except Exception as e:
        print(f"Error declining movie: {e}")
    finally:
        if mydb.is_connected():
            cursor.close()


class PendingMoviesView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_admin:
            return self.render('index.html')

        pending_movies = get_pending_movies()
        print(f"pending_movies")
        return self.render('admin/admin_pending_movies.html', movies=pending_movies)

    @expose('/approve/<int:movie_id>', methods=['GET'])
    def approve_movie(self, movie_id):
        if not current_user.is_admin:
            flash("You don't have permission to access this page.", 'warning')
            return redirect(url_for('core.index'))

        approve_movie(movie_id)
        flash("Movie approved successfully!", 'success')
        return redirect(url_for('pending_movies.index'))

    @expose('/decline/<int:movie_id>')
    def admin_decline_movie(self, movie_id):
        if not current_user.is_admin:
            flash("You don't have permission to access this page.", 'warning')
            return redirect(url_for('core.index'))

        decline_movie(movie_id)
        flash("Movie declined successfully!", 'success')
        return redirect(url_for('pending_movies.index'))
