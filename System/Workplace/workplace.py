from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
import numpy as np
import mysql.connector
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.model_selection import train_test_split

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)


def create_ratings_table(mydb):
    item_user_ratings_df = pd.read_sql('SELECT m.title, u.userId, r.ratings FROM movies as m JOIN ratings as r ON '
                                       'm.movieId '
                                       '= r.movieId JOIN users as u ON r.userId = u.userId;', con=mydb)
    return pd.pivot_table(item_user_ratings_df, values='ratings', index=['userId'], columns=['title'])


def normalize_data(df):
    avg_ratings = df.mean(axis=1)
    df_centred = df.sub(avg_ratings, axis=0)
    df_centred.fillna(0, inplace=True)
    return df_centred, avg_ratings


def decompose_matrix(sparse_matrix, k=10):
    U, sigma, Vt = svds(sparse_matrix.toarray(), k=k)
    sigma = np.diag(sigma)
    return U, sigma, Vt


def calculate_predicted_matrix(U, sigma, Vt, avg_ratings):
    pred_matrix = np.dot(np.dot(U, sigma), Vt)
    pred_matrix = pred_matrix + avg_ratings.values.reshape(-1, 1)
    return pred_matrix


def create_pred_df(pred_matrix, ratings_table, index):
    return pd.DataFrame(pred_matrix, columns=ratings_table.columns, index=index)


def cross_validate(ratings_table, n_splits=10, k=10, random_state=1):
    kfold = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    mse_values = []

    for train, val in kfold.split(ratings_table):
        ratings_train = ratings_table.iloc[train]
        ratings_val = ratings_table.iloc[val]

        ratings_train_centred, avg_ratings_train = normalize_data(ratings_train)
        ratings_val_centred, avg_ratings_val = normalize_data(ratings_val)

        ratings_train_sparse = csr_matrix(ratings_train_centred.values)
        ratings_val_sparse = csr_matrix(ratings_val_centred.values)

        U, sigma, Vt = decompose_matrix(ratings_train_sparse, k=k)

        pred_val = calculate_predicted_matrix(U, sigma, Vt, avg_ratings_train)

        mse = mean_squared_error(ratings_val_sparse.data, pred_val[ratings_val_sparse.nonzero()])
        mse_values.append(mse)

    mean_mse = np.mean(mse_values)
    return mean_mse


def evaluate_model(ratings_table, test_size=0.2, random_state=1, k=10):
    X_train, X_test = train_test_split(ratings_table, test_size=test_size, random_state=random_state)

    X_train_centred, avg_ratings_train = normalize_data(X_train)
    X_test_centred, avg_ratings_test = normalize_data(X_test)

    ratings_train_sparse = csr_matrix(X_train_centred.values)
    ratings_test_sparse = csr_matrix(X_test_centred.values)

    U, sigma, Vt = decompose_matrix(ratings_train_sparse, k=k)

    pred_val = calculate_predicted_matrix(U, sigma, Vt, avg_ratings_train)

    mse_test = mean_squared_error(ratings_test_sparse.data, pred_val[ratings_test_sparse.nonzero()])

    return pred_val, X_train.index, mse_test

# ratings_table = create_ratings_table(mydb)
#
# mean_mse = cross_validate(ratings_table)
# print(f"Mean MSE over 10-fold cross validation: {mean_mse:.4f}")
#
# pred_val, user_index, mse_test = evaluate_model(ratings_table)
# pred_df = create_pred_df(pred_val, ratings_table, user_index)
# print(pred_df)
