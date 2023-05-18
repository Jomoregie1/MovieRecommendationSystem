from collections import defaultdict
from matplotlib import pyplot as plt
from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.model_selection import train_test_split
from System.database import connect_db

mydb = connect_db()


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

    return mse_values


def evaluate_model(ratings_table, test_size=0.2, random_state=1, k=10):
    X_train, X_test = train_test_split(ratings_table, test_size=test_size, random_state=random_state)

    X_train_centred, avg_ratings_train = normalize_data(X_train)
    X_test_centred, avg_ratings_test = normalize_data(X_test)

    ratings_train_sparse = csr_matrix(X_train_centred.values)
    ratings_test_sparse = csr_matrix(X_test_centred.values)

    U, sigma, Vt = decompose_matrix(ratings_train_sparse, k=k)

    pred_val = calculate_predicted_matrix(U, sigma, Vt, avg_ratings_train)

    mse_test = mean_squared_error(ratings_test_sparse.data, pred_val[ratings_test_sparse.nonzero()])

    return pred_val, X_train, X_test, mse_test


def plot_rating_distribution(ratings_table):
    rounded_ratings = np.round(ratings_table.values.flatten())
    plt.figure(figsize=(10, 5))
    plt.hist(rounded_ratings, bins=np.arange(0.5, 6.5, 1), alpha=0.7, color='b', edgecolor='black')
    plt.xticks(range(1, 6))
    plt.xlabel('Rating')
    plt.ylabel('Frequency')
    plt.title('Distribution of Ratings')
    plt.show()


def plot_mse(mse_values, mse_test):
    plt.figure(figsize=(10, 5))

    # plot MSE for each fold in cross-validation
    plt.bar(range(1, len(mse_values) + 1), mse_values, color='blue', label='Cross-validation MSE')

    # plot MSE for test set
    plt.axhline(y=mse_test, color='red', linestyle='-', label='Test MSE')

    plt.xlabel('Fold')
    plt.ylabel('MSE')
    plt.legend()
    plt.title('Model MSE across folds and on test set')
    plt.show()


def plot_matrix_sparsity(ratings_table):
    plt.figure(figsize=(10, 5))
    plt.spy(ratings_table)
    plt.xlabel('Movies')
    plt.ylabel('Users')
    plt.title('Matrix Sparsity')
    plt.show()


def plot_mse_vs_factors(ratings_table, max_k=50):
    k_values = range(1, max_k + 1)
    mse_values = []
    for k in k_values:
        mse_k = cross_validate(ratings_table, k=k)
        mse_values.append(np.mean(mse_k))
    plt.figure(figsize=(10, 5))
    plt.plot(k_values, mse_values, marker='o', linestyle='-')
    plt.xlabel('Number of Latent Factors (k)')
    plt.ylabel('Mean MSE')
    plt.title('MSE vs. Number of Latent Factors')
    plt.show()


def precision_recall_at_k(predictions, k=10, threshold=3.5):
    '''Return precision and recall at k metrics for each user.'''

    # First map the predictions to each user.
    user_est_true = defaultdict(list)
    for uid, _, true_r, est in predictions:
        user_est_true[uid].append((est, true_r))

    precisions = dict()
    recalls = dict()
    for uid, user_ratings in user_est_true.items():
        # Sort user ratings by estimated value
        user_ratings.sort(key=lambda x: x[0], reverse=True)

        # Number of relevant items
        n_rel = sum((true_r >= threshold) for (_, true_r) in user_ratings)

        # Number of recommended items in top k
        n_rec_k = sum((est >= threshold) for (est, _) in user_ratings[:k])

        # Number of relevant and recommended items in top k
        n_rel_and_rec_k = sum(((true_r >= threshold) and (est >= threshold))
                              for (est, true_r) in user_ratings[:k])

        # Precision@K: Proportion of recommended items that are relevant
        precisions[uid] = n_rel_and_rec_k / n_rec_k if n_rec_k != 0 else 1

        # Recall@K: Proportion of relevant items that are recommended
        recalls[uid] = n_rel_and_rec_k / n_rel if n_rel != 0 else 1

    return precisions, recalls


def plot_precision_recall_curve(precision_list, recall_list, k_list):
    plt.figure(figsize=(8, 6))
    plt.plot(k_list, precision_list, label='Precision', marker='o')
    plt.plot(k_list, recall_list, label='Recall', marker='o')
    plt.xlabel('Number of Recommendations (k)')
    plt.ylabel('Score')
    plt.title('Precision-Recall Curve')
    plt.legend()
    plt.grid()
    plt.show()


def generate_predictions(ratings_table, pred_val):
    predictions = []
    for i in range(len(ratings_table)):
        for j in range(len(ratings_table.columns)):
            if ratings_table.iloc[i, j] != 0:
                uid = ratings_table.index[i]
                iid = ratings_table.columns[j]
                true_r = ratings_table.iloc[i, j]
                est = pred_val[i, j]
                predictions.append((uid, iid, true_r, est))
    return predictions


if __name__ == '__main__':
    ratings_table = create_ratings_table(mydb)
    mse_values = cross_validate(ratings_table, n_splits=10, k=10, random_state=1)
    pred_val, X_train, X_test, mse_test = evaluate_model(ratings_table, test_size=0.2, random_state=1, k=10)

    plot_mse(mse_values, mse_test)
    plot_rating_distribution(ratings_table)
    plot_matrix_sparsity(ratings_table)
    plot_mse_vs_factors(ratings_table)

    k_values = range(1, 51)  # Test with k from 1 to 50
    precision_list = []
    recall_list = []

    predictions = generate_predictions(X_train, pred_val)

    for k in k_values:
        precisions, recalls = precision_recall_at_k(predictions, k=k)
        precision_k = np.mean(list(precisions.values()))
        recall_k = np.mean(list(recalls.values()))
        precision_list.append(precision_k)
        recall_list.append(recall_k)

    plot_precision_recall_curve(precision_list, recall_list, k_values)
