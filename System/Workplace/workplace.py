from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
import numpy as np
import mysql.connector
import pandas as pd

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)

movies_df = pd.read_csv('C:/Users/Joseph/PycharmProjects/MovieRecommendationSystem/movies.csv',
                        usecols=["movieId", "title"])

ratings_df = pd.read_csv('C:/Users/Joseph/PycharmProjects/MovieRecommendationSystem/ratings.csv',
                         usecols=["userId", "movieId", "rating"])

merged_df = pd.merge(movies_df, ratings_df, on='movieId')

merged_df_pivot = pd.pivot_table(merged_df, values='rating', index=['userId'], columns=['title'])

item_user_ratings_df = pd.read_sql('SELECT m.title,u.userId,r.ratings FROM movies as m JOIN ratings as r ON '
                                   'm.movieId '
                                   '= r.movieId JOIN users as u ON r.userId = u.userId;', con=mydb)

ratings_table = pd.pivot_table(item_user_ratings_df, values='ratings', index=['userId'], columns=['title'])

# calculating the sparsity of this data
number_of_empty = ratings_table.isnull().values.sum()
total_number = ratings_table.size
sparsity = number_of_empty / total_number
print(f'The sparsity of this data set is {sparsity * 100}%, this percentage represents how sparse our dataset is.')

# Matrix factorisation
# Normalising our data (centring our data by deducting the row average from each row
avg_ratings = ratings_table.mean(axis=1)
# we create a pivot table for the centred data and subtracted the mean from the matrix on a row-level.
ratings_pivot_centred = ratings_table.sub(avg_ratings, axis=0)
# We then fill in the missing values with 0,making sure our ratings are not affected.
ratings_pivot_centred.fillna(0, inplace=True)
# create sparse matrix
ratings_pivot_sparse = csr_matrix(ratings_pivot_centred.values)
# decompose the matrix
U, sigma, Vt = svds(ratings_pivot_sparse.toarray(), k=200)
# convert the sigma into a diagonal matrix
sigma = np.diag(sigma)
# calculated the product of U and sigma
# allows us to get the full utility matrix
pred = np.dot(np.dot(U, sigma), Vt)
# finding the full utility matrix
# add averages back
pred = pred + avg_ratings.values.reshape(-1, 1)

# Create DataFrame of the results
pred_df = pd.DataFrame(pred, columns=ratings_table.columns, index=ratings_table.index)

# example to show user 5 highest rated films
user_5_ratings = pred_df.loc[1, :].sort_values(ascending=False)

# Validate our predictions
# create a hold-out set, the hold out set will contain the first 40 rows and 200 columns
actual_values = ratings_table.iloc[:40, :200].values
# we blank out the area in the original data with nan's
ratings_table.iloc[:40, 100:] = np.nan

# we perform retrieve the hold out set values from our predicted data
pred_values = pred_df.iloc[:40, :200].values

# Mask the values, so we can only compare with ratings that did exist
mask = ~np.isnan(actual_values)

# calculating rmse
print(mean_squared_error(actual_values[mask], pred_values[mask], squared=False))
