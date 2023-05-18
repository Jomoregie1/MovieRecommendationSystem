import functools
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sklearn.neighbors import NearestNeighbors
import pandas as pd
from sqlalchemy import create_engine, text
from fuzzywuzzy import process
from System.database import connect_db
import spacy
from rake_nltk import Rake
import mysql.connector

mydb = connect_db()
db_connection_string = "mysql+mysqlconnector://root:root@localhost:3306/movierecommendation"
engine = create_engine(db_connection_string)
nlp = spacy.load("en_core_web_lg")


def popular_movies_df():
    """
    Returns a list of popular movies based on the number of ratings and average rating.
    :return: list of tuples, each tuple containing movie ID and title
    """
    try:
        query = """SELECT m.movieId, m.title, COUNT(r.ratings) as num_ratings, AVG(r.ratings) as avg_rating
                   FROM movies as m
                   INNER JOIN ratings as r ON m.movieId = r.movieId
                   GROUP BY m.movieId, m.title 
                   HAVING num_ratings > 30
                   ORDER BY avg_rating DESC, m.movieId ASC;"""
        popular_movies_df = pd.read_sql_query(query, con=mydb)
        return list(zip(popular_movies_df['movieId'], popular_movies_df['title']))
    except Exception as e:
        print("Error fetching popular movies:", e)
        return []


def list_of_genres():
    """
        Fetches a list of distinct genre names from the 'genres' table in the database,
        excluding the '(no genres listed)' value.

        Returns:
            list: A list of strings representing distinct genre names, with the
            exception of '(no genres listed)'. Returns an empty list if there's an error
            while fetching the genres.
    """
    try:
        query = """select distinct name from genres;"""
        genres_df = pd.read_sql_query(query, con=mydb)
        genres = list(genres_df['name'])
        filtered_genres = [genre for genre in genres if genre != '(no genres listed)']
        return filtered_genres
    except Exception as e:
        print("Error fetching genres", e)
        return []


def get_rated_movies(user):
    """
    Returns a list of movies rated by the given user.
    param user: int, user ID
    :return: list of tuples, each tuple containing movie ID and title
    """
    try:
        query = """SELECT r.movieId, m.title
                   FROM ratings as r
                   INNER JOIN movies as m ON r.movieId = m.movieId
                   WHERE userId = %s AND ratings > 0;"""
        rated_movies_df = pd.read_sql_query(query, con=mydb, params=[user])
        return list(rated_movies_df[['movieId', 'title']].itertuples(index=False, name=None))
    except Exception as e:
        print("Error fetching rated movies:", e)
        return []


def get_movie_titles():
    """
    Returns a DataFrame containing movie titles.
    :return: pandas DataFrame, movie titles
    """
    try:
        with engine.connect() as connection:
            query = text("""SELECT title
                       FROM movies;""")
            result = connection.execute(query)
            movie_data = pd.DataFrame(result.fetchall(), columns=['title'])
            return movie_data
    except Exception as e:
        print("Error fetching movie titles:", e)
        return pd.DataFrame()


def count_rated_movies_for_user(user):
    """
    Counts the number of movies rated by the given user.
    param user: int, user ID
    :return: int, number of rated movies
    """
    try:
        query = "SELECT COUNT(*) FROM ratings WHERE userId = %s"
        count_ratings_df = pd.read_sql_query(query, con=mydb, params=[str(user)])
        num_rated_movies = count_ratings_df.iloc[0][0]
        return num_rated_movies
    except Exception as e:
        print("Error counting rated movies for user:", e)
        return 0


def store_rating(user_id, movie_id, rating):
    """
    Stores a rating for a given user and movie in the ratings table.
    :param user_id: int, user ID
    :param movie_id: int, movie ID
    :param rating: float, rating given by the user
    """

    check_query = "SELECT COUNT(*) FROM ratings WHERE userId = %s AND movieId = %s"
    insert_query = "INSERT INTO ratings (userId, movieId, ratings) VALUES (%s, %s, %s)"

    try:
        with mydb.cursor() as cursor:
            cursor.execute(check_query, (user_id, movie_id))
            count = cursor.fetchone()[0]

            if count > 0:
                return False
            else:
                cursor.execute(insert_query, (user_id, movie_id, rating))
                mydb.commit()
                return True

    except mysql.connector.Error as e:
        print(f"The error '{e}' occurred")


def get_movie_data():
    """
    Returns a DataFrame containing movie data including genres, tags, and description.
    :return: pandas DataFrame, movie data
    """
    try:
        with engine.connect() as connection:
            query = text("SELECT m.movieId, m.title, GROUP_CONCAT(DISTINCT g.name SEPARATOR ', ') AS genres, "
                         "GROUP_CONCAT(DISTINCT IFNULL(t.tag, 'None') SEPARATOR ', ') AS tags, COALESCE("
                         "md.description, "
                         "'None') AS "
                         "description FROM movies as m LEFT JOIN movie_genre as mg ON m.movieId = mg.movieId LEFT JOIN "
                         "genres as g ON mg.genre_id = g.genre_id LEFT JOIN tags as t ON m.movieId = t.movieId LEFT "
                         "JOIN "
                         "movie_description as md ON m.movieId = md.movieId GROUP BY m.movieId, m.title, "
                         "md.description;")
            result = connection.execute(query)
            movie_data = pd.DataFrame(result.fetchall(), columns=['movieId', 'title', 'genres', 'tags', 'description'])
            return movie_data
    except Exception as e:
        print("Error occurred while fetching movie data:", e)
        return None


def create_movie_features(movie_data):
    """
    Creates a text feature by combining movie genres, tags, and description.
    :param movie_data: pandas DataFrame, movie data
    :return: pandas DataFrame, movie data with text feature
    """
    movie_data['features'] = movie_data['genres'] + ' ' + movie_data['tags'] + ' ' + movie_data['description']
    return movie_data


def get_unseen_movies(user_seen_movies, all_movies):
    """
    Returns a list of movies that have not been seen by the given user.

    Args:
        user_seen_movies (list, set): A list or set of movies seen by the user.
        all_movies (list): A list of all available movies.

    Returns:
        A list of movies that the user has not seen yet.
    """
    # Convert user_seen_movies to a set if it is not already
    user_seen_movies_set = set(user_seen_movies)

    return [movie for movie in all_movies if movie not in user_seen_movies_set]


def get_similar_users(user, temp_pred_df):
    """
    Finds similar users based on their predicted ratings.
    :param user: int, user ID
    :param temp_pred_df: pandas DataFrame, predicted ratings
    :return: list of ints, similar users
    """
    return find_similar_users(user, temp_pred_df)


def get_unique_movie_list(movie_ratings_sorted, movieId_to_title):
    """
    Returns a list of movie titles and their ratings, sorted by rating.
    param movie_ratings_sorted: pd.Series, movie ratings sorted by rating
    param movieId_to_title: dict, a dictionary mapping movieId to movie title
    :return: list of tuples, movieId and movie titles
    """
    unique_movie_list = []
    for movie_title, rating in movie_ratings_sorted.items():
        movieId = list(movieId_to_title.keys())[list(movieId_to_title.values()).index(movie_title)]
        unique_movie_list.append((movieId, movie_title))

    return unique_movie_list


def fetch_predicted_ratings():
    """
    Returns a DataFrame of predicted ratings.
    :return: pandas DataFrame, predicted ratings
    """
    try:
        with engine.connect() as connection:
            query = text('SELECT userId, movieId, ratings FROM pred_ratings')
            result = connection.execute(query)
            pred_df = pd.DataFrame(result.fetchall(), columns=['userId', 'movieId', 'ratings'])
            return pred_df.pivot(index='userId', columns='movieId', values='ratings')
    except Exception as e:
        print("Error occurred while fetching predicted ratings:", e)
        return None


def extract_keyword(description):
    """
    Extracts keywords from a given text description using the RAKE (Rapid Automatic Keyword Extraction) algorithm.

    Args:
        description (str): Text description from which to extract keywords.

    Returns:
        str: Extracted keyword or an empty string if no keywords are found.
    """
    r = Rake()
    r.extract_keywords_from_text(description)
    extracted_keywords = r.get_ranked_phrases()
    return extracted_keywords[0] if extracted_keywords else ""


def fetch_user_ratings(user_id):
    """Retrieve a Series containing a given user's ratings for all movies.

        Args:
            user_id (int): The user ID.

        Returns:
            A pandas Series containing the user's ratings for all movies.
        """
    try:
        with engine.connect() as connection:
            query = text("SELECT movieId, ratings FROM ratings WHERE userId = :user_id;")
            result = connection.execute(query, {'user_id': user_id})
            user_ratings_df = pd.DataFrame(result.fetchall(), columns=['movieId', 'ratings'])
            user_ratings_series = pd.Series(data=user_ratings_df["ratings"].values,
                                            index=user_ratings_df["movieId"].values)
            return user_ratings_series
    except Exception as e:
        print("Error occurred while fetching user ratings:", e)
        return None


def find_similar_users(user_id, temp_pred_df):
    """Find similar users to a given user based on their ratings' history.

        Args:
            user_id (int): The user ID.
            temp_pred_df (DataFrame): A DataFrame containing predicted ratings for all users.

        Returns:
            A list of user IDs similar to the given user.
        """
    knn = NearestNeighbors(metric='cosine', algorithm='brute')
    knn.fit(temp_pred_df.values)

    user_present = user_id in temp_pred_df.index.tolist()
    user_index = temp_pred_df.index.tolist().index(user_id) if user_present else None

    if not user_present:
        user_ratings = fetch_user_ratings(user_id)
        temp_pred_df.loc[user_id] = temp_pred_df.loc[user_id].combine_first(user_ratings)

    distances, indices = knn.kneighbors(temp_pred_df.values, n_neighbors=4 if user_present else 3)

    if user_present:
        sim_users = indices[user_index].tolist()
        sim_users.remove(user_index)
    else:
        sim_users = indices[-1].tolist()

    return sim_users


def fetch_top_rated_movies(sim_users):
    """Retrieve a list of top-rated movies for a given set of similar users.

    Args:
        sim_users (list): A list of user IDs similar to the given user.

    Returns:
        A list of top-rated movies for the given set of users, sorted by average rating.
    """
    try:
        # Check if sim_users is a list
        if not isinstance(sim_users, list):
            raise ValueError("sim_users must be a list")

        # Check if sim_users list is not empty
        if len(sim_users) == 0:
            raise ValueError("sim_users list must not be empty")

        # Check if all elements in sim_users list are integers
        if not all(isinstance(user, int) for user in sim_users):
            raise ValueError("All elements in sim_users list must be integers")

        similar_users_str = ','.join(str(user) for user in sim_users)
        with engine.connect() as connection:
            query = text(
                "SELECT movieId, AVG(ratings) as avg_rating "
                "FROM ratings WHERE FIND_IN_SET(userId, :similar_users) "
                "GROUP BY movieId "
                "ORDER BY avg_rating DESC"
            )
            result = connection.execute(query, {'similar_users': similar_users_str})
            top_movies = pd.DataFrame(result.fetchall(), columns=['movieId', 'avg_rating'])

            recommended_movies = []
            for movieId, avg_rating in top_movies[['movieId', 'avg_rating']].values:
                query = text("SELECT title FROM movies WHERE movieId = :movie_id")
                result = connection.execute(query, {'movie_id': movieId})
                movie_title = result.fetchone()[0]
                recommended_movies.append((int(movieId), movie_title, round(avg_rating, 1)))

        return [(movie_id, movie_title) for movie_id, movie_title, _ in recommended_movies]

    except Exception as e:
        print(f"Error: {e}")
        return None


def fetch_item_predicted_ratings():
    """Fetches the predicted ratings for movies based on the item, i.e., the movie.

        Returns:
            pandas.DataFrame: The predicted ratings pivot table, indexed by movie title and with columns for each user.
        """
    with engine.connect() as connection:
        query = text('select m.title, p.userId, p.ratings from movies as m inner join pred_ratings as p on m.movieId '
                     '= p.movieId')
        result = connection.execute(query)
        item_pred_df = pd.DataFrame(result.fetchall(), columns=['title', 'userId', 'ratings'])

        # Pivot the DataFrame
        item_pred_pivot = item_pred_df.pivot_table(index='title', columns='userId', values='ratings')

        return item_pred_pivot


@functools.lru_cache(maxsize=None)
def compute_similarity_matrices():
    """
        Computes and caches the movie data and cosine similarity matrices for movie recommendations.

        The results are cached indefinitely or until the cache is manually cleared or the program is terminated.

        Returns:
            movie_data (pd.DataFrame): A DataFrame containing movie data with combined features for each movie.
            cosine_sim (np.ndarray): A square 2D array containing cosine similarity scores for each pair of movies.
        """
    movie_data = get_movie_data()
    movie_data = create_movie_features(movie_data)

    # Calculate the TF-IDF matrix
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(movie_data['features'])

    # Calculate cosine similarities
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

    return movie_data, cosine_sim


def is_sequel(title1, title2):
    """Determines if two movie titles are likely sequels of each other based on their similarity.

        Args:
            title1 (str): The first movie title to compare.
            title2 (str): The second movie title to compare.

        Returns:
            bool: True if the titles are likely sequels, False otherwise.
        """
    title1_clean = re.sub(r'\W+', ' ', title1).lower().strip()
    title2_clean = re.sub(r'\W+', ' ', title2).lower().strip()
    return title1_clean in title2_clean or title2_clean in title1_clean


@functools.lru_cache(maxsize=None)
def fetch_predicted_ratings_cache():
    """
    Fetches predicted ratings from the cache or computes and caches them if not available.
    :return: pd.DataFrame, a DataFrame containing predicted ratings.
    """
    return fetch_predicted_ratings()


@functools.lru_cache(maxsize=None)
def fetch_user_ratings_cache(user_id):
    """
    Fetches user ratings for a given user ID from the cache or computes and caches them if not available.
    param user_id: int, user ID for which to fetch the ratings.
    :return: pd.DataFrame, a DataFrame containing user ratings for the given user ID.
    """
    return fetch_user_ratings(user_id)


def recommend_movies_based_on_user(user_id):
    """
    Recommends movies for a given user based on their ratings and the ratings of similar users.

    Args:
        user_id (int): The ID of the user to recommend movies for.

    Returns:
        list: A list of recommended movie titles.
    """
    pred_df = fetch_predicted_ratings_cache()
    user_ratings = fetch_user_ratings_cache(user_id)

    # Add a new row for the user with all values set to NaN
    pred_df.loc[user_id] = np.nan

    # Update the user's ratings in the pred_df
    for movie_id, rating in user_ratings.items():
        pred_df.loc[user_id, movie_id] = rating

    # Fill NaN values with 0
    pred_df.fillna(0, inplace=True)

    sim_users = find_similar_users(user_id, pred_df)
    top_rated_movies = fetch_top_rated_movies(sim_users)

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = set((movie_id, title) for movie_id, title in get_rated_movies(user_id))

    # Remove the movies that the user has already seen
    recommended_movies = [(movie_id, title) for movie_id, title in top_rated_movies if
                          (movie_id, title) not in seen_movies]

    return recommended_movies


def recommend_movies_based_on_title(title, user):
    """
    Recommends up to three movies similar to the provided title using cosine similarity of movie features.

    Args:
    title (str): The title of the movie to base the recommendations on.
    user (int): The ID of the user for whom the recommendations are being made.

    Returns:
    recommended_movies (list): A list of up to three recommended movie titles.
    """

    movie_data, cosine_sim = compute_similarity_matrices()

    titles = movie_data['title'].tolist()
    movie_ids = movie_data['movieId'].tolist()

    # Find the closest matching title using FuzzyWuzzy
    match = process.extractOne(title, titles)
    if match[1] < 80:
        return "No movie with a similar title found."

    matched_title = match[0]
    index_user_likes = titles.index(matched_title)

    # Get the indices of the most similar movies
    sim_scores = sorted(enumerate(cosine_sim[index_user_likes]), key=lambda x: x[1], reverse=True)[1:]

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movie_ids = set(movie_id for movie_id, _ in get_rated_movies(user))

    recommended_movies = []
    unique_movie_titles = set()  # Initialize an empty set for unique movie titles
    for score in sim_scores:
        if len(recommended_movies) >= 3:
            break
        movie_index = score[0]
        movie_title = titles[movie_index]
        movie_id = movie_ids[movie_index]
        if movie_id not in seen_movie_ids and (
                movie_id, movie_title) not in recommended_movies and movie_title != matched_title and not is_sequel(
            matched_title,
            movie_title) and movie_title not in unique_movie_titles:  # Add a condition to check if the title is not
            # in the set
            unique_movie_titles.add(movie_title)  # Add the movie title to the set
            recommended_movies.append((movie_id, movie_title))

    return recommended_movies


def recommend_movies_based_on_genre(genre, user):
    """
    Recommends movies to the given user based on a specified genre.

    Args:
    - genre (str): The name of the genre to base the movie recommendations on.
    - user (int): The ID of the user to recommend movies to.

    Returns:
    - A list of tuples, where each tuple contains the title and average rating of a recommended movie.
    """
    pred_df = fetch_predicted_ratings()
    user_ratings = fetch_user_ratings(user)
    temp_pred_df = pd.concat([pred_df, pd.DataFrame(user_ratings).T.rename({0: user})])
    temp_pred_df.fillna(0, inplace=True)

    # retrieves all the movie titles for a given genre.
    with engine.connect() as connection:
        query = text("SELECT m.title, m.movieId FROM movies as m "
                     "INNER JOIN movie_genre as mg ON m.movieId = mg.movieId "
                     "INNER JOIN genres as g ON mg.genre_id = g.genre_id "
                     "WHERE g.name LIKE :genre_pattern").params(genre_pattern=f"%{genre}%")
        result = connection.execute(query)
        movies_genres = pd.DataFrame(result.fetchall(), columns=['title', 'movieId'])

    movieId_to_title = dict(zip(movies_genres['movieId'], movies_genres['title']))

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = set(title for _, title in get_rated_movies(user))

    # Remove the movies that the user has already seen
    unseen_titles = [title for title in movies_genres['title'].tolist() if title not in seen_movies]

    # Find the three most similar users
    sim_users = get_similar_users(user, temp_pred_df)

    temp_pred_df.columns = temp_pred_df.columns.map(lambda x: movieId_to_title.get(x, x))

    # Filter the temp_pred_df DataFrame to only include the ratings from the similar users and selected titles
    valid_titles = [title for title in unseen_titles if title in temp_pred_df.columns]
    filtered_df = temp_pred_df.loc[sim_users, valid_titles]

    # Get the average ratings for the movies in the specified genre based on the ratings of the similar users
    genre_movie_ratings = filtered_df.mean(axis=0).round(2)

    # Sort the average movie ratings in descending order
    movie_ratings_sorted = genre_movie_ratings.sort_values(ascending=False)

    # Create a list of unique movie titles and their corresponding average ratings
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted, movieId_to_title)

    return unique_movie_list


def recommend_movies_based_on_year(year, user):
    """
    Recommends unseen movies released in a given year based on similar user ratings.

    Args:
        year (int): The year of movie release to filter by.
        user (int): The ID of the user for whom to generate recommendations.

    Returns:
        list: A list of tuples containing the recommended movies and their average predicted rating.

    """

    pred_df = fetch_predicted_ratings()
    user_ratings = fetch_user_ratings(user)
    temp_pred_df = pd.concat([pred_df, pd.DataFrame(user_ratings).T.rename({0: user})])
    temp_pred_df.fillna(0, inplace=True)

    with engine.connect() as connection:
        query = text("select title, movieId from movies Where year = :year_param;")
        result = connection.execute(query, {"year_param": year})
        movies_by_year = pd.DataFrame(result.fetchall(), columns=['title', 'movieId'])

    movieId_to_title = dict(zip(movies_by_year['movieId'], movies_by_year['title']))

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = set(title for _, title in get_rated_movies(user))

    # Remove the movies that the user has already seen
    unseen_titles = [title for title, movieId in zip(movies_by_year['title'], movies_by_year['movieId']) if
                     movieId not in seen_movies and movieId in temp_pred_df.columns]

    # Find the three most similar users
    sim_users = get_similar_users(user, temp_pred_df)

    temp_pred_df.columns = temp_pred_df.columns.map(lambda x: movieId_to_title.get(x, x))

    # Filter the temp_pred_df DataFrame to only include the ratings from the similar users and selected titles
    filtered_df = temp_pred_df.loc[sim_users, unseen_titles]

    # Get the average ratings for the movies in the specified genre based on the ratings of the similar users
    movies_by_year_ratings = filtered_df.mean(axis=0).round(2)

    # Sort the average movie ratings in descending order
    movie_ratings_sorted = movies_by_year_ratings.sort_values(ascending=False)

    # Create a list of unique movie titles and their corresponding average ratings
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted, movieId_to_title)

    return unique_movie_list


def recommend_movies_based_on_tags(phrase, user):
    """
    Recommends movies based on tags associated with the movie. Tags that are highly associated with the given phrase
    are used to recommend movies.

    Args:
        phrase (str): The phrase to be used for tag comparison.
        user (int): The user ID for which movie recommendations are being generated.

    Returns:
        A list of recommended movies based on the given phrase.
    """
    with engine.connect() as connection:
        query = text(
            "SELECT m.title, m.movieId, COALESCE(MAX(t.tag), '') AS tag, COALESCE(MAX(md.description), "
            "'') AS description FROM movies as m LEFT JOIN tags as t ON m.movieId = t.movieId LEFT JOIN "
            "movie_description as md ON m.movieId = md.movieId WHERE t.tag IS NOT NULL OR md.description IS NOT NULL "
            "GROUP BY m.movieId, m.title "
        )
        result = connection.execute(query)
        movies_and_tags = pd.DataFrame(result.fetchall(), columns=['title', 'movieId', 'tag', 'description'])

    # Create a SpaCy document for the given phrase
    phrase_doc = nlp(phrase)

    # Extract keyword from the description and calculate tag or keyword similarity scores
    similarities = []
    for index, row in movies_and_tags.iterrows():
        keyword = extract_keyword(row['description'])
        tag_or_keyword = row['tag'] if row['tag'] else keyword
        similarity = phrase_doc.similarity(nlp(tag_or_keyword))
        similarities.append(similarity)

    movies_and_tags['similarity'] = similarities

    # Filter tags with a similarity score greater than or equal to 0.6
    highly_related_tags = movies_and_tags[movies_and_tags['similarity'] >= 0.6]

    # Sort the DataFrame by similarity score in descending order
    highly_related_tags = highly_related_tags.sort_values(by='similarity', ascending=False)

    # Remove duplicate movie titles
    recommended_movies_df = highly_related_tags.drop_duplicates(subset='title')

    # Get the movies the user has already seen
    users_movies_seen = set(title for _, title in get_rated_movies(user))

    # Remove the movies that the user has already seen
    recommended_movies_df = recommended_movies_df[~recommended_movies_df['title'].isin(users_movies_seen)]

    # Convert the DataFrame column to a list
    recommended_movies = list(recommended_movies_df[['movieId', 'title']].itertuples(index=False, name=None))

    return recommended_movies


def recommend_movies_based_on_year_and_genre(year, genre, user):
    """
    Recommends movies to a user based on the specified year and genre. The function filters movies
    that match the given year and genre, then calculates average ratings using the ratings of the
    three most similar users, and finally recommends movies that the user has not seen yet.

    Args:
        year (int): The year for which movies should be filtered.
        genre (str): The genre for which movies should be filtered.
        user (int): The user ID for which movie recommendations are being generated.

    Returns:
        A list of recommended movies based on the specified year and genre.
    """
    pred_df = fetch_predicted_ratings()
    user_ratings = fetch_user_ratings(user)
    temp_pred_df = pd.concat([pred_df, pd.DataFrame(user_ratings).T.rename({0: user})])
    temp_pred_df.fillna(0, inplace=True)

    with engine.connect() as connection:
        query = text(
            "SELECT m.title, m.movieId "
            "FROM movies as m "
            "INNER JOIN movie_genre as mg ON m.movieId = mg.movieId "
            "INNER JOIN genres as g ON mg.genre_id = g.genre_id "
            "WHERE g.name LIKE :genre_pattern AND year = :year"
        )
        result = connection.execute(query, {'genre_pattern': f"%{genre}%", 'year': year})
        movies_genres = pd.DataFrame(result.fetchall(), columns=['title', 'movieId'])

    movieId_to_title = dict(zip(movies_genres['movieId'], movies_genres['title']))

    # creating a list of titles
    movie_titles = movies_genres['title'].tolist()

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = set(title for _, title in get_rated_movies(user))

    # Remove the movies that the user has already seen
    titles = get_unseen_movies(seen_movies, movie_titles)

    # Find the three most similar users
    sim_users = get_similar_users(user, temp_pred_df)

    temp_pred_df.columns = temp_pred_df.columns.map(lambda x: movieId_to_title.get(x, x))

    # Filter the temp_pred_df DataFrame to only include the ratings from the similar users and selected titles
    filtered_df = temp_pred_df.loc[sim_users, titles]

    # Get the average ratings for the movies in the specified genre based on the ratings of the similar users
    movies_by_year_ratings = filtered_df.mean(axis=0).round(2)

    # Sort the average movie ratings in descending order
    movie_ratings_sorted = movies_by_year_ratings.sort_values(ascending=False)

    # Create a list of unique movie titles and their corresponding average ratings
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted, movieId_to_title)

    return unique_movie_list


def recommend_movies_to_rate_for_new_users(user):
    """
        Recommends popular movies for a new user to rate.

        Args:
            user (int): The ID of the new user.

        Returns:
            list: A list of popular movies that the new user has not yet rated.
        """
    rated_movies = set(get_rated_movies(user))
    popular_movies = set(popular_movies_df())

    # Remove the movies that the user has already rated from the popular_movies_list
    movies_to_rate = popular_movies - rated_movies

    if len(rated_movies) < 10:
        return list(movies_to_rate)
