from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sklearn.neighbors import NearestNeighbors
import pandas as pd
from sqlalchemy import create_engine, text
from fuzzywuzzy import process
from System.Workplace.workplace import mydb
import spacy

# TODO 0 - Split recommendation functions in a manageable way(do this later) and then comment code.
# TODO 2 - You may want to add error handling to your functions to handle exceptions that may arise during database connections, queries, or other operations. This will help make your functions more robust and provide better feedback to the user in case something goes wrong.
# after recommendation engine
# TODO 5 - In the get_rated_movies() function, you have an SQL query that uses %s as placeholders for parameters. In the previous response, I suggested using SQLAlchemy's text() function to create parameterized queries. You can use a similar approach in this function to make your code more robust and avoid SQL injection vulnerabilities.
# TODO 6 - n the store_rating() function, you are using a cursor to execute the SQL query. While this approach works, it's recommended to use the with statement when working with database connections and cursors to ensure that the resources are properly closed after use. For example, you can rewrite the function like this:


db_connection_string = "mysql+mysqlconnector://root:root@localhost:3306/movierecommendation"
engine = create_engine(db_connection_string)
nlp = spacy.load("en_core_web_lg")


def popular_movies_df():
    query = """SELECT m.movieId, m.title, COUNT(r.ratings) as num_ratings, AVG(r.ratings) as avg_rating
               FROM movies as m
               INNER JOIN ratings as r ON m.movieId = r.movieId
               GROUP BY m.movieId, m.title 
               HAVING num_ratings > 30
               ORDER BY avg_rating DESC, m.movieId ASC;"""
    popular_movies_df = pd.read_sql_query(query, con=mydb)
    return list(zip(popular_movies_df['movieId'], popular_movies_df['title']))


def get_rated_movies(user):
    query = """SELECT r.movieId, m.title
               FROM ratings as r
               INNER JOIN movies as m ON r.movieId = m.movieId
               WHERE userId = %s AND ratings > 0;"""
    rated_movies_df = pd.read_sql_query(query, con=mydb, params=[user])
    return list(rated_movies_df[['movieId', 'title']].itertuples(index=False, name=None))


def count_rated_movies_for_user(user):
    """Count the number of movies the given user has rated."""
    query = "SELECT COUNT(*) FROM ratings WHERE userId = %s"
    count_ratings_df = pd.read_sql_query(query, con=mydb, params=[str(user)])
    num_rated_movies = count_ratings_df.iloc[0][0]
    return num_rated_movies


def store_rating(user_id, movie_id, rating):
    print(f"Storing rating: user_id={user_id}, movie_id={movie_id}, rating={rating}")
    query = "INSERT INTO ratings (userId, movieId, ratings) VALUES (%s, %s, %s)"
    cursor = mydb.cursor()
    cursor.execute(query, (user_id, movie_id, rating))
    mydb.commit()
    print("Rating stored successfully")


def get_movie_data():
    with engine.connect() as connection:
        query = text("SELECT m.title, g.name, t.tag "
                     "FROM movies as m "
                     "INNER JOIN movie_genre as mg ON m.movieId = mg.movieId "
                     "INNER JOIN genres as g ON mg.genre_id = g.genre_id "
                     "INNER JOIN tags as t ON m.movieId = t.movieId;")
        result = connection.execute(query)
        movie_data = pd.DataFrame(result.fetchall(), columns=['title', 'genre', 'tag'])
        return movie_data


def create_movie_features(movie_data):
    # Combine genres and description into a single text feature
    movie_data['features'] = movie_data['genre'] + ' ' + movie_data['tag']
    return movie_data


def get_unseen_movies(user_seen_movies, all_movies):
    return [movie for movie in all_movies if movie not in user_seen_movies]


def get_similar_users(user, temp_pred_df):
    return find_similar_users(user, temp_pred_df)


def get_unique_movie_list(movie_ratings_sorted):
    return [(title, rating) for title, rating in movie_ratings_sorted.items()]


def fetch_predicted_ratings():
    with engine.connect() as connection:
        query = text('SELECT userId, movieId, ratings FROM pred_ratings')
        result = connection.execute(query)
        pred_df = pd.DataFrame(result.fetchall(), columns=['userId', 'movieId', 'ratings'])
        return pred_df.pivot(index='userId', columns='movieId', values='ratings')


def fetch_user_ratings(user_id):
    with engine.connect() as connection:
        query = text("SELECT movieId, ratings FROM ratings WHERE userId = :user_id;")
        result = connection.execute(query, {'user_id': user_id})
        user_ratings_df = pd.DataFrame(result.fetchall(), columns=['movieId', 'ratings'])
        user_ratings_series = pd.Series(data=user_ratings_df["ratings"].values, index=user_ratings_df["movieId"].values)
        return user_ratings_series


def find_similar_users(user_id, temp_pred_df):
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
            recommended_movies.append((movie_title, round(avg_rating, 1)))

    return recommended_movies


def fetch_item_predicted_ratings():
    with engine.connect() as connection:
        query = text('select m.title, p.userId, p.ratings from movies as m inner join pred_ratings as p on m.movieId '
                     '= p.movieId')
        result = connection.execute(query)
        item_pred_df = pd.DataFrame(result.fetchall(), columns=['title', 'userId', 'ratings'])

        # Pivot the DataFrame
        item_pred_pivot = item_pred_df.pivot_table(index='title', columns='userId', values='ratings')

        return item_pred_pivot


def recommend_movies_based_on_user(user_id):
    pred_df = fetch_predicted_ratings()
    user_ratings = fetch_user_ratings(user_id)

    temp_pred_df = pd.concat([pred_df, pd.DataFrame(user_ratings).T.rename({0: user_id})])

    temp_pred_df.fillna(0, inplace=True)

    sim_users = find_similar_users(user_id, temp_pred_df)
    top_rated_movies = fetch_top_rated_movies(sim_users)
    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = [title for _, title in get_rated_movies(user_id)]
    # Remove the movies that the user has already seen
    recommended_movies = [title for title in top_rated_movies if title not in seen_movies]

    return recommended_movies


def recommend_movies_based_on_title(title, user):
    movie_data = get_movie_data()
    movie_data = create_movie_features(movie_data)

    titles = movie_data['title'].tolist()

    # Find the closest matching title using FuzzyWuzzy
    match = process.extractOne(title, titles)
    if match[1] >= 80:
        matched_title = match[0]
        index_user_likes = titles.index(matched_title)
    else:
        return "No movie with a similar title found."

    # Calculate the TF-IDF matrix
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(movie_data['features'])

    # Calculate cosine similarities
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

    # Get the indices of the most similar movies
    sim_scores = list(enumerate(cosine_sim[index_user_likes]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Remove the first element, which is the movie itself
    sim_scores = sim_scores[1:6]

    # Get the movie indices
    sim_movie_indices = [i[0] for i in sim_scores]

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = [title for _, title in get_rated_movies(user)]

    recommended_movies = []
    for movie_index in sim_movie_indices:
        movie_title = titles[movie_index]
        if movie_title not in seen_movies and movie_title not in recommended_movies and movie_title != matched_title:
            recommended_movies.append(movie_title)

    return recommended_movies


def recommend_movies_based_on_genre(genre, user):
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

    # creates a list for all the titles in a given genre.
    title_list = movies_genres['title'].tolist()

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = [title for _, title in get_rated_movies(user)]

    # Remove the movies that the user has already seen
    titles = get_unseen_movies(seen_movies, title_list)

    # Find the three most similar users
    sim_users = get_similar_users(user, temp_pred_df)

    temp_pred_df.columns = temp_pred_df.columns.map(lambda x: movieId_to_title.get(x, x))

    # Filter the temp_pred_df DataFrame to only include the ratings from the similar users and selected titles
    filtered_df = temp_pred_df.loc[sim_users, titles]

    # Get the average ratings for the movies in the specified genre based on the ratings of the similar users
    genre_movie_ratings = filtered_df.mean(axis=0).round(2)

    # Sort the average movie ratings in descending order
    movie_ratings_sorted = genre_movie_ratings.sort_values(ascending=False)

    # Create a list of unique movie titles and their corresponding average ratings
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted)

    return unique_movie_list


def recommend_movies_based_on_year(year, user):
    pred_df = fetch_predicted_ratings()
    user_ratings = fetch_user_ratings(user)
    temp_pred_df = pd.concat([pred_df, pd.DataFrame(user_ratings).T.rename({0: user})])
    temp_pred_df.fillna(0, inplace=True)

    with engine.connect() as connection:
        query = text("select title, movieId from movies Where year = :year_param;")
        result = connection.execute(query, {"year_param": year})
        movies_by_year = pd.DataFrame(result.fetchall(), columns=['title', 'movieId'])

    movieId_to_title = dict(zip(movies_by_year['movieId'], movies_by_year['title']))

    # we create a list for all the movies title.
    title_list = movies_by_year['title'].tolist()

    # Get the movies the user has already seen using the get_rated_movies function
    seen_movies = [title for _, title in get_rated_movies(user)]

    # Remove the movies that the user has already seen
    titles = get_unseen_movies(seen_movies, title_list)

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
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted)

    return unique_movie_list


# Recommends movies based of a given phrase for a given user.
def recommend_movies_based_on_tags(phrase, user):
    # retrieves  all the titles, movieId and tags
    with engine.connect() as connection:
        query = text(
            f" select m.title, t.movieId, t.tag from tags as t inner join movies as m on t.movieId = m.movieId;")
        result = connection.execute(query)
        movies_and_tags = pd.DataFrame(result.fetchall(), columns=['title', 'movieId', 'tag'])

    # creating a list of tags
    movie_title_tag_list = list(zip(movies_and_tags['title'], movies_and_tags['tag']))

    # This list holds all the tags and the associated similarity scores between the given phrase.
    tag_comparison_values = []

    # iterates through the list of tags and measures the comparison between each tag and the provided phrase.
    for tag in movie_title_tag_list:
        similarity_score = nlp(phrase).similarity(nlp(tag[1]))
        tag_comparison_values.append((tag, similarity_score))

    # extracts only the tags most associated with our given phrase.
    highly_related_tags = [tag for tag in tag_comparison_values if tag[1] >= 0.6]

    # Sort the list of tags and scores in descending order.
    tag_ratings_sorted = sorted(highly_related_tags, key=lambda x: x[1], reverse=True)

    seen_titles = set()
    movie_titles = [tup[0][0] for tup in tag_ratings_sorted if
                    not (tup[0][0] in seen_titles or seen_titles.add(tup[0][0]))]

    # changes the set movies_titles into a list.
    movie_titles_list = list(movie_titles)

    # Get the movies the user has already seen using the get_rated_movies function
    users_movies_seen = [title for _, title in get_rated_movies(user)]

    # Remove the movies that the user has already seen
    recommended_movies = [title for title in movie_titles_list if title not in users_movies_seen]

    return recommended_movies


# recommend movies based of the year and genre
def recommend_movies_based_on_year_and_genre(year, genre, user):
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
    seen_movies = [title for _, title in get_rated_movies(user)]

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
    unique_movie_list = get_unique_movie_list(movie_ratings_sorted)

    return unique_movie_list


def recommend_movies_to_rate_for_new_users(user):
    rated_movies = set(get_rated_movies(user))
    popular_movies = set(popular_movies_df())

    # Remove the movies that the user has already rated from the popular_movies_list
    movies_to_rate = popular_movies - rated_movies

    if len(rated_movies) < 10:
        return list(movies_to_rate)


# recommend_movies_to_rate_for_new_users(615)
# print(recommend_movies_based_on_year_and_genre(1990, 'act', 612))
# print(recommend_movies_based_on_tags('animals', 612))
# print(recommend_movies_based_on_genre('action', 612))
# print(recommend_movies_based_on_year(2007, 612))
# print(recommend_movies_based_on_similar_title("Schindler's List", 612))
print(recommend_movies_based_on_title('Truman Show, The', 612))
# print(recommend_movies_based_on_user(612))
