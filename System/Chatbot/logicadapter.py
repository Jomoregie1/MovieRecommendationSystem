import re
from chatterbot import utils
from chatterbot.logic import LogicAdapter
from chatterbot.storage.sql_storage import SQLStorageAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from System.RecommendationEngine.recommendationEngine import count_rated_movies_for_user, \
    recommend_movies_to_rate_for_new_users, store_rating, recommend_movies_based_on_user, recommend_movies_based_on_tags \
    , recommend_movies_based_on_year, recommend_movies_based_on_year_and_genre, recommend_movies_based_on_title \
    , recommend_movies_based_on_genre
from chatterbot.conversation import Statement
from sqlalchemy.sql.expression import text
from flask_login import current_user
from System.models import Statement
from datetime import datetime
from System.image import image_url
import json


# TODO Look into having separate metadata for each recommendation system by using separate keys in the conversation metadata
# TODO you are having serious issues with the control flow, with the meta (mainly) NEEDS TO BE ADDRESSED!
# TODO test with new users to monitor how the code works around this, the issue is now that the meta data is not updating for what ever reason so the solution has been stated above, after this is resolved focus on control flow

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


# TODO major issue with this adapter getting an eror while rating
# TODO oding testO quite a bit of issues with this one completely during the ratings gives an attribute error and also after 10 movies has been rated has unexpected behaviour
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
        if num_rated_movies >= 10:
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
        self.adapter_in_use = True
        self.invalid_input = False

    def set_user_id(self, user_id):
        self.user_id = user_id
        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, 'set_user_id') and not isinstance(adapter, BridgeLogicAdapter):
                adapter.set_user_id(user_id)

    def can_process(self, statement):
        num_rated_movies = count_rated_movies_for_user(self.user_id)

        if num_rated_movies < 10:
            return False

        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False

        print("After the adapter is active check")
        try:
            selected_option = int(statement.text.strip())
            if selected_option == 0 or selected_option not in range(1, 7):
                print(f"BridgeLogicAdapter can_process: True -- Inside this selected_option == 0 or selected_option "
                      f"not in range(1, 7) ")
                return True
        except ValueError:
            print(f"BridgeLogicAdapter can_process: True -- valueError")
            return True

        print(f"BridgeLogicAdapter can_process: False")
        return False

    def reset_meta_data(self, conversation):
        metadata = conversation[0].meta
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        print("Metadata before reset:", metadata)

        metadata["current_movie_index"] = 0
        keys_to_remove = ["popular_movies", "recommended_movies", "last_recommendation"]
        if all(key in metadata for key in keys_to_remove):
            for key in keys_to_remove:
                del metadata[key]

        self.update_metadata_and_conversation(self.user_id, conversation, metadata)

        print("Metadata after reset:", metadata)

        return metadata

    # def handle_recommendation_option(self, statement):
    #     try:
    #         selected_option = int(statement.text.strip())
    #         print(f"BridgeLogicAdapter selected_option: {selected_option}")
    #     except ValueError:
    #         # User entered something other than a number
    #         self.invalid_input = True
    #         return None
    #
    #     if 1 <= selected_option <= len(self.recommendation_adapters):
    #         selected_adapter = self.recommendation_adapters[selected_option - 1]
    #         print(f"BridgeLogicAdapter selected_adapter: {type(selected_adapter).__name__}")
    #         if hasattr(selected_adapter, 'can_process') and selected_adapter.can_process(statement):
    #             response = selected_adapter.process(statement)
    #             return response
    #
    #     return None

    def update_metadata_and_conversation(self, user_id, conversation, metadata):
        conversation[0].meta = metadata
        self.chatbot.storage.update_conversation(user_id, conversation)

    def process(self, statement, additional_response_selection_parameters=None):
        print(f"Debug: BridgeLogicAdapter process called, statement: {statement.text.strip()}")
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

        response_text = "Please choose one of the following recommendation options:\n" \
                        "1. Recommend movies based on year and genre\n" \
                        "2. Recommend movies based on a tag\n" \
                        "3. Recommend movies based on genre\n" \
                        "4. Recommend movies based on year\n" \
                        "5. Recommend movies based on a similar title\n" \
                        "6. Recommend movies based on user"

        response = Statement(text=response_text)
        response.confidence = 1.0
        return response


class RecommendMoviesBasedOnYearAndGenreAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):

        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False
            elif isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                return True

        if statement.text.strip() == '1':
            self.active = True
            return True
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print("RecommendMoviesBasedOnYearAndGenreAdapter")
        pass


# TODO to work on the functionality of the adapters first before moving on to the making improvements to the recommendation system.
class RecommendMoviesBasedOnTagAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):

        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False
            elif isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                return True

        if statement.text.strip() == '2':
            self.active = True
            return True
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMovieBasedOnGenreAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):

        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False
            elif isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                return True

        if statement.text.strip() == '3':
            self.active = True
            return True
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        pass


class RecommendMoviesBasedOnYearAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):
        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False
            elif isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                return True

        if statement.text.strip() == '4':
            self.active = True
            return True
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        pass


# TODO when I type 0 it changes the recommend movies list, it now does take me back to the recommendation list. However an it does not prompt me to enter title and the movie changes!
# TODO issue includes control flow, after I have rated a movie, I should be allowed to rate another movie straight away,but I am unable too as once I supply a title it takes me back to the menu. However this works after a rating has been accepted.


class RecommendMovieBasedOnSimilarTitleAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.first_interaction = True
        self.isPromptMessage = True
        self.prev_recommendations = set()
        self.active = False
        self.title = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMovieBasedOnSimilarTitleAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 5 ")
        if statement.text.strip() == '5':
            self.active = True
            print(f"Debug: RecommendMovieBasedOnSimilarTitleAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 5 ")
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['similar_title_meta']['recommended_movies_list']) > 0:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['similar_title_meta']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['similar_title_meta']['recommended_movies_list'].pop(0)
                    meta['similar_title_meta']['movies_list'].clear()
                    meta['similar_title_meta']['shown_movie'].clear()
                    self.update_user_conversation_meta(user_conversation, meta)
                    self.first_interaction = True
                    if 3 < int(user_rating) <= 5:
                        response_text = f"Great, thank you for your rating. Really glad you enjoyed the movie! I'll be " \
                                        f"sure to keep up the good work. 😊 "
                        self.movie_image_url = None
                    elif int(user_rating) < 3:
                        response_text = f"Great, thank you for your rating. So sorry you did not enjoy the movie! " \
                                        f"I'll do " \
                                        f"better next time. 😔 "
                        self.movie_image_url = None
                    else:
                        response_text = f"Great, thank you for your rating. I think I can do better next time, " \
                                        f"just keep " \
                                        f"believing. 😁"
                        self.movie_image_url = None
                else:
                    response_text = f"Oops! It looks like you have already rated this movie. Do you want to try " \
                                    f"again? or enter 0 to go back to the recommendation menu 😊 "
                    self.movie_image_url = None
                    meta['similar_title_meta']['recommended_movies_list'].pop(0)
                    self.update_user_conversation_meta(user_conversation, meta)

            elif user_rating.isdigit() and int(user_rating) == 0:
                self.active = False
                response_text = f"Back to the main menu we go, Once you have finished watching, {recommended_movie[1]}, " \
                                f"Don't forget to provide a rating, pinky promise?! 🤞💖"
                self.movie_image_url = None
                self.first_interaction = True


            else:
                response_text = f"Please rate the movie {recommended_movie[1]} (1-5) before getting more " \
                                f"recommendations or if you haven't watched the movie yet, 0 to go back to the main " \
                                f"menu. "
                self.movie_image_url = image_url(recommended_movie[1])
                self.first_interaction = False
        else:

            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            print(f"DEBUG: What is isPromptMessage value {self.isPromptMessage}")
            if self.isPromptMessage:
                self.isPromptMessage = False
                response_text = "Please enter a movie title, and I'll suggest some similar movies you might enjoy."
                self.movie_image_url = None
            else:
                self.title = statement.text.strip()
                print(f"This is a test for self.title: {self.title}")
                recommended_movies = recommend_movies_based_on_title(self.title, self.user_id)
                print(f"The recommended movies list: {recommended_movies}")
                meta = self.initialize_meta(user_conversation)
                meta, invalid_input = self.update_meta_based_on_user_input(meta, statement, recommended_movies)

                print(
                    f"This is meta after the update_meta function, showing meta: {meta} and the invalid_input: {invalid_input}")
                response_text = self.generate_next_movie_recommendation(meta, statement, invalid_input)
                print(f"This is the response_text: {response_text}")
                print(f"What is the active status {self.active}")
                self.update_user_conversation_meta(user_conversation, meta)
                print(f"DEBUG: Meta that is being passed {meta}")

        response = Statement(text=response_text)
        response.confidence = 1.0
        return response

    def get_or_create_user_conversation(self):
        user_conversation = self.chatbot.storage.get_conversation(self.user_id)
        if not user_conversation:
            user_conversation = self.chatbot.storage.create_conversation(self.user_id)
        return user_conversation

    def initialize_meta(self, user_conversation):
        print(f"User conversation: {user_conversation}")
        meta = user_conversation[0].meta or "{}"
        print(f"Meta after initial assignment: {meta}")
        if not isinstance(meta, dict):
            meta = json.loads(meta)
            print(f"Meta after json.loads: {meta}")

        if 'similar_title_meta' not in meta:
            meta['similar_title_meta'] = {
                'movies_list': None,
                'current_movie_index': 0,
                'shown_movie': None,
                'recommended_movies_list': [],
            }

        return meta

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    @property
    def is_active(self):
        return self.active

    def update_user_conversation_meta(self, user_conversation, meta):
        print("Before updating meta:", user_conversation[0].meta)
        user_conversation[0].meta = json.dumps(meta)
        print("After updating meta:", user_conversation[0].meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

    def update_meta_based_on_user_input(self, meta, statement, recommended_movies):
        invalid_input = False
        user_response = statement.text.strip().lower()

        if user_response == 'yes' and len(meta['similar_title_meta']['movies_list']) > 0:
            meta['similar_title_meta']['recommended_movies_list'].append(meta['similar_title_meta']['shown_movie'])
        elif user_response == 'no' and len(meta['similar_title_meta']['movies_list']) > 0:
            meta['similar_title_meta']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['similar_title_meta']['movies_list'].clear()
            meta['similar_title_meta']['shown_movie'].clear()
        # TODO issue with this part of code as it does not allow me to enter an invalid input it simply never reaches
        #  the else statement BIG PROBLEM!
        elif user_response == self.title:
            meta['similar_title_meta']['movies_list'] = recommended_movies
            meta['similar_title_meta']['current_movie_index'] = 0

        print(f"Update meta based on user input {print(meta)}")
        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        global next_movie_title
        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['similar_title_meta']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['similar_title_meta']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more similar movie recommendations. Please enter another " \
                            "movie title or enter 0 to go back to the recommendation menu."
            self.movie_image_url = None
            meta['similar_title_meta']['current_movie_index'] = 0

        else:
            try:
                if len(meta['similar_title_meta']['movies_list']) > 0:
                    next_movie_title = meta['similar_title_meta']['movies_list'][current_movie_index][1]
                    shown_movie = meta['similar_title_meta']['movies_list'][current_movie_index]
                    meta['similar_title_meta']['shown_movie'] = shown_movie

                # TODO - Test this, see if once you say yes does it allow you to rate the movie then, does it allow
                #  you to suggest another movie title.
                if user_response == 'yes':
                    response_text = 'Awesome, I''m so glad you loved my recommendation! I hope you enjoy watching the ' \
                                    'movie. ' \
                                    'Once you''re done watching, you''ll be promoted to rate the movie! Your feedback ' \
                                    'is ' \
                                    'valuable and will help me make even better suggestions in the future. '
                    self.active = False
                    self.movie_image_url = None
                    self.isPromptMessage = True
                elif invalid_input:
                    response_text = f"Sorry, I didn't understand that. Please reply with 'yes' or 'no' for {next_movie_title}." \
                                    f"or 0 to go back to the recommendation menu."
                    self.movie_image_url = None

                # TODO potentially might need to set first_interaction to TRUE
                elif user_response == '0':
                    response_text = "Great, I'll take you back to the recommendation menu, hope that is okay?"
                    self.movie_image_url = None
                    self.isPromptMessage = True
                else:
                    response_text = f"Based on the title you provided, I really think you'll enjoy {next_movie_title}." \
                                    f"Would you like to watch it now, or would you prefer a recommendation for another " \
                                    f"movie that's similar to the title provided? " \
                                    f"Please let me know by replying with 'yes' if you'd like to watch it, or 'no' if " \
                                    f"you'd like another recommendation or enter 0 to go back to the recommendation " \
                                    f"menu or type another movie title for different suggestions. 😁"

                    self.movie_image_url = image_url(next_movie_title)
            except IndexError:
                response_text = "No movie with a similar title found. Please try again with another title"

        return response_text


class RecommendMoviesBasedOnUserAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.first_interaction = True
        self.prev_recommendations = set()  # Add a set to store previous movie recommendations
        self.active = False

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):

        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, "is_active") and adapter.is_active:
                return False
            elif isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                return True

        if statement.text.strip() == '6':
            self.regenerate_movie_recommendations()
            self.active = True
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

    @property
    def is_active(self):
        return self.active

    def is_greeting(self, statement):
        greeting_keywords = ["hello", "hi", "hey", "greetings", "welcome", "Yo"]
        statement_words = re.findall(r'\w+', statement.text.lower())
        return any(word in statement_words for word in greeting_keywords)

    def update_user_conversation_meta(self, user_conversation, meta):
        user_conversation[0].meta = json.dumps(meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)
