from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
import numpy as np
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
import spacy
from sklearn.model_selection import KFold
from sklearn.model_selection import train_test_split

# # initialising spacy model, this model has word vectors included.
# nlp = spacy.load('en_core_web_lg')

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)

item_user_ratings_df = pd.read_sql('SELECT m.title,u.userId,r.ratings FROM movies as m JOIN ratings as r ON '
                                   'm.movieId '
                                   '= r.movieId JOIN users as u ON r.userId = u.userId;', con=mydb)

ratings_table = pd.pivot_table(item_user_ratings_df, values='ratings', index=['userId'], columns=['title'])

# Matrix factorisation
# Normalising our data (centring our data by deducting the row average from each row)
avg_ratings = ratings_table.mean(axis=1)
# we create a pivot table for the centred data and subtracted the mean from the matrix on a row-level.
ratings_pivot_centred = ratings_table.sub(avg_ratings, axis=0)
# We then fill in the missing values with 0,making sure our ratings are not affected.
ratings_pivot_centred.fillna(0, inplace=True)
# create sparse matrix
ratings_train_sparse = csr_matrix(ratings_pivot_centred.values)
# decompose the matrix
U, sigma, Vt = svds(ratings_train_sparse.toarray(), k=10)
# convert the sigma into a diagonal matrix
sigma = np.diag(sigma)
# calculate the product of U and sigma
# allows us to get the full utility matrix
pred_train = np.dot(np.dot(U, sigma), Vt)
# finding the full utility matrix
# add averages back
pred_train = pred_train + avg_ratings.values.reshape(-1, 1)

# create a dataframe for the predicted matrix
pred_df = pd.DataFrame(pred_train, columns=ratings_table.columns, index=ratings_table.index)







# Cross validation
kfold = KFold(n_splits=10, shuffle=True, random_state=1)
mse_values = []
for train, val in kfold.split(ratings_table):
    # Create train and validation sets
    ratings_train = ratings_table.iloc[train]
    ratings_val = ratings_table.iloc[val]

    # Normalise data
    avg_ratings_train = ratings_train.mean(axis=1)
    ratings_train_centred = ratings_train.sub(avg_ratings_train, axis=0)
    ratings_train_centred.fillna(0, inplace=True)

    avg_ratings_val = ratings_val.mean(axis=1)
    ratings_val_centred = ratings_val.sub(avg_ratings_val, axis=0)
    ratings_val_centred.fillna(0, inplace=True)

    # Convert to sparse matrices
    ratings_train_sparse = csr_matrix(ratings_train_centred.values)
    ratings_val_sparse = csr_matrix(ratings_val_centred.values)

    # Decompose the train matrix
    U, sigma, Vt = svds(ratings_train_sparse.toarray(), k=10)
    sigma = np.diag(sigma)

    # Calculate the predicted ratings
    pred_val = np.dot(np.dot(U, sigma), Vt)
    pred_val = pred_val + avg_ratings_train.values.reshape(-1, 1)

    # Calculate the MSE for the validation set
    mse = mean_squared_error(ratings_val_sparse.data, pred_val[ratings_val_sparse.nonzero()])
    mse_values.append(mse)

# Calculate the mean MSE over all folds
mean_mse = np.mean(mse_values)
print(f"Mean MSE over 10-fold cross validation: {mean_mse:.4f}")

# Split data into training and test sets
X_train, X_test = train_test_split(ratings_table, test_size=0.2, random_state=1)

# Normalise data
avg_ratings_train = X_train.mean(axis=1)
X_train_centred = X_train.sub(avg_ratings_train, axis=0)
X_train_centred.fillna(0, inplace=True)

avg_ratings_test = X_test.mean(axis=1)
X_test_centred = X_test.sub(avg_ratings_test, axis=0)
X_test_centred.fillna(0, inplace=True)

# Convert to sparse matrices
ratings_train_sparse = csr_matrix(X_train_centred.values)
ratings_test_sparse = csr_matrix(X_test_centred.values)

# Decompose the train matrix
U, sigma, Vt = svds(ratings_train_sparse.toarray(), k=10)
sigma = np.diag(sigma)

# Calculate the predicted ratings
pred_val = np.dot(np.dot(U, sigma), Vt)
pred_val = pred_val + avg_ratings_train.values.reshape(-1, 1)
