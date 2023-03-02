from chatterbot.logic import LogicAdapter
from System.RecommendationEngine.recommendationEngine import recommend_movies_based_on_year, \
    recommend_movies_based_on_tags, recommend_movies_based_on_year_and_genre, recommend_movies_based_on_user, \
    recommend_movie_based_on_similar_title, recommend_movie_based_on_genre
from chatterbot.conversation import Statement
from flask_login import current_user


class RecommendMoviesAdapter(LogicAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def can_process(self, statement):
        # Check if the user's statement includes a year
        if 'year' in statement.text.lower():
            return True
        else:
            return False

    def process(self, statement, additional_response_selection_parameters=None):
        # Extract the year from the user's statement
        year = None
        for word in statement.text.split():
            if word.isdigit():
                year = int(word)
                break

        # If a valid year was found, recommend movies
        if year:
            recommended_movies = recommend_movies_based_on_year(year, user=current_user.get_id())

            # Construct a response string listing the recommended movies
            response = f"Here are the top movies from {year}:"
            for rank, movie in enumerate(recommended_movies, start=1):
                response += f"\n{rank}. {movie[0]}"

            return self.process_response(statement, response)
        else:
            return self.process_response(statement, "I'm sorry, I didn't understand which year you were asking about.")

    def process_response(self, statement, response):
        """
        This method takes in a statement and a response and returns a response object.
        """
        response_statement = Statement(response)
        response_statement.confidence = 1.0
        return response_statement
