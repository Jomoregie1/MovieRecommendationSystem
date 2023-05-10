import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from System.RecommendationEngine.recommendationEngine import recommend_movies_based_on_year_and_genre, \
    recommend_movies_to_rate_for_new_users, recommend_movies_based_on_year, recommend_movies_based_on_tags, \
    recommend_movies_based_on_title, recommend_movies_based_on_genre, recommend_movies_based_on_user


class TestMovieRecommendationSystem(unittest.TestCase):

    def test_recommend_movies_based_on_year_and_genre(self):
        # Mock the required functions and data
        with patch(
                "System.RecommendationEngine.recommendationEngine.fetch_predicted_ratings") as fetch_predicted_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.fetch_user_ratings") as fetch_user_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_unseen_movies") as get_unseen_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_similar_users") as get_similar_users_mock, \
                patch(
                    "System.RecommendationEngine.recommendationEngine.get_unique_movie_list") as get_unique_movie_list_mock:
            # Set return values for the mocked functions
            fetch_predicted_ratings_mock.return_value = pd.DataFrame(index=[2, 3, 4], columns=["Movie B", "Movie C"])
            fetch_user_ratings_mock.return_value = []
            get_rated_movies_mock.return_value = [("1", "Movie A")]
            get_unseen_movies_mock.return_value = ["Movie B", "Movie C"]
            get_similar_users_mock.return_value = [2, 3, 4]
            get_unique_movie_list_mock.return_value = [("2", "Movie B"), ("3", "Movie C")]

            # Test the function
            result = recommend_movies_based_on_year_and_genre(2020, "Action", 1)

            # Check if the result is as expected
            self.assertEqual(result, [("2", "Movie B"), ("3", "Movie C")])

    def test_recommend_movies_to_rate_for_new_users(self):
        # Mock the required functions
        with patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.popular_movies_df") as popular_movies_df_mock:
            # Set return values for the mocked functions
            get_rated_movies_mock.return_value = [("1", "Movie A")]
            popular_movies_df_mock.return_value = ["Movie A", "Movie B", "Movie C"]

            # Test the function
            result = recommend_movies_to_rate_for_new_users(1)

            # Check if the result is as expected
            self.assertEqual(set(result), {"Movie B", "Movie C", "Movie A"})

    def test_recommend_movies_based_on_year(self):
        with patch(
                "System.RecommendationEngine.recommendationEngine.fetch_predicted_ratings") as fetch_predicted_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.fetch_user_ratings") as fetch_user_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_similar_users") as get_similar_users_mock, \
                patch(
                    "System.RecommendationEngine.recommendationEngine.get_unique_movie_list") as get_unique_movie_list_mock:
            fetch_predicted_ratings_mock.return_value = pd.DataFrame(index=[2, 3, 4], columns=["Movie A", "Movie B"])
            fetch_user_ratings_mock.return_value = []
            get_rated_movies_mock.return_value = [("1", "Movie A")]
            get_similar_users_mock.return_value = [2, 3, 4]
            get_unique_movie_list_mock.return_value = [("2", "Movie B")]

            result = recommend_movies_based_on_year(2020, 1)

            self.assertEqual(result, [("2", "Movie B")])

    def test_recommend_movies_based_on_tags(self):
        with patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.nlp") as nlp_mock, \
                patch("System.RecommendationEngine.recommendationEngine.extract_keyword") as extract_keyword_mock:
            get_rated_movies_mock.return_value = []
            nlp_mock.return_value = MagicMock()
            nlp_mock.return_value.similarity.side_effect = [0.8, 0.4, 0.3]
            extract_keyword_mock.side_effect = ["action", "comedy", "drama"]

            movies_and_tags = pd.DataFrame([
                {"title": "Movie A", "movieId": "1", "tag": "action", "description": "Action movie"},
                {"title": "Movie B", "movieId": "2", "tag": "comedy", "description": "Comedy movie"},
                {"title": "Movie C", "movieId": "3", "tag": "drama", "description": "Drama movie"},
            ])

            with patch("System.RecommendationEngine.recommendationEngine.engine.connect") as connect_mock:
                connect_mock().__enter__().execute().fetchall.return_value = movies_and_tags.to_records(index=False)
                result = recommend_movies_based_on_tags("action", 1)

            self.assertEqual(result, [('1', 'Movie A')])

    def test_recommend_movies_based_on_title(self):
        with patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch(
                    "System.RecommendationEngine.recommendationEngine.compute_similarity_matrices") as compute_similarity_matrices_mock:
            get_rated_movies_mock.return_value = [("1", "Movie A")]
            compute_similarity_matrices_mock.return_value = (pd.DataFrame([
                {"title": "Movie A", "movieId": "1"},
                {"title": "Movie B", "movieId": "2"},
                {"title": "Movie C", "movieId": "3"},
            ]), np.array([[1, 0.8, 0.5], [0.8, 1, 0.4], [0.5, 0.4, 1]]))

            result = recommend_movies_based_on_title("Movie A", 1)
            self.assertEqual(result, [("2", "Movie B"), ("3", "Movie C")])

    def test_recommend_movies_based_on_user(self):
        # Mock the required functions and data
        with patch(
                "System.RecommendationEngine.recommendationEngine.fetch_predicted_ratings_cache") as fetch_predicted_ratings_cache_mock, \
                patch(
                    "System.RecommendationEngine.recommendationEngine.fetch_user_ratings_cache") as fetch_user_ratings_cache_mock, \
                patch("System.RecommendationEngine.recommendationEngine.find_similar_users") as find_similar_users_mock, \
                patch(
                    "System.RecommendationEngine.recommendationEngine.fetch_top_rated_movies") as fetch_top_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock:
            user_id = 1
            seen_movies = [(1, "Seen Movie 1"), (2, "Seen Movie 2")]
            top_rated_movies = [(3, "Top Rated Movie 1"), (4, "Top Rated Movie 2"), (5, "Top Rated Movie 3")]

            # Set return values for the mocked functions
            fetch_predicted_ratings_cache_mock.return_value = pd.DataFrame(columns=["Movie 1", "Movie 2", "Movie 3"])
            fetch_user_ratings_cache_mock.return_value = {}
            find_similar_users_mock.return_value = [2, 3, 4]
            fetch_top_rated_movies_mock.return_value = top_rated_movies
            get_rated_movies_mock.return_value = seen_movies

            # Test the function
            result = recommend_movies_based_on_user(user_id)

            # Check that none of the recommended movies have been seen by the user
            for movie_id, title in result:
                self.assertNotIn((movie_id, title), seen_movies)

    def test_recommend_movies_based_on_genre(self):
        # Mock the required functions and objects
        with patch(
                "System.RecommendationEngine.recommendationEngine.fetch_predicted_ratings") as fetch_predicted_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.fetch_user_ratings") as fetch_user_ratings_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_rated_movies") as get_rated_movies_mock, \
                patch("System.RecommendationEngine.recommendationEngine.get_similar_users") as get_similar_users_mock, \
                patch("System.RecommendationEngine.recommendationEngine.engine.connect") as connect_mock:
            # Set return values for the mocked functions
            fetch_predicted_ratings_mock.return_value = pd.DataFrame(index=[2, 3, 4], columns=["1", "2", "3"])
            fetch_user_ratings_mock.return_value = pd.DataFrame({1: [0], 2: [0], 3: [0]}, index=[1])
            get_rated_movies_mock.return_value = [("1", "Seen Movie 1")]
            get_similar_users_mock.return_value = [2, 3, 4]

            # Mock the engine and connection objects
            connection_mock = MagicMock()
            connect_mock.return_value.__enter__.return_value = connection_mock
            connection_mock.execute.return_value.fetchall.return_value = [("Movie 2", "2"), ("Movie 3", "3")]

            # Test the function
            genre = "Action"
            user = 1
            result = recommend_movies_based_on_genre(genre, user)

            # Check if the result is as expected
            self.assertEqual(result, [("2", "Movie 2"), ("3", "Movie 3")])


if __name__ == '__main__':
    unittest.main()
