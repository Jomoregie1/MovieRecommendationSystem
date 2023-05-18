import unittest
from unittest.mock import MagicMock, patch, Mock
from chatterbot.conversation import Statement
from System.Chatbot.logicadapter import BridgeLogicAdapter, UserConversationLogicAdapter, \
    RecommendMoviesBasedOnTagAdapter, RecommendMovieBasedOnGenreAdapter


class TestBridgeLogicAdapter(unittest.TestCase):

    def setUp(self):
        self.chatbot_mock = MagicMock()
        self.logic_adapter = BridgeLogicAdapter(self.chatbot_mock)

    def test_can_process(self):
        # Mock the required methods
        self.logic_adapter.get_recommendation_engine_function = MagicMock()
        self.logic_adapter.get_recommendation_engine_function.return_value = lambda x: 11  # More than 10 movies rated

        # Mock the statement
        statement = Statement("0")

        # Test the method
        can_process = self.logic_adapter.can_process(statement)

        # Assert the result
        self.assertTrue(can_process)

    def test_process(self):
        # Mock the required methods
        self.logic_adapter.get_recommendation_engine_function = MagicMock()
        self.logic_adapter.get_recommendation_engine_function.return_value = lambda x: 11  # More than 10 movies rated
        self.logic_adapter.reset_meta_data = MagicMock()
        self.logic_adapter.reset_meta_data.return_value = {"completed_initial_rating": False}
        self.logic_adapter.update_metadata_and_conversation = MagicMock()

        # Mock the statement
        statement = Statement("1")

        # Test the method
        result = self.logic_adapter.process(statement)

        # Assert the result
        self.assertEqual(result.text, "Congratulations! You have rated 11 movies. "
                                      "I now have a better understanding of your preferences.")
        self.assertEqual(result.confidence, 1.0)


class TestUserConversationLogicAdapter(unittest.TestCase):

    def setUp(self):
        self.chatbot_mock = MagicMock()
        self.logic_adapter = UserConversationLogicAdapter(self.chatbot_mock)

    def test_can_process(self):
        # Mock the required methods
        self.logic_adapter.get_recommendation_engine_function = MagicMock()
        self.logic_adapter.get_recommendation_engine_function.return_value = lambda x: 9  # Less than 10 movies rated

        # Set user_id
        self.logic_adapter.set_user_id("test_user")

        # Mock the statement
        statement = Statement("0")

        # Test the method
        can_process = self.logic_adapter.can_process(statement)

        # Assert the result
        self.assertTrue(can_process)

    @patch('System.Chatbot.logicadapter.UserConversationLogicAdapter.update_user_conversation_meta')
    @patch('System.Chatbot.logicadapter.UserConversationLogicAdapter.generate_next_movie_recommendation')
    @patch('System.Chatbot.logicadapter.UserConversationLogicAdapter.update_meta_based_on_user_input')
    @patch('System.Chatbot.logicadapter.UserConversationLogicAdapter.initialize_meta')
    def test_process(self, mock_initialize_meta, mock_update_meta, mock_generate_next_movie_recommendation,
                     mock_update_user_conversation_meta):
        # Mock the required methods
        self.logic_adapter.get_recommendation_engine_function = MagicMock()
        self.logic_adapter.get_recommendation_engine_function.return_value = lambda x: 9  # Less than 10 movies rated
        mock_initialize_meta.return_value = {"completed_initial_rating": False}
        mock_update_meta.return_value = (mock_initialize_meta.return_value, False)
        mock_generate_next_movie_recommendation.return_value = "Have you watched movie1? If yes, please rate it from " \
                                                               "1 to 5. If you haven't seen it, reply 'no'. "

        # Mock the statement
        statement = Statement("1")

        # Test the method
        result = self.logic_adapter.process(statement)

        # Assert the result
        self.assertEqual(result.text.strip(), "Have you watched movie1? If yes, please rate it from 1 to 5. If you "
                                              "haven't seen it, reply 'no'.")
        self.assertEqual(result.confidence, 1.0)


class TestRecommendMoviesBasedOnTagAdapter(unittest.TestCase):

    def setUp(self):
        self.chatbot = Mock()
        self.chatbot.search_algorithms = MagicMock()
        self.chatbot.logic_adapters = []
        self.adapter = RecommendMoviesBasedOnTagAdapter(self.chatbot)

    def test_can_process(self):
        # Patch the recommendation engine function to control its output
        with patch.object(self.adapter, 'get_recommendation_engine_function', return_value=Mock(return_value=10)):
            statement = Statement(text="2")
            self.adapter.set_user_id('test_user')
            self.adapter.active = False
            self.assertTrue(self.adapter.can_process(statement))

    def test_process(self):
        # Mock the required functions
        store_rating_mock = Mock(return_value=True)
        recommend_movies_mock = Mock(return_value=[(1, 'Movie 1'), (2, 'Movie 2')])

        # Patch the recommendation engine function to control its output
        with patch.object(self.adapter, 'get_recommendation_engine_function',
                          side_effect=[store_rating_mock, recommend_movies_mock]):
            statement = Statement(text="4")
            self.adapter.set_user_id('test_user')
            self.adapter.active = True
            self.adapter.first_interaction = False
            self.adapter.initialize_meta = Mock(return_value={
                'movies_on_tag_meta': {'recommended_movies_list': [(1, 'Movie 1')], 'movies_list': [],
                                       'shown_movie': []}})
            self.adapter.update_user_conversation_meta = Mock()

            response = self.adapter.process(statement)
            self.assertEqual(response.text, "Great, thank you for your rating. Really glad you enjoyed the movie! "
                                            "I'll be sure to keep up the good work. 😊 ")
            self.assertEqual(response.confidence, 1.0)

    def test_reset(self):
        self.adapter.set_user_id('test_user')
        self.adapter.isPromptMessage = False
        self.adapter.active = True
        self.adapter.first_interaction = False
        self.adapter.initialize_meta = Mock(return_value={
            'movies_on_tag_meta': {'movies_list': [(1, 'Movie 1')], 'current_movie_index': 0,
                                   'shown_movie': [(1, 'Movie 1')], 'recommended_movies_list': [(1, 'Movie 1')]}})
        self.adapter.update_user_conversation_meta = Mock()
        self.adapter.reset()
        self.assertTrue(self.adapter.isPromptMessage)
        self.assertFalse(self.adapter.active)
        self.assertTrue(self.adapter.first_interaction)


class TestRecommendMovieBasedOnGenreAdapter(unittest.TestCase):
    def setUp(self):
        self.chatbot_mock = MagicMock()
        self.adapter = RecommendMovieBasedOnGenreAdapter(self.chatbot_mock)

    @patch('System.RecommendationEngine.recommendationEngine.count_rated_movies_for_user', return_value=15)
    def test_can_process(self, mock_count_rated_movies_for_user):
        # Setup
        self.adapter.set_user_id(1)
        statement = Statement('3')

        # Call the method
        result = self.adapter.can_process(statement)

        # Check the results
        self.assertTrue(result)
        self.assertTrue(self.adapter.is_active)

    @patch('System.RecommendationEngine.recommendationEngine.count_rated_movies_for_user', return_value=5)
    def test_can_process_not_enough_rated_movies(self, mock_count_rated_movies_for_user):
        # Setup
        self.adapter.set_user_id(1)
        statement = Statement('3')

        # Call the method
        result = self.adapter.can_process(statement)

        # Check the results
        self.assertFalse(result)
        self.assertFalse(self.adapter.is_active)

    @patch('System.RecommendationEngine.recommendationEngine.recommend_movies_based_on_genre',
           return_value=[(1, 'Test movie')])
    @patch('System.RecommendationEngine.recommendationEngine.list_of_genres',
           return_value=['action'])
    @patch('System.Chatbot.logicadapter.RecommendMovieBasedOnGenreAdapter.initialize_meta',
           return_value={"similar_genre_meta": {"recommended_movies_list": []}})
    def test_process(self, mock_initialize_meta, mock_list_of_genres, mock_recommend_movies_based_on_genre):
        # Setup
        self.adapter.set_user_id(1)
        statement = Statement('action')

        # Call the method
        response = self.adapter.process(statement)

        # Check the results
        self.assertEqual(response.text.strip(),
                         "Please enter one of the following genres (Adventure, Comedy, Action, Drama, Crime, "
                         "Children, Mystery, Animation, Documentary, Thriller, Horror, Fantasy, Western, Film-Noir, "
                         "Romance, Sci-Fi, Musical, War, IMAX) and I'll be able to suggest some movies I think you "
                         "might enjoy that were made in that genre")
        self.assertEqual(response.confidence, 1.0)
        self.assertFalse(self.adapter.is_active)


if __name__ == "__main__":
    unittest.main()
