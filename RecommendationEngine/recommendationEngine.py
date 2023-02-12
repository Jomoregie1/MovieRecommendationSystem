from sklearn.neighbors import NearestNeighbors
import pandas as pd

ratings_data = pd.read_csv('C:/Users/Joseph/PycharmProjects/MovieRecommendationSystem/Movies_data/ratings.csv',
                           usecols=['userId', 'movieId', 'rating'])
movies_data = pd.read_csv('C:/Users/Joseph/PycharmProjects/MovieRecommendationSystem/Movies_data/movies.csv',
                          usecols=['movieId', 'title', 'genres'])
tags_data = pd.read_csv('C:/Users/Joseph/PycharmProjects/MovieRecommendationSystem/Movies_data/tags.csv',
                        usecols=['userId', 'movieId', 'tag'])

# Split the 'genres' column on the '|' character
genres_df = movies_data['genres'].str.split('|', expand=True)
# Rename the columns to 'genre_0', 'genre_1', etc.
genres_df = genres_df.add_prefix('genre_')
# Concatenate the original DataFrame and the new genre DataFrame
movies_data = pd.concat([movies_data, genres_df], axis=1)
# Melt the 'movies_data' DataFrame to create a long format
movies_long = pd.melt(movies_data, id_vars=['movieId', 'title'],
                      value_vars=['genre_0', 'genre_1', 'genre_2', 'genre_3', 'genre_4', 'genre_5', 'genre_6',
                                  'genre_7', 'genre_8', 'genre_9'], value_name='genre').drop('variable',
                                                                                             axis=1).dropna()
# Drop any rows with missing genre values
movies_long = movies_long.dropna(subset=['genre'])
# Drop the 'genres' column from the original DataFrame
movies_data = movies_data.drop('genres', axis=1)
# Create a new DataFrame with unique genre values and the movie titles that belong to each genre
genres_data = movies_long.groupby('genre')['movieId'].apply(list).reset_index()
genres_data.columns = ['genre', 'movieIds']

# Split the year from the movie titles
new_df = movies_data['title'].str.split('(', n=1, expand=True)
new_df.columns = ['title', 'year']
new_df['year'] = new_df['year'].str.rstrip(')')
new_df['year'] = new_df['year'].str[-4:]

# Create a new data frame with movie ID and title
cleaned_movies_data = pd.concat([movies_data['movieId'], new_df['title']], axis=1)
# Create a new data frame with the movie ID and year
movie_year_df = pd.concat([movies_data['movieId'], new_df['year']], axis=1)

combined_data = pd.merge(ratings_data, movies_data, how='inner', on='movieId')
combined_year_movies_data = pd.merge(cleaned_movies_data, movie_year_df, how='inner', on='movieId')
combined_year_movies_data['year'] = combined_year_movies_data['year'].fillna(0)
combined_year_movies_data['year'] = combined_year_movies_data['year'].apply(lambda x: int(str(x).strip(') ')))
combined_year_movies_data['title'] = combined_year_movies_data['title'].apply(lambda x: str(x).strip())

print(combined_data)

# creates a pivot table and places a 0 where empty data is, we are going to assume that where there is a 0 the movie
# has not been watched.
df = combined_data.pivot_table(index='title', columns='userId', values='rating', fill_value=0)
df1 = df.copy()

# # Recommends movies based of unwatched movies by the user.
# def recommend_movies_based_on_user(user, num_recommended_movies):
#     print(f'The list of the Movies {user} Has Watched \n')
#
#     # outputs all the movies viewed by the user
#     for m in df[df[user] > 0][user].index.tolist():
#         print(m)
#
#     print('\n')
#
#     # a list that will keep track of all the movies our system would recommend.
#     recommended_movies = []
#
#     # iterates through a list of unseen movies and sets the index of the movie to index_df.
#     for m in df[df[user] == 0].index.tolist():
#         index_df = df.index.tolist().index(m)
#         # the index_df is used to access the predicted rating of the unseen movie from the dataframe
#         predicted_rating = df1.iloc[index_df, df1.columns.tolist().index(user)]
#         # A tuple of the title and the predicted rating os appended to a list
#         recommended_movies.append((m, predicted_rating))
#
#     # a list of recommended movies sorted according to predicted ratings in descending order.
#     sorted_rm = sorted(recommended_movies, key=lambda x: x[1], reverse=True)
#
#     # outputs a list of recommended movies, with the rank of the movie.
#     print('The list of the Recommended Movies \n')
#     rank = 1
#     for recommended_movie in sorted_rm[:num_recommended_movies]:
#         print(f'{rank}: {recommended_movie[0]} - predicted rating:{recommended_movie[1]}')
#         rank = rank + 1
#
#
# # Recommends a movie based of the title, checks if a user has viewed the movie and returns a list of movies similar
# # to the title but that have not been seen.
# def recommend_movie_based_on_title(title, user):
#     # uses cosing similarity metric and trains data on the dataframe values which finds the 3 nearest neighbours.
#     knn = NearestNeighbors(metric='cosine', algorithm='brute')
#     knn.fit(df.values)
#     distances, indices = knn.kneighbors(df.values, n_neighbors=3)
#
#     index_user_likes = df.index.tolist().index(title)  # get an index for a movie
#     sim_movies = indices[index_user_likes].tolist()  # make list for similar movies
#     movie_distances = distances[index_user_likes].tolist()  # the list for distances of similar movies
#     id_movie = sim_movies.index(index_user_likes)  # get the position of the movie itself in indices and distances
#
#     print('Unseen similar movies to ' + str(df.index[index_user_likes]) + ': \n')
#
#     sim_movies.remove(index_user_likes)  # remove the movie itself in indices
#     movie_distances.pop(id_movie)  # remove the movie itself in distances
#
#     # An empty list to keep track of all movies the current user has viewed
#     seen_movies = []
#
#     # a for loop to loop through all the movies the user has seen and then appends said movie to the seen_movies list
#     for m in df[df[user] > 0].index.tolist():
#         seen_movies.append(m)
#
#     # checks to see if similar movies to be recommended are present in the seen_movies list. if they are they are
#     # removed from the similar movies.
#     for i in sim_movies:
#         if df.index[i] in seen_movies:
#             sim_movies.remove(i)
#
#     # This the prints out all the movies in the similar movies list, giving each movie present a rank.
#     rank = 1
#     for movie in sim_movies:
#         print(f'{rank}: {df.index[movie]}')
#         rank = rank + 1
#
#
# # TODO after meeting: based of similar actors/directors/titles/genre's -- user-based collaborative filtering. TODO 1
# #  add movies.csv and rating.csv to mysql database (create all tables and get current features working same way with
# #  sql) TODO 2 watch youtube video to understand how recommendations are working TODO 3 Create more recommendations
# #   based possibly on actors, directors, genres and also similar users.
#
# recommend_movie_based_on_title("Toy Story (1995)", 5)
# recommend_movies_based_on_user(1, 10)
