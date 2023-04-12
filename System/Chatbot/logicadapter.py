import re
from chatterbot import utils
from chatterbot.logic import LogicAdapter
from chatterbot.storage.sql_storage import SQLStorageAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from System.RecommendationEngine.recommendationEngine import count_rated_movies_for_user, \
    recommend_movies_to_rate_for_new_users, store_rating, recommend_movies_based_on_user
from chatterbot.conversation import Statement
from sqlalchemy.sql.expression import text
from flask_login import current_user
from System.models import Statement
from datetime import datetime
from System.image import image_url
import json


class CustomSQLStorageAdapter(SQLStorageAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = create_engine('mysql://root:root@localhost:3306/chatbot')
        self.Session = sessionmaker(bind=self.engine)

    def create_conversation(self, user_id, meta=None):
        current_time = datetime.now()
        session = self.Session()
        meta_str = json.dumps(meta) if meta else json.dumps({})
        new_conversation = Statement(text="", conversation=f"user_id:{user_id}", search_in_response_to="",
                                     search_text="", created_at=current_time, in_response_to=""
                                     , persona="", meta=meta_str)
        session.add(new_conversation)
        session.commit()
        session.close()
        return [new_conversation]

    def get_conversation(self, user_id):
        session = self.Session()
        conversation = session.query(Statement).filter(Statement.conversation.like(f"%user_id:{user_id}%")).all()
        session.close()

        if conversation:
            print("Metadata in get_conversation:", conversation[0].meta)
        return conversation

    def update_conversation(self, user_id, conversation):
        print("Update conversation called for user_id:", user_id)
        session = self.Session()

        # Only update the metadata for the first statement in the conversation
        statement = conversation[0]
        print("Statement to update:", statement)
        print("Statement metadata before update:", statement.meta)

        if statement.id is None:
            statement.conversation = f"user_id:{user_id}"
            session.add(statement)
        else:
            existing_statement = session.query(Statement).filter(Statement.id.__eq__(statement.id)).first()
            if existing_statement:
                existing_statement.meta = statement.meta
                session.add(existing_statement)

        session.commit()
        print("Statement metadata after update:", statement.meta)
        session.close()


class UserConversationLogicAdapter(LogicAdapter):
    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.first_interaction = True

    def set_user_id(self, user_id):
        self.user_id = user_id

    def reset_first_interaction(self):
        self.first_interaction = True

    def can_process(self, statement):
        if not self.user_id:
            return False

        print(self.user_id)
        print("UserConversation")
        # Check if the user has rated 10 movies
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        if num_rated_movies == 10:
            return False

        return True

    def process(self, statement, additional_response_selection_parameters=None):
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        popular_movies = recommend_movies_to_rate_for_new_users(self.user_id)
        meta = self.initialize_meta(user_conversation, popular_movies)
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        meta, invalid_input = self.update_meta_based_on_user_input(meta, statement)

        if not meta['completed_initial_rating'] and self.is_greeting(statement) and self.first_interaction:
            self.first_interaction = False
            if num_rated_movies == 0:
                response_text = "Hey, Thanks for registering. Before we start recommending movies to you, " \
                                "we need to get a taste of what you like. We will show you a list of movies. " \
                                "Please rate 10 movies you have seen before between 1 and 5. "
                response_text += self.generate_next_movie_recommendation(meta)
            else:
                response_text = f"Welcome back! You have rated {num_rated_movies} movies. " \
                                f"We still need to get a sense of what you like. "
                response_text += self.generate_next_movie_recommendation(meta)
        else:
            response_text = self.generate_next_movie_recommendation(meta, invalid_input)

        self.update_user_conversation_meta(user_conversation, meta)

        response = Statement(text=response_text)
        response.confidence = 1.0

        return response

    def get_or_create_user_conversation(self):
        user_conversation = self.chatbot.storage.get_conversation(self.user_id)
        if not user_conversation:
            user_conversation = self.chatbot.storage.create_conversation(self.user_id)
        return user_conversation

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def initialize_meta(self, user_conversation, popular_movies):
        meta = user_conversation[0].meta or "{}"
        print(f"Loaded meta from user_conversation: {meta}")
        if not isinstance(meta, dict):
            meta = json.loads(meta)

            # Initialize the keys if they are not in the meta dictionary
        if 'popular_movies' not in meta:
            meta['popular_movies'] = popular_movies
        if 'current_movie_index' not in meta:
            meta['current_movie_index'] = 0
        if 'last_recommendation' not in meta:
            meta['last_recommendation'] = None
        if 'completed_initial_rating' not in meta:
            meta['completed_initial_rating'] = False

        print(f"Initialized meta: {meta}")
        return meta

    def update_meta_based_on_user_input(self, meta, statement):
        invalid_input = False
        rating_match = re.match(r"(\d)", statement.text.strip())

        if rating_match and 'last_recommendation' in meta:
            rating = int(rating_match.group(1))
            movie_id = meta['last_recommendation'][0]
            if 1 <= rating <= 5:
                store_rating(self.user_id, movie_id, rating)
                meta['current_movie_index'] += 1
            else:
                invalid_input = True
        elif statement.text.strip().lower() == 'no':
            meta['current_movie_index'] += 1
        else:
            invalid_input = True

        # Set 'current_movie_index' to 0 if it's not already set
        if 'current_movie_index' not in meta:
            meta['current_movie_index'] = 0

        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, invalid_input=False):
        next_movie_id, next_movie_title = meta['popular_movies'][
            int(meta['current_movie_index']) % len(meta['popular_movies'])]
        meta['last_recommendation'] = (next_movie_id, next_movie_title)

        self.movie_image_url = image_url(next_movie_title)

        if invalid_input:
            response_text = f"Sorry, I didn't understand that. Please enter a rating between 1 and 5 or 'no' for {next_movie_title}."
        else:
            response_text = f"Have you watched {next_movie_title}? If yes, please rate it from 1 to 5. If you haven't " \
                            f"seen it, reply 'no'. "

        return response_text

    def is_greeting(self, statement):
        greeting_keywords = ["hello", "hi", "hey", "greetings", "welcome", "Yo"]
        statement_words = re.findall(r'\w+', statement.text.lower())
        return any(word in statement_words for word in greeting_keywords)

    def update_user_conversation_meta(self, user_conversation, meta):
        user_conversation[0].meta = json.dumps(meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)


# TODO still bugs in the process function when a user reaches 10 sometimes does not work as expected!
class BridgeLogicAdapter(LogicAdapter):
    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.recommendation_adapters = []

        # Instantiate recommendation adapters
        recommendation_adapters_config = kwargs.get('recommendation_adapters', [])
        for adapter_config in recommendation_adapters_config:
            adapter_instance = utils.import_module(adapter_config['import_path'])(chatbot)
            self.recommendation_adapters.append(adapter_instance)

    def set_user_id(self, user_id):
        self.user_id = user_id
        for adapter in self.recommendation_adapters:
            if hasattr(adapter, 'set_user_id'):
                adapter.set_user_id(user_id)

    def can_process(self, statement):
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        if num_rated_movies >= 10:
            return True
        return False

    def reset_meta_data(self, conversation):
        metadata = conversation[0].meta
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        metadata["current_movie_index"] = 0

        keys_to_remove = ["popular_movies", "next_movie_recommendation", "last_recommendation"]
        if all(key in metadata for key in keys_to_remove):
            for key in keys_to_remove:
                del metadata[key]

        return metadata

    def handle_recommendation_option(self, statement):
        try:
            selected_option = int(statement.text.strip())
        except ValueError:
            # User entered something other than a number
            return None

        if 1 <= selected_option <= len(self.recommendation_adapters):
            selected_adapter = self.recommendation_adapters[selected_option - 1]
            if hasattr(selected_adapter, 'process'):
                response = selected_adapter.process(statement)
                return response

        return None

    def update_metadata_and_conversation(self, user_id, conversation, metadata):
        conversation[0].meta = metadata
        self.chatbot.storage.update_conversation(user_id, conversation)

    def process(self, statement, additional_response_selection_parameters=None):
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        conversation = self.chatbot.storage.get_conversation(self.user_id)
        metadata = self.reset_meta_data(conversation)

        if not metadata.get("completed_initial_rating", False):
            response_text = f"Congratulations! You have rated {num_rated_movies} movies. " \
                            "I now have a better understanding of your preferences."
            metadata["completed_initial_rating"] = True
            response = Statement(text=response_text)
            response.confidence = 1.0
            conversation[0].meta = metadata
            self.update_metadata_and_conversation(self.user_id, conversation, metadata)
            return response
        else:
            if not metadata.get("recommendation_options_shown", False):
                response_text = "Please choose one of the following recommendation options:\n" \
                                "1. Recommend movies based on year and genre\n" \
                                "2. Recommend movies based on a tag\n" \
                                "3. Recommend movies based on genre\n" \
                                "4. Recommend movies based on year\n" \
                                "5. Recommend movies based on a similar title\n" \
                                "6. Recommend movies based on user"
                metadata["recommendation_options_shown"] = True
                self.update_metadata_and_conversation(self.user_id, conversation, metadata)
            else:
                response = self.handle_recommendation_option(statement)
                if response is not None:
                    return response
                else:
                    response_text = "Please enter the number corresponding to your chosen recommendation option."
                    metadata["recommendation_options_shown"] = False
                    self.update_metadata_and_conversation(self.user_id, conversation, metadata)

            response = Statement(text=response_text)
            response.confidence = 1.0
            return response


class RecommendMoviesBasedOnYearAndGenreAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        return statement.text.strip() == '1'

    def process(self, statement, additional_response_selection_parameters=None):
        print("RecommendMoviesBasedOnYearAndGenreAdapter")
        pass


# TODO tO work on the functionality of the adapters first before moving on to the making improvements to the recommendation system.
class RecommendMoviesBasedOnTagAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        return statement.text.strip() == '2'

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMovieBasedOnGenreAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        return statement.text.strip() == '3'

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMoviesBasedOnYearAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        return statement.text.strip() == '4'

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMovieBasedOnSimilarTitleAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        return statement.text.strip() == '5'

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMoviesBasedOnUserAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.first_interaction = True
        self.prev_recommendations = set()  # Add a set to store previous movie recommendations

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        if statement.text.strip() == '6':
            self.regenerate_movie_recommendations()
            return True
        return False

    def reset_first_interaction(self):
        self.first_interaction = True

    def process(self, statement, additional_response_selection_parameters=None):
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        movies_based_on_users = recommend_movies_based_on_user(self.user_id)
        print(movies_based_on_users)
        meta = self.initialize_meta(user_conversation, movies_based_on_users)
        meta, invalid_input = self.update_meta_based_on_user_input(meta, statement)

        if self.is_greeting(statement) and self.first_interaction:
            self.first_interaction = False
            response_text = "Great lets recommend you a movie based on similar users!"
            response_text += self.generate_next_movie_recommendation(meta)
        else:
            response_text = self.generate_next_movie_recommendation(meta, invalid_input)

        self.update_user_conversation_meta(user_conversation, meta)

        response = Statement(text=response_text)
        response.confidence = 1.0

        return response

    def get_or_create_user_conversation(self):
        user_conversation = self.chatbot.storage.get_conversation(self.user_id)
        if not user_conversation:
            user_conversation = self.chatbot.storage.create_conversation(self.user_id)
        return user_conversation

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def initialize_meta(self, user_conversation, movies_based_on_users):
        meta = user_conversation[0].meta or "{}"
        print(f"Loaded meta from RecommendMoviesBasedOnUserAdapter : {meta}")
        if not isinstance(meta, dict):
            meta = json.loads(meta)

            # Initialize the keys if they are not in the meta dictionary
        if 'movies_based_on_users' not in meta:
            meta['movies_based_on_users'] = movies_based_on_users
        if 'current_movie_index' not in meta:
            meta['current_movie_index'] = 0
        if 'last_recommendation' not in meta:
            meta['last_recommendation'] = None
        return meta

    def update_meta_based_on_user_input(self, meta, statement):
        invalid_input = False
        rating_match = re.match(r"(\d)", statement.text.strip())

        if rating_match and 'last_recommendation' in meta:
            rating = int(rating_match.group(1))
            movie_id = meta['last_recommendation'][0]
            if 1 <= rating <= 5:
                store_rating(self.user_id, movie_id, rating)
                meta['current_movie_index'] += 1
            else:
                invalid_input = True
        elif statement.text.strip().lower() == 'no':
            meta['current_movie_index'] += 1
        else:
            invalid_input = True

        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, invalid_input=False):
        next_movie_title, next_movie_rating = meta['movies_based_on_users'][
            int(meta['current_movie_index']) % len(meta['movies_based_on_users'])]
        meta['last_recommendation'] = (next_movie_title, next_movie_rating)

        self.movie_image_url = image_url(next_movie_title)
        print(f"RecommendMoviesBasedOnUserAdapter movie_image_url: {self.movie_image_url}")

        if invalid_input:
            response_text = f"Sorry, I didn't understand that. Please enter a rating between 1 and 5 or 'no' for {next_movie_title}."
        else:
            response_text = f" I think you would really like this movie {next_movie_title}? If yes, please rate it from 1 to 5. If you haven't " \
                            f"seen it, reply 'no'. "

        return response_text

    def regenerate_movie_recommendations(self):
        self.prev_recommendations.clear()  # Clear the set of previous movie recommendations
        movies_based_on_users = recommend_movies_based_on_user(self.user_id)
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation, movies_based_on_users)
        self.update_user_conversation_meta(user_conversation, meta)

    def is_greeting(self, statement):
        greeting_keywords = ["hello", "hi", "hey", "greetings", "welcome", "Yo"]
        statement_words = re.findall(r'\w+', statement.text.lower())
        return any(word in statement_words for word in greeting_keywords)

    def update_user_conversation_meta(self, user_conversation, meta):
        user_conversation[0].meta = json.dumps(meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)
