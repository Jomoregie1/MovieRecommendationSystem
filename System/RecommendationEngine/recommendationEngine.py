from sklearn.neighbors import NearestNeighbors
from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
import numpy as np
import mysql.connector
import pandas as pd
from System.Workplace.workplace import pred_df, item_user_ratings_df

# user_5_ratings = pred_df.loc[1, :].sort_values(ascending=False)
# print(user_5_ratings.head)
# ratings_table.fillna(0,inplace=True)
pred_df.index = pred_df.index.astype(str).str.strip("'")
pred_df = pred_df.reset_index()
item_pred_df = pred_df.transpose()
ratings_pivot_table = pd.pivot_table(item_user_ratings_df, index='userId', columns='title', values='ratings')
item_pivot_table = pd.pivot_table(item_user_ratings_df, index='title', columns='userId', values='ratings')
ratings_pivot_table.fillna(0, inplace=True)
item_pivot_table.fillna(0, inplace=True)

#   # An empty list to keep track of all movies the current user has viewed
# seen_movies = []
#
#     # a for loop to loop through all the movies the user has seen and then appends said movie to the seen_movies list
# for m in ratings_pivot_table.loc[1][ratings_pivot_table.loc[1] > 0].index.tolist():
#     seen_movies.append(m)
#
# knn = NearestNeighbors(metric='cosine', algorithm='brute')
# knn.fit(item_pred_df.values)
# distances, indices = knn.kneighbors(item_pred_df.values, n_neighbors=3)
# index_user_likes = item_pred_df.index.tolist().index("Toy Story")
# sim_movies = indices[index_user_likes].tolist()
# print(f'this is the scene movies...{sim_movies}')
# for i in sim_movies:
#     if item_pred_df.index[i] in seen_movies:
#         pass
#     print(item_pred_df.index[i])


def recommend_movies_based_on_user(user_id, num_recommended_movies):
    print(f'The list of the Movies {user_id} Has Watched \n')

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


# Recommends a movie based of the title, checks if a user has viewed the movie and returns a list of movies similar
# to the title but that have not been seen.
def recommend_movie_based_on_title(title, user):
    # uses cosing similarity metric and trains data on the dataframe values which finds the 3 nearest neighbours.
    knn = NearestNeighbors(metric='cosine', algorithm='brute')
    knn.fit(item_pred_df.values)
    distances, indices = knn.kneighbors(item_pred_df.values, n_neighbors=5)

    index_user_likes = item_pred_df.index.tolist().index(title)  # get an index for a movie
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


# TODO after meeting: based of similar actors/directors/titles/genre's -- user-based collaborative filtering. TODO 1
#  add movies.csv and rating.csv to mysql database (create all tables and get current features working same way with
#  sql) TODO 2 watch youtube video to understand how recommendations are working TODO 3 Create more recommendations
#   based possibly on actors, directors, genres and also similar users.
#
recommend_movie_based_on_title("Toy Story", 5)
recommend_movies_based_on_user(3, 10)
