from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from System.Workplace.workplace import pred_df, item_user_ratings_df
from fuzzywuzzy import process
from System.Workplace.workplace import mydb
import spacy

# Strip title of whitespace
pred_df.index = pred_df.index.astype(str).str.strip("'")
pred_df = pred_df.reset_index()
# To create a data frame of pred_df where the item is indexed.
item_pred_df = pred_df.transpose()
# pivot table for ratings data, with no predicted values
ratings_pivot_table = pd.pivot_table(item_user_ratings_df, index='userId', columns='title', values='ratings')
# This is a pivot table for ratings with no predicted values and the items are indexed.
item_pivot_table = pd.pivot_table(item_user_ratings_df, index='title', columns='userId', values='ratings')
ratings_pivot_table.fillna(0, inplace=True)
item_pivot_table.fillna(0, inplace=True)

# finding the similarities between items
similarities = cosine_similarity(item_pred_df)
# Creating a dataframe to compare similarities between different items.
cosine_similarity_df = pd.DataFrame(similarities, index=item_pred_df.index, columns=item_pred_df.index)


# TODO I want to change this to recommend not just the highest rated movie the user has not watched but to compare against similar users and recommend that way.
def recommend_movies_based_on_user(user_id, num_recommended_movies):
    print(f'The list of the Movies {user_id} Has Watched -- Only showing for test purposes \n')

    movies_watched = ratings_pivot_table.loc[user_id][ratings_pivot_table.loc[user_id] > 0].index.tolist()

    # outputs all the movies viewed by the user
    for m in movies_watched:
        print(m)

    print('\n')

    # a list that will keep track of all the movies our system would recommend.
    recommended_movies = []

    # iterates through a list of unseen movies and sets the index of the movie to index_df.
    for m in ratings_pivot_table.columns[ratings_pivot_table.loc[user_id] == 0].tolist():
        pred_movie_ratings_df = pred_df.loc[user_id, m]
        # the pred_movie_ratings_df is used to access the predicted rating of the unseen movie from the dataframe
        recommended_movies.append((m, pred_movie_ratings_df))

    # a list of recommended movies sorted according to predicted ratings in descending order.
    sorted_rm = sorted(recommended_movies, key=lambda x: x[1], reverse=True)

    # outputs a list of recommended movies, with the rank of the movie.
    print('The list of the Recommended Movies \n')
    rank = 1
    for recommended_movie in sorted_rm[:num_recommended_movies]:
        print(f'{rank}: {recommended_movie[0]} - predicted rating:{round(recommended_movie[1], 1)}')
        rank = rank + 1


# TODO add functionality to find also the similar users and use that to give the best movie based on title.
# Recommends a movie based of the title, checks if a user has viewed the movie and returns a list of movies similar
# to the title but that have not been seen.
def recommend_movie_based_on_similar_title(title, user):
    # uses Knn metric and trains data on the dataframe values which finds the 3 nearest neighbours.
    global index_user_likes
    knn = NearestNeighbors(metric='cosine', algorithm='brute')
    knn.fit(item_pred_df.values)
    distances, indices = knn.kneighbors(item_pred_df.values, n_neighbors=5)

    # a list of all movie titles
    titles = item_pred_df.index.tolist()
    match = process.extractOne(title, titles)

    if match[1] >= 80:
        index_user_likes = item_pred_df.index.tolist().index(match[0])  # get an index for a movie
    else:
        print("Error: No movie with a similar title found.")

    sim_movies = indices[index_user_likes].tolist()  # make list for similar movies
    movie_distances = distances[index_user_likes].tolist()  # the list for distances of similar movies
    id_movie = sim_movies.index(index_user_likes)  # get the position of the movie itself in indices and distances

    print('Unseen similar movies to ' + str(item_pred_df.index[index_user_likes]) + ': \n')

    sim_movies.remove(index_user_likes)  # remove the movie itself in indices
    movie_distances.pop(id_movie)  # remove the movie itself in distances

    # An empty list to keep track of all movies the current user has viewed
    seen_movies = []

    # a for loop to loop through all the movies the user has seen and then appends said movie to the seen_movies list
    for m in ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist():
        seen_movies.append(m)

    # checks to see if similar movies to be recommended are present in the seen_movies list. if they are
    # removed from the similar movies.
    for i in sim_movies:
        if item_pred_df.index[i] in seen_movies:
            sim_movies.remove(i)

    # This then prints out all the movies in the similar movies list, giving each movie present a rank.
    rank = 1
    for movie in sim_movies:
        print(f'{rank}: {item_pred_df.index[movie]}')
        rank = rank + 1


def recommend_movie_based_on_genre(genre, user):
    movies_genres = pd.read_sql(
        f"select m.title from movies as m inner join movie_genre as mg  on m.movieId = mg.movieId inner join genres "
        f"as g  on mg.genre_id = g.genre_id Where g.name like '%{genre}%';", con=mydb)

    title_list = movies_genres['title'].tolist()

    # Remove the movies that the user has already seen
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    titles = [title for title in title_list if title not in seen_movies]

    movie_ratings = []

    # TODO error with repeated titles for specific users.

    for title in titles:
        try:
            movie_index = item_pred_df.index.tolist().index(title)
            user_rating = item_pred_df.iloc[movie_index, user]
            movie_ratings.append((title, user_rating))
        except ValueError:
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    top_movies = movie_ratings_sorted[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}: {movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


def recommend_movies_based_on_year(year, user):
    movies_by_year = pd.read_sql(
        f"select title from movies Where year = {year};", con=mydb)

    title_list = movies_by_year['title'].tolist()

    # Remove the movies that the user has already seen
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    titles = [title for title in title_list if title not in seen_movies]

    movie_ratings = []

    for title in titles:
        try:
            movie_index = item_pred_df.index.tolist().index(title)
            user_rating = item_pred_df.iloc[movie_index, user]
            movie_ratings.append((title, user_rating))
        except ValueError:
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    top_movies = movie_ratings_sorted[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}: {movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


def recommend_movies_based_on_tags(phrase, user):
    # initialising spacy model, this model has word vectors included.
    nlp = spacy.load("en_core_web_lg")

    movie_and_tags = pd.read_sql(
        f"select m.title, t.movieId, t.tag from tags as t inner join movies as m on t.movieId = m.movieId;", con=mydb)

    # creating a list of titles
    tags_list = movie_and_tags['tag'].tolist()

    tag_comparison_values = []

    for tag in tags_list:
        similarity_score = nlp(phrase).similarity(nlp(tag))
        tag_comparison_values.append((tag, similarity_score))

    # Sort the list of movie ratings by user rating in descending order
    tag_ratings_sorted = sorted(tag_comparison_values, key=lambda x: x[1], reverse=True)

    # extracts only the tags most associated with our given phrase.
    highly_related_tags = [tag for tag in tag_ratings_sorted if tag[1] >= 0.5]

    # creates an empty set
    movie_titles = set()

    # This iterates through each tag and retrieves the money for each associated tag.
    for tag in highly_related_tags:
        titles = movie_and_tags[movie_and_tags['tag'] == tag[0]]
        list_of_titles = titles['title'].tolist()
        movie_titles.update(list_of_titles)
        list_of_titles.clear()

    movie_titles_list = list(movie_titles)

    #   have a list for all the movies the user has watched.
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    movie_titles_list = [title for title in movie_titles_list if title not in seen_movies]

    movie_ratings = []

    for title in movie_titles_list:
        try:
            movie_index = item_pred_df.index.tolist().index(title)
            user_rating = item_pred_df.iloc[movie_index, user]
            movie_ratings.append((title, user_rating))
        except ValueError:
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    top_movies = movie_ratings_sorted[:5]
    rank = 1
    for movie in top_movies:
        print(f'{rank}:{movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


def recommend_movies_based_on_year_and_genre(year, genre, user):
    sql_query = pd.read_sql(
        f"select m.title from movies as m inner join movie_genre as mg on m.movieId = mg.movieId Inner join "
        f"genres as g on mg.genre_id = g.genre_id where g.name like '%{genre}%' and year = {year}", con=mydb)

    movie_titles = sql_query['title'].tolist()

    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    movie_titles_list = [title for title in movie_titles if title not in seen_movies]

    movie_ratings = []

    for title in movie_titles_list:
        try:
            movie_index = item_pred_df.index.tolist().index(title)
            user_rating = item_pred_df.iloc[movie_index, user]
            movie_ratings.append((title, user_rating))
        except ValueError:
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    top_movies = movie_ratings_sorted[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}:{movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


# TODO after meeting: based of similar actors/directors/titles/genre's -- user-based collaborative filtering
#  TODO 3 Create more recommendations based possibly on actors, directors, and also similar users.


# recommend_movies_based_on_year_and_genre(1990, 'action', 1)
# recommend_movies_based_on_tags('happy', 1)
# recommend_movie_based_on_genre('drama', 11)
# recommend_movies_based_on_year(1990, 1)
# recommend_movie_based_on_similar_title("hun", 5)
# recommend_movies_based_on_user(4, 3)
