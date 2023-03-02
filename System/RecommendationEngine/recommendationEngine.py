from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from System.Workplace.workplace import pred_df, item_user_ratings_df
from fuzzywuzzy import process
from System.Workplace.workplace import mydb
import spacy

# To create a data frame of pred_df where the item is indexed.
item_pred_df = pred_df.transpose()
# pivot table for ratings data, with no predicted values where the userId is indexed.
ratings_pivot_table = pd.pivot_table(item_user_ratings_df, index='userId', columns='title', values='ratings')
# This is a pivot table for ratings with no predicted values and the items are indexed.
item_pivot_table = pd.pivot_table(item_user_ratings_df, index='title', columns='userId', values='ratings')

# Fill both nan's with 0's
ratings_pivot_table.fillna(0, inplace=True)
item_pivot_table.fillna(0, inplace=True)

# finding the similarities between items to make predictions.
similarities = cosine_similarity(item_pred_df)
# Creating a dataframe to compare similarities between different items.
cosine_similarity_df = pd.DataFrame(similarities, index=item_pred_df.index, columns=item_pred_df.index)


# This recommends based of movies the user has not seen, it takes the amount of movies the user would like recommended.
def recommend_movies_based_on_user(user_id, num_recommended_movies):
    # Using KNN to find the 5 nearest neighbours to the given user_id.
    knn = NearestNeighbors(metric='cosine', algorithm='brute')
    knn.fit(pred_df.values)
    distances, indices = knn.kneighbors(pred_df.values, n_neighbors=5)

    # Find the index of the given user in the pred_df dataframe.
    user_index = pred_df.index.tolist().index(user_id)  # get an index for a given user

    sim_users = indices[user_index].tolist()  # make list for similar users
    user_distances = distances[user_index].tolist()  # the list for distances of similar users
    id_user = sim_users.index(user_index)  # get the position of the users itself in indices and distances

    # remove user in the similar users list and in the user_distances list.
    sim_users.remove(user_index)
    user_distances.pop(id_user)

    # a list that will keep track of all the movies our system would recommend.
    recommended_movies = []

    # iterates through a list of unseen movies and sets the index of the movie to index_df.
    for m in ratings_pivot_table.columns[ratings_pivot_table.loc[user_id] == 0].tolist():
        pred_movie_ratings_df = pred_df.loc[user_id, m]
        # the pred_movie_ratings_df is used to access the predicted rating of the unseen movie from the dataframe
        recommended_movies.append((m, pred_movie_ratings_df))

    # a list of recommended movies sorted according to predicted ratings in descending order.
    sorted_rm = sorted(recommended_movies, key=lambda x: x[1], reverse=True)

    # prints a list of recommended movies, based on movies not viewed by the user and predicted highly.
    print('The list of the Recommended Movies for you! \n')
    rank = 1
    for recommended_movie in sorted_rm[:num_recommended_movies]:
        print(f'{rank}: {recommended_movie[0]} - predicted rating:{round(recommended_movie[1], 1)}')
        rank = rank + 1

    # create an empty list for to hold the average ratings of similar users, for each movie that is highly
    average_sim_users_rating = []
    # This variable will hold the avg for the movie
    avg_movie_rating = 0

    # this helps calculate the average similar users to the give users rate a particular movie.
    for movie in sorted_rm:
        for user in sim_users:
            avg_movie_rating += pred_df.loc[user, movie[0]]

        avg_movie_rating = avg_movie_rating / len(sim_users)
        average_sim_users_rating.append((movie, avg_movie_rating))
        avg_movie_rating = 0

    # sorts all the movies that have already been sorted by highest user ratings by average ratings of similar users
    sorted_average_by_sim_users = sorted(average_sim_users_rating, key=lambda x: x[1], reverse=True)

    # outputs a list of recommended movies, with the rank of the movie.
    print('\n')
    print('The list of the Recommended potential hidden gems! \n')
    rank = 1

    # To prevent the same movie recommended twice, a quick check to see
    # if the movie was being recommended is in the previous list. if it is, it is popped out.
    for recommended_movie in sorted_average_by_sim_users[:num_recommended_movies]:
        if recommended_movie[0] in sorted_rm[:num_recommended_movies]:
            index_of_recommended_movie = sorted_average_by_sim_users.index(recommended_movie)
            sorted_average_by_sim_users.pop(index_of_recommended_movie)
        else:
            print(f'{rank}: {recommended_movie[0][0]} - predicted rating:{round(recommended_movie[0][1], 1)}')
            rank = rank + 1


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

    # retrieves the index of the  closest related movie for the given title
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


# recommends movies for a given genre based of a given user.
def recommend_movie_based_on_genre(genre, user):
    # retrieves all the movie titles for a given genre.
    movies_genres = pd.read_sql(
        f"select m.title from movies as m inner join movie_genre as mg  on m.movieId = mg.movieId inner join genres "
        f"as g  on mg.genre_id = g.genre_id Where g.name like '%{genre}%';", con=mydb)

    # creates a list for all the titles in a given genre.
    title_list = movies_genres['title'].tolist()

    # Remove the movies that the user has already seen
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    titles = [title for title in title_list if title not in seen_movies]

    # create an empty list to hold all the titles and ratings for each movie.
    movie_ratings = []

    # TODO error with repeated titles for specific users.

    for title in titles:
        try:
            # finds the index for a given title
            movie_index = item_pred_df.index.tolist().index(title)
            # retrieves the rating for a given movie index and user
            user_rating = item_pred_df.iloc[movie_index, user]
            # adds both the rating and title of the movie to the movie_ratings list.
            movie_ratings.append((title, user_rating))
        except ValueError:
            # if the title is not found in the dataframe then we continue onto the next movie title.
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    # create a temp dictionary to hold only unique movie titles.
    temp_movie_ratings_dict = {}
    for item in movie_ratings_sorted:
        if item[0] not in temp_movie_ratings_dict:
            temp_movie_ratings_dict[item[0]] = item[1]

    # casting the temp dict into a list to retrieve the highest rated movie.
    unique_movie_list = list(temp_movie_ratings_dict.items())

    # This allows us to output the top 3 rated movies in our list.
    top_movies = unique_movie_list[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}: {movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


# Recommend movies based of a given year.
def recommend_movies_based_on_year(year, user):
    # This retrieves the movie titles for a given year
    movies_by_year = pd.read_sql(
        f"select title from movies Where year = {year};", con=mydb)

    # we create a list for all the movies title.
    title_list = movies_by_year['title'].tolist()

    # Remove the movies that the user has already seen
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    titles = [title for title in title_list if title not in seen_movies]

    # This saves a list of the title and user ratings for the given users.
    movie_ratings = []

    for title in titles:
        try:
            # finds the index for a given title
            movie_index = item_pred_df.index.tolist().index(title)
            # retrieves the rating for a given movie index and user
            user_rating = item_pred_df.iloc[movie_index, user]
            # adds both the rating and title of the movie to the movie_ratings list.
            movie_ratings.append((title, user_rating))
        except ValueError:
            # if the title is not found in the dataframe then we continue onto the next movie title.
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    # This allows us to output the top 3 rated movies in our list.
    top_movies = movie_ratings_sorted[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}: {movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


# Recommends movies based of a given phrase for a given user.
def recommend_movies_based_on_tags(phrase, user):
    # initialising spacy model, this model has word vectors included.
    nlp = spacy.load("en_core_web_lg")

    # retrieves  all the titles, movieId and tags
    movie_and_tags = pd.read_sql(
        f"select m.title, t.movieId, t.tag from tags as t inner join movies as m on t.movieId = m.movieId;", con=mydb)

    # creating a list of titles
    tags_list = movie_and_tags['tag'].tolist()

    # This list holds all the tags and the associated similarity scores between the given phrase.
    tag_comparison_values = []

    # iterates through the list of tags and measures the comparison between each tag and the provided phrase.
    for tag in tags_list:
        similarity_score = nlp(phrase).similarity(nlp(tag))
        tag_comparison_values.append((tag, similarity_score))

    # Sort the list of movie ratings by user rating in descending order
    tag_ratings_sorted = sorted(tag_comparison_values, key=lambda x: x[1], reverse=True)

    # extracts only the tags most associated with our given phrase.
    highly_related_tags = [tag for tag in tag_ratings_sorted if tag[1] >= 0.5]

    # creates an empty set to store unique movie titles.
    movie_titles = set()

    # This iterates through each tag and retrieves the money for each associated tag.
    for tag in highly_related_tags:
        titles = movie_and_tags[movie_and_tags['tag'] == tag[0]]
        list_of_titles = titles['title'].tolist()
        movie_titles.update(list_of_titles)
        list_of_titles.clear()

    # changes the set movies_titles into a list.
    movie_titles_list = list(movie_titles)

    # a list for all the movies the user has watched.
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    movie_titles_list = [title for title in movie_titles_list if title not in seen_movies]

    # A list to hold the ratings of each title and associated user
    movie_ratings = []

    for title in movie_titles_list:
        try:
            # finds the index for a given title
            movie_index = item_pred_df.index.tolist().index(title)
            # retrieves the rating for a given movie index and user
            user_rating = item_pred_df.iloc[movie_index, user]
            # adds both the rating and title of the movie to the movie_ratings list.
            movie_ratings.append((title, user_rating))
        except ValueError:
            # if the title is not found in the dataframe then we continue onto the next movie title.
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    # This allows us to output the top 5 rated movies in our list.
    top_movies = movie_ratings_sorted[:5]
    rank = 1
    for movie in top_movies:
        print(f'{rank}: {movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


# recommend movies based of the year and genre
def recommend_movies_based_on_year_and_genre(year, genre, user):
    # retrieves all the titles for a given genre and year.
    sql_query = pd.read_sql(
        f"select m.title from movies as m inner join movie_genre as mg on m.movieId = mg.movieId Inner join "
        f"genres as g on mg.genre_id = g.genre_id where g.name like '%{genre}%' and year = {year}", con=mydb)

    # creating a list of titles
    movie_titles = sql_query['title'].tolist()

    # Remove the movies that the user has already seen
    seen_movies = ratings_pivot_table.loc[user][ratings_pivot_table.loc[user] > 0].index.tolist()
    movie_titles_list = [title for title in movie_titles if title not in seen_movies]

    # A list to hold the ratings of each title and associated user
    movie_ratings = []

    for title in movie_titles_list:
        try:
            # finds the index for a given title
            movie_index = item_pred_df.index.tolist().index(title)
            # retrieves the rating for a given movie index and user
            user_rating = item_pred_df.iloc[movie_index, user]
            # adds both the rating and title of the movie to the movie_ratings list.
            movie_ratings.append((title, user_rating))
        except ValueError:
            # if the title is not found in the dataframe then we continue onto the next movie title.
            print(f'{title} has not been found --- for testing purposes')
            continue

    # Sort the list of movie ratings by user rating in descending order
    movie_ratings_sorted = sorted(movie_ratings, key=lambda x: x[1], reverse=True)

    # This allows us to output the top 3 rated movies in our list.
    top_movies = movie_ratings_sorted[:3]
    rank = 1
    for movie in top_movies:
        print(f'{rank}:{movie[0]}')
        rank = rank + 1

    print(f'{top_movies}, only showing for testing purposes')


# # recommend_movies_based_on_year_and_genre(1990, 'act', 1)
# recommend_movies_based_on_tags('football', 3)
# recommend_movie_based_on_genre('action', 373)
# recommend_movies_based_on_year(1990, 1)
# recommend_movie_based_on_similar_title("hug", 5)
# recommend_movies_based_on_user(2, 3)
