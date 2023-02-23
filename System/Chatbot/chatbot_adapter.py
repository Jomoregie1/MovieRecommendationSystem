from chatterbot.logic import LogicAdapter
from chatterbot.conversation import Statement


class RecommendByTagsAdapter(LogicAdapter):
    def can_process(self, statement):
        # Always return True
        return True

    def process(self, statement, additional_response_selection_parameters=None):
        # Ask the user for a movie description
        response = Statement("What is one phrase you would use to describe a movie?")

        # Get the user's response
        user_input = statement.text.strip()

        # Check the length of the user's input
        if len(user_input) > 15:
            response = Statement(
                "Sorry, your description is too long. Please enter a shorter phrase with 15 characters or less.")
        else:
            response = Statement(f"Thanks for your description: {user_input}")

        return response


# Define a custom logic adapter to prompt the user for movie preferences
class RecommendationByYearAndGenreAdapter(LogicAdapter):
    def can_process(self, statement):
        return True

    def process(self, statement, additional_response_selection_parameters=None):
        # Prompt the user for movie preferences
        response = Statement("What year and genre are you interested in?")
        return response


class RecommendBySimilarTitleAdapter(LogicAdapter):
    def can_process(self, statement):
        # Check if the user input contains a phrase related to similar title recommendation
        return any(word in statement.text.lower() for word in ['similar', 'title'])

    def process(self, statement, additional_response_selection_parameters=None):
        # Prompt the user for movie title
        response = Statement("What movie title do you want similar recommendations for?")
        return response


class RecommendByUserAdapter(LogicAdapter):
    def can_process(self, statement):
        # Check if the user input contains a phrase related to user-based recommendation
        return any(word in statement.text.lower() for word in ['user', 'users'])

    def process(self, statement, additional_response_selection_parameters=None):
        # Prompt the user for user preferences
        response = Statement("What user do you want recommendations for?")
        return response


class RecommendByGenreAdapter(LogicAdapter):
    def can_process(self, statement):
        # Check if the user input contains a phrase related to genre-based recommendation
        return any(word in statement.text.lower() for word in ['genre', 'genres'])

    def process(self, statement, additional_response_selection_parameters=None):
        # Prompt the user for genre preferences
        response = Statement("What genre are you interested in?")
        return response


class RecommendByYearAdapter(LogicAdapter):
    def can_process(self, statement):
        # Check if the user input contains a phrase related to year-based recommendation
        return any(word in statement.text.lower() for word in ['year', 'years'])

    def process(self, statement, additional_response_selection_parameters=None):
        # Prompt the user for year preferences
        response = Statement("What year are you interested in?")
        return response
