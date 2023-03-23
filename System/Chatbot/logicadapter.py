import re
from chatterbot.logic import LogicAdapter
from chatterbot.storage.sql_storage import SQLStorageAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from System.RecommendationEngine.recommendationEngine import count_rated_movies_for_user, \
    recommend_movies_to_rate_for_new_users, store_rating
from chatterbot.conversation import Statement
from sqlalchemy.sql.expression import text
from flask_login import current_user
from System.models import Statement
from datetime import datetime
import json


class CustomSQLStorageAdapter(SQLStorageAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = create_engine('mysql://root:root@localhost:3306/chatbot')
        self.Session = sessionmaker(bind=self.engine)

    def create_conversation(self, user_id):
        current_time = datetime.now()
        session = self.Session()
        new_conversation = Statement(text="", conversation=f"user_id:{user_id}", search_in_response_to="",
                                     search_text="", created_at=current_time, in_response_to=""
                                     , persona="", metadata=json.dumps({}))
        session.add(new_conversation)
        session.commit()
        session.close()
        return [new_conversation]

    def get_conversation(self, user_id):
        session = self.Session()
        conversation = session.query(Statement).filter(Statement.conversation.like(f"%user_id:{user_id}%")).all()
        session.close()
        return conversation

    def update_conversation(self, user_id, conversation):
        session = self.Session()
        for statement in conversation:
            if statement.id is None:
                statement.conversation = f"user_id:{user_id}"
                session.add(statement)
        session.commit()
        session.close()


# TODO 1 MAKE SURE THIS WORKS AS EXPECTED! - so far main issue with this code is the logic is all wrong, TODO 2 need
#  to make sure that the conversation can be maintained and on top of that, ensure that previous conversation is
#  kept, ensure that the current index of the popular list is also maintained
class UserConversationLogicAdapter(LogicAdapter):
    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        if not self.user_id:
            return False

        # Check if the user has rated 10 movies
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        if num_rated_movies >= 10:
            return False

        return True

    def process(self, statement, additional_response_selection_parameters=None):
        response_text = ""
        # Retrieve the user's conversation from storage or create a new one
        user_conversation = self.chatbot.storage.get_conversation(self.user_id)
        if not user_conversation:
            user_conversation = self.chatbot.storage.create_conversation(self.user_id)

        # Store the user's input statement
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

        # Get movie recommendations
        message, popular_movies = recommend_movies_to_rate_for_new_users(self.user_id)

        # Load metadata from the first statement in user_conversation
        metadata = user_conversation[0].metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        elif not isinstance(metadata, dict):
            metadata = {}

        # Set 'current_movie_index' to 0 if it's not already set
        if 'current_movie_index' not in metadata:
            metadata['current_movie_index'] = 0

        if statement.text.strip().lower() == 'no':
            metadata['current_movie_index'] += 1

        # Check if the user has provided a rating for the last recommended movie
        rating_match = re.match(r"(\d)", statement.text.strip())
        if rating_match and 'last_recommendation' in metadata:
            rating = int(rating_match.group(1))
            movie_id = metadata['last_recommendation'][0]
            if 1 <= rating <= 5:
                store_rating(self.user_id, movie_id, rating)
                metadata.pop('last_recommendation', None)
                metadata['current_movie_index'] += 1

        if 'last_recommendation' not in metadata and len(popular_movies) > 0:
            next_movie_id, next_movie_title = popular_movies[int(metadata['current_movie_index'])]
            response_text = f"Have you watched {next_movie_title}? If yes, please rate it from 1 to 5. If you haven't " \
                            f"seen it, reply 'no'. "
            metadata['last_recommendation'] = (next_movie_id, next_movie_title)
            metadata['current_movie_index'] += 1

        response = Statement(text=response_text)

        # Store metadata back as a JSON string or a MetaData object, depending on your implementation
        if isinstance(metadata, dict):
            user_conversation[0].metadata = json.dumps(metadata)
        else:
            user_conversation[0].metadata = metadata

        # Update the conversation in storage
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

        response.confidence = 1.0

        return response

# class RecommendMoviesAdapter(LogicAdapter):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#
#     def can_process(self, statement):
#         # Check if the user's statement includes a year
#         if 'year' in statement.text.lower():
#             return True
#         else:
#             return False
#
#     def process(self, statement, additional_response_selection_parameters=None):
#         # Extract the year from the user's statement
#         year = None
#         for word in statement.text.split():
#             if word.isdigit():
#                 year = int(word)
#                 break
#
#         # If a valid year was found, recommend movies
#         if year:
#             recommended_movies = recommend_movies_based_on_year(year, user=current_user.get_id())
#
#             # Construct a response string listing the recommended movies
#             response = f"Here are the top movies from {year}:"
#             for rank, movie in enumerate(recommended_movies, start=1):
#                 response += f"\n{rank}. {movie[0]}"
#
#             return self.process_response(statement, response)
#         else:
#             return self.process_response(statement, "I'm sorry, I didn't understand which year you were asking about.")
#
#     def process_response(self, statement, response):
#         """
#         This method takes in a statement and a response and returns a response object.
#         """
#         response_statement = Statement(response)
#         response_statement.confidence = 1.0
#         return response_statement

# TODO this needs to handle functionality to be able to allow new users on the platform a way to rate 10 movies.
# class RecommendationAdapter(LogicAdapter):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.movies_rated = 0
#
#     def can_process(self, statement):
#         # Check if the user has rated less than 10 movies
#         if self.movies_rated < 10:
#             # Check if the user is new and has not rated any movies
#             if 'new user' in self.chatbot.user_data.get('recommendation_state', ''):
#                 return True
#             # Check if the user has not rated any movies yet
#             elif 'rated' not in self.chatbot.user_data.get('recommendation_state', ''):
#                 return True
#         return False
#
#     def process(self, statement, additional_response_selection_parameters=None):
#         # If the user is new, recommend a list of movies
#         if 'new user' in self.chatbot.user_data.get('recommendation_state', ''):
#             recommended_movies = self.recommend_movies()
#             response = f"Welcome to the platform! Here are some movies you might like:\n{recommended_movies}"
#             self.chatbot.user_data['recommendation_state'] = 'recommended'
#         # If the user has not rated any movies yet, ask them to rate a movie
#         elif 'rated' not in self.chatbot.user_data.get('recommendation_state', ''):
#             movie = self.get_unrated_movie()
#             response = f"Have you watched {movie}? Please rate it out of 5."
#             self.chatbot.user_data['current_movie'] = movie
#             self.chatbot.user_data['recommendation_state'] = 'asked'
#         # If the user has rated a movie, update the state and ask for another rating
#         else:
#             rating = int(statement.text)
#             movie = self.chatbot.user_data['current_movie']
#             self.update_movie_rating(movie, rating)
#             self.movies_rated += 1
#             if self.movies_rated < 10:
#                 movie = self.get_unrated_movie()
#                 response = f"Thank you for rating {movie}. Have you watched another movie? Please rate it out of 5."
#                 self.chatbot.user_data['current_movie'] = movie
#                 self.chatbot.user_data['recommendation_state'] = 'asked'
#             else:
#                 response = "Thank you for rating the movies. Enjoy the recommendations!"
#                 self.chatbot.user_data['recommendation_state'] = 'rated'
#
#         return self.process_response(statement, response)
#
#     def recommend_movies(self):
#         # Call your recommendation engine to recommend a list of movies for new users
#         # (you'll need to replace 'recommend_movies' with your function name)
#         recommended_movies = recommend_movies(user='new_user')
#         # Join the movie titles into a single string
#         recommended_movies = '\n'.join([f'{i+1}. {m[0]}' for i, m in enumerate(recommended_movies)])
#         return recommended_movies
#
#     def get_unrated_movie(self):
#         # Call your database to find a movie that the user has not rated yet
#         # (you'll need to replace 'get_unrated_movie' with your function name)
#         movie = get_unrated_movie(self.chatbot.user.id)
#         return movie
#
#     def update_movie_rating(self, movie, rating):
#         # Call your database to update the rating for a movie by the current user
#         # (you'll


