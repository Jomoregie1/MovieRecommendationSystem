import re
from chatterbot import utils
from chatterbot.logic import LogicAdapter
from chatterbot.storage.sql_storage import SQLStorageAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from System.RecommendationEngine.recommendationEngine import count_rated_movies_for_user, \
    recommend_movies_to_rate_for_new_users, store_rating, recommend_movies_based_on_user, recommend_movies_based_on_tags \
    , recommend_movies_based_on_year, recommend_movies_based_on_year_and_genre, recommend_movies_based_on_title \
    , recommend_movies_based_on_genre, list_of_genres
from chatterbot.conversation import Statement
from sqlalchemy.sql.expression import text
from System.models import Statement
from datetime import datetime
from System.image import image_url
import json


# TODO Need to fix issue with first adpater to bridge adapter
# TODO need to finish adapter 6
# TODO need to finish other adapters
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

    def set_bridge_adapter_activate_status(self, activate_status):
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                adapter.set_activate(activate_status)

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
        if count_rated_movies_for_user(self.user_id) == 10:
            print(
                f"Print value of movies user has rated inside def process: {count_rated_movies_for_user(self.user_id)}")
            self.set_bridge_adapter_activate_status(True)
            self.movie_image_url = None

        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                print(adapter.activate)

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
        elif count_rated_movies_for_user(self.user_id) == 10:
            response_text = "That was so exhausting! I've learnt so much about you!... Are you ready? 😁"
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
        self.activate = False

    def set_user_id(self, user_id):
        self.user_id = user_id
        for adapter in self.chatbot.logic_adapters:
            if hasattr(adapter, 'set_user_id') and not isinstance(adapter, BridgeLogicAdapter):
                adapter.set_user_id(user_id)

    def set_activate(self, activate_status):
        self.activate = activate_status

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
            if selected_option == 0 or selected_option not in range(1, 7) or self.activate:
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
        keys_to_remove = ["popular_movies", "last_recommendation"]
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
            self.activate = False
            metadata["completed_initial_rating"] = True
            response = Statement(text=response_text)
            response.confidence = 1.0
            conversation[0].meta = metadata
            self.update_metadata_and_conversation(self.user_id, conversation, metadata)
            print("Inside the first response message ")
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
        self.isPromptMessage = True
        self.first_interaction = True
        self.year = ''
        self.genre = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):
        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMoviesBasedOnYearAndGenreAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMoviesBasedOnYearAndGenreAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 1 ")
        if (statement.text.strip() == '1' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
            self.active = True
            print(f"Debug: RecommendMoviesBasedOnYearAndGenreAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 1 ")
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['similar_genre_and_year_meta']['recommended_movies_list']) > 0:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['similar_genre_and_year_meta']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['similar_genre_and_year_meta']['recommended_movies_list'].pop(0)
                    meta['similar_genre_and_year_meta']['movies_list'].clear()
                    meta['similar_genre_and_year_meta']['shown_movie'].clear()
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
                    meta['similar_genre_and_year_meta']['recommended_movies_list'].pop(0)
                    self.update_user_conversation_meta(user_conversation, meta)

            elif user_rating.isdigit() and int(user_rating) == 0:
                self.active = False
                response_text = f"Back to the main menu we go, Once you have finished watching, {recommended_movie[1]}, " \
                                f"Don't forget to provide a rating, pinky promise?! 🤞💖"
                self.movie_image_url = None
                self.first_interaction = True


            else:
                response_text = f"Please rate the movie {recommended_movie[1]} between (1-5) before getting more " \
                                f"recommendations or if you haven't watched the movie yet, 0 to go back to the main " \
                                f"menu. "
                self.movie_image_url = image_url(recommended_movie[1])
                self.first_interaction = False
        else:

            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            print(f"DEBUG: What is isPromptMessage value {self.isPromptMessage}")
            if self.isPromptMessage:
                self.isPromptMessage = False
                response_text = "Please enter one of the following genres (Adventure, Comedy, Action, Drama, Crime, " \
                                "Children, Mystery, Animation, Documentary, Thriller, Horror, Fantasy, Western, " \
                                "Film-Noir, Romance, Sci-Fi, Musical, War, IMAX) followed by a year between (1902 and " \
                                "2018) and" \
                                "I'll be able to suggest some " \
                                "movies I think you " \
                                "might enjoy that were " \
                                "made in that genre "
                self.movie_image_url = None
            else:
                meta = self.initialize_meta(user_conversation)
                meta, invalid_input = self.update_meta_based_on_user_input(meta, statement)
                print(f"This is meta after the update_meta function, showing meta: {meta}.")
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

        if 'similar_genre_and_year_meta' not in meta:
            meta['similar_genre_and_year_meta'] = {
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': [],
                'recommended_movies_list': [],
            }

        return meta

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'similar_genre_meta' in meta:
            meta['similar_genre_and_year_meta']['movies_list'].clear()
            meta['similar_genre_and_year_meta']['shown_movie'].clear()
            meta['similar_genre_and_year_meta']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def update_user_conversation_meta(self, user_conversation, meta):
        print("Before updating meta:", user_conversation[0].meta)
        user_conversation[0].meta = json.dumps(meta)
        print("After updating meta:", user_conversation[0].meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

    def update_meta_based_on_user_input(self, meta, statement):
        user_response = statement.text.strip().lower()
        genre_list = [genre.lower() for genre in list_of_genres()]
        invalid_input = False

        year_pattern = r'\d{4}'
        year_match = re.search(year_pattern, user_response)
        year = int(year_match.group()) if year_match else None

        genre = None
        for g in genre_list:
            if g in user_response:
                genre = g
                break

        if genre and year:
            if 1902 <= year <= 2018:
                self.year = year
                self.genre = genre
                recommended_movies = recommend_movies_based_on_year_and_genre(self.year, self.genre, self.user_id)
                meta['similar_genre_and_year_meta']['movies_list'] = recommended_movies
                meta['similar_genre_and_year_meta']['current_movie_index'] = 0
            else:
                invalid_input = True
                self.year = None
                self.genre = None
        elif user_response == 'yes' and len(meta['similar_genre_and_year_meta']['movies_list']) > 0:
            meta['similar_genre_and_year_meta']['recommended_movies_list'].append(meta['similar_genre_and_year_meta']['shown_movie'])
        elif user_response == 'no' and len(meta['similar_genre_and_year_meta']['movies_list']) > 0:
            meta['similar_genre_and_year_meta']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['similar_genre_and_year_meta']['movies_list'].clear()
            meta['similar_genre_and_year_meta']['shown_movie'].clear()
            meta['similar_genre_and_year_meta']['current_movie_index'] = 0
        else:
            invalid_input = True

        print(f"Update meta based on user input {print(meta)}")
        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        global next_movie_title
        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['similar_genre_and_year_meta']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['similar_genre_and_year_meta']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more similar movie recommendations. Please enter another " \
                            "movie genre or enter 0 to go back to the recommendation menu."
            self.movie_image_url = None
            meta['similar_genre_and_year_meta']['current_movie_index'] = 0

        else:
            try:
                if len(meta['similar_genre_and_year_meta']['movies_list']) > 0:
                    next_movie_title = meta['similar_genre_and_year_meta']['movies_list'][current_movie_index][1]
                    shown_movie = meta['similar_genre_and_year_meta']['movies_list'][current_movie_index]
                    meta['similar_genre_and_year_meta']['shown_movie'] = shown_movie

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
                    response_text = f"Based on the genre you provided, I really think you'll enjoy {next_movie_title}." \
                                    f"Would you like to watch it now, or would you prefer a recommendation for another " \
                                    f"movie that's in a similar genre " \
                                    f"Please let me know by replying with 'yes' if you'd like to watch it, or 'no' if " \
                                    f"you'd like another recommendation or enter 0 to go back to the recommendation " \
                                    f"menu or type another movie title for different suggestions. 😁"

                    self.movie_image_url = image_url(next_movie_title)
            except IndexError:
                response_text = "No movie with a similar genre found. Please try again with another title"

        return response_text


# TODO to work on the functionality of the adapters first before moving on to the making improvements to the
#  recommendation system.
class RecommendMoviesBasedOnTagAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False
        self.isPromptMessage = True
        self.first_interaction = True
        self.tag = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):
        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMoviesBasedOnTagAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMoviesBasedOnTagAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 2 ")
        if (statement.text.strip() == '2' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
            self.active = True
            print(f"Debug: RecommendMoviesBasedOnTagAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 2 ")
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['movies_on_tag_meta']['recommended_movies_list']) > 0:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['movies_on_tag_meta']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['movies_on_tag_meta']['recommended_movies_list'].pop(0)
                    meta['movies_on_tag_meta']['movies_list'].clear()
                    meta['movies_on_tag_meta']['shown_movie'].clear()
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
                    meta['movies_on_tag_meta']['recommended_movies_list'].pop(0)
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
                response_text = "Please enter a descriptive word , and I'll suggest some movies I think you might " \
                                "enjoy.🤞 "
                self.movie_image_url = None
            else:
                self.tag = statement.text.strip()
                print(f"This is a test for self.title: {self.tag}")
                recommended_movies = recommend_movies_based_on_tags(self.tag, self.user_id)
                print(f"The recommended movies list: {recommended_movies}")
                meta = self.initialize_meta(user_conversation)
                meta = self.update_meta_based_on_user_input(meta, statement, recommended_movies)

                print(
                    f"This is meta after the update_meta function, showing meta: {meta} ")
                response_text = self.generate_next_movie_recommendation(meta, statement)
                print(f"This is the response_text: {response_text}")
                print(f"What is the active status {self.active}")
                self.update_user_conversation_meta(user_conversation, meta)
                print(f"DEBUG: Meta that is being passed {meta}")

        response = Statement(text=response_text)
        response.confidence = 1.0
        return response

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'movies_on_tag_meta' in meta:
            meta['movies_on_tag_meta']['movies_list'].clear()
            meta['movies_on_tag_meta']['shown_movie'].clear()
            meta['movies_on_tag_meta']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

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

        if 'movies_on_tag_meta' not in meta:
            meta['movies_on_tag_meta'] = {
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': [],
                'recommended_movies_list': [],
            }

        return meta

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def update_user_conversation_meta(self, user_conversation, meta):
        print("Before updating meta:", user_conversation[0].meta)
        user_conversation[0].meta = json.dumps(meta)
        print("After updating meta:", user_conversation[0].meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

    def update_meta_based_on_user_input(self, meta, statement, recommended_movies):
        user_response = statement.text.strip().lower()

        if user_response == 'yes' and len(meta['movies_on_tag_meta']['movies_list']) > 0:
            meta['movies_on_tag_meta']['recommended_movies_list'].append(meta['movies_on_tag_meta']['shown_movie'])
        elif user_response == 'no' and len(meta['movies_on_tag_meta']['movies_list']) > 0:
            meta['movies_on_tag_meta']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['movies_on_tag_meta']['movies_list'].clear()
            meta['movies_on_tag_meta']['shown_movie'].clear()
        # TODO issue with this part of code as it does not allow me to enter an invalid input it simply never reaches
        #  the else statement BIG PROBLEM!
        else:
            meta['movies_on_tag_meta']['movies_list'] = recommended_movies
            meta['movies_on_tag_meta']['current_movie_index'] = 0

        print(f"Update meta based on user input {print(meta)}")
        return meta

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        global next_movie_title
        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['movies_on_tag_meta']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['movies_on_tag_meta']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more similar movie recommendations. Please enter another " \
                            "descriptive word or enter 0 to go back to the recommendation menu."
            self.movie_image_url = None
            meta['movies_on_tag_meta']['current_movie_index'] = 0

        else:
            try:
                if len(meta['movies_on_tag_meta']['movies_list']) > 0:
                    next_movie_title = meta['movies_on_tag_meta']['movies_list'][current_movie_index][1]
                    shown_movie = meta['movies_on_tag_meta']['movies_list'][current_movie_index]
                    meta['movies_on_tag_meta']['shown_movie'] = shown_movie

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
                # TODO potentially might need to set first_interaction to TRUE
                elif user_response == '0':
                    response_text = "Great, I'll take you back to the recommendation menu, hope that is okay?"
                    self.movie_image_url = None
                    self.isPromptMessage = True
                else:
                    response_text = f"Based on the word you provided, I really think you'll enjoy {next_movie_title}." \
                                    f"Would you like to watch it now, or would you prefer a recommendation for another " \
                                    f"movie that's similar to the word provided? " \
                                    f"Please let me know by replying with 'yes' if you'd like to watch it, or 'no' if " \
                                    f"you'd like another recommendation or enter 0 to go back to the recommendation " \
                                    f"menu or type another descriptive word for different suggestions. 😁"

                    self.movie_image_url = image_url(next_movie_title)
            except IndexError:
                response_text = "No movie with a similar word found. Please try again with another descriptive word."

        return response_text


class RecommendMovieBasedOnGenreAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False
        self.isPromptMessage = True
        self.first_interaction = True
        self.genre = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):
        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMovieBasedOnGenreAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMovieBasedOnGenreAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 3 ")
        if (statement.text.strip() == '3' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
            self.active = True
            print(f"Debug: RecommendMovieBasedOnGenreAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 3 ")
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['similar_genre_meta']['recommended_movies_list']) > 0:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['similar_genre_meta']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['similar_genre_meta']['recommended_movies_list'].pop(0)
                    meta['similar_genre_meta']['movies_list'].clear()
                    meta['similar_genre_meta']['shown_movie'].clear()
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
                    meta['similar_genre_meta']['recommended_movies_list'].pop(0)
                    self.update_user_conversation_meta(user_conversation, meta)

            elif user_rating.isdigit() and int(user_rating) == 0:
                self.active = False
                response_text = f"Back to the main menu we go, Once you have finished watching, {recommended_movie[1]}, " \
                                f"Don't forget to provide a rating, pinky promise?! 🤞💖"
                self.movie_image_url = None
                self.first_interaction = True


            else:
                response_text = f"Please rate the movie {recommended_movie[1]} between (1-5) before getting more " \
                                f"recommendations or if you haven't watched the movie yet, 0 to go back to the main " \
                                f"menu. "
                self.movie_image_url = image_url(recommended_movie[1])
                self.first_interaction = False
        else:

            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            print(f"DEBUG: What is isPromptMessage value {self.isPromptMessage}")
            if self.isPromptMessage:
                self.isPromptMessage = False
                response_text = "Please enter one of the following genres (Adventure, Comedy, Action, Drama, Crime, " \
                                "Children, Mystery, Animation, Documentary, Thriller, Horror, Fantasy, Western, " \
                                "Film-Noir, Romance, Sci-Fi, Musical, War, IMAX) and I'll be able to suggest some " \
                                "movies I think you " \
                                "might enjoy that were " \
                                "made in that genre "
                self.movie_image_url = None
            else:
                meta = self.initialize_meta(user_conversation)
                meta, invalid_input = self.update_meta_based_on_user_input(meta, statement)
                print(f"This is meta after the update_meta function, showing meta: {meta}.")
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

        if 'similar_genre_meta' not in meta:
            meta['similar_genre_meta'] = {
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': [],
                'recommended_movies_list': [],
            }

        return meta

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'similar_genre_meta' in meta:
            meta['similar_genre_meta']['movies_list'].clear()
            meta['similar_genre_meta']['shown_movie'].clear()
            meta['similar_genre_meta']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def update_user_conversation_meta(self, user_conversation, meta):
        print("Before updating meta:", user_conversation[0].meta)
        user_conversation[0].meta = json.dumps(meta)
        print("After updating meta:", user_conversation[0].meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

    def update_meta_based_on_user_input(self, meta, statement):
        user_response = statement.text.strip().lower()
        genre = [genre.lower() for genre in list_of_genres()]
        invalid_input = False

        if user_response in genre:
            self.genre = user_response
            recommended_movies = recommend_movies_based_on_genre(self.genre, self.user_id)
            meta['similar_genre_meta']['movies_list'] = recommended_movies
            meta['similar_genre_meta']['current_movie_index'] = 0
        elif user_response == 'yes' and len(meta['similar_genre_meta']['movies_list']) > 0:
            meta['similar_genre_meta']['recommended_movies_list'].append(meta['similar_genre_meta']['shown_movie'])
        elif user_response == 'no' and len(meta['similar_genre_meta']['movies_list']) > 0:
            meta['similar_genre_meta']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['similar_genre_meta']['movies_list'].clear()
            meta['similar_genre_meta']['shown_movie'].clear()
            meta['similar_genre_meta']['current_movie_index'] = 0
        else:
            invalid_input = True

        print(f"Update meta based on user input {print(meta)}")
        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        global next_movie_title
        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['similar_genre_meta']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['similar_genre_meta']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more similar movie recommendations. Please enter another " \
                            "movie genre or enter 0 to go back to the recommendation menu."
            self.movie_image_url = None
            meta['similar_genre_meta']['current_movie_index'] = 0

        else:
            try:
                if len(meta['similar_genre_meta']['movies_list']) > 0:
                    next_movie_title = meta['similar_genre_meta']['movies_list'][current_movie_index][1]
                    shown_movie = meta['similar_genre_meta']['movies_list'][current_movie_index]
                    meta['similar_genre_meta']['shown_movie'] = shown_movie

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
                    response_text = f"Based on the genre you provided, I really think you'll enjoy {next_movie_title}." \
                                    f"Would you like to watch it now, or would you prefer a recommendation for another " \
                                    f"movie that's in a similar genre " \
                                    f"Please let me know by replying with 'yes' if you'd like to watch it, or 'no' if " \
                                    f"you'd like another recommendation or enter 0 to go back to the recommendation " \
                                    f"menu or type another movie title for different suggestions. 😁"

                    self.movie_image_url = image_url(next_movie_title)
            except IndexError:
                response_text = "No movie with a similar genre found. Please try again with another title"

        return response_text


class RecommendMoviesBasedOnYearAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.active = False
        self.isPromptMessage = True
        self.first_interaction = True
        self.year = 0

    def set_user_id(self, user_id):
        self.user_id = user_id

    @property
    def is_active(self):
        return self.active

    def can_process(self, statement):
        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMoviesBasedOnYearAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMoviesBasedOnYearAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 4 ")
        if (statement.text.strip() == '4' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
            self.active = True
            print(f"Debug: RecommendMoviesBasedOnYearAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 4 ")
        return False

    # TODO once a movie has been rated, if the user has logged out and atemptes to rate the movie again once they enter the adapter the movie is processed.
    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['similar_year_meta']['recommended_movies_list']) > 0:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['similar_year_meta']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['similar_year_meta']['recommended_movies_list'].pop(0)
                    meta['similar_year_meta']['movies_list'].clear()
                    meta['similar_year_meta']['shown_movie'].clear()
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
                    meta['similar_year_meta']['recommended_movies_list'].pop(0)
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
                response_text = "Please enter any year from (1902 - 2018) and I'll suggest some movies I think you " \
                                "might enjoy that were " \
                                "made in that year! "
                self.movie_image_url = None
            else:
                meta = self.initialize_meta(user_conversation)
                meta, invalid_input = self.update_meta_based_on_user_input(meta, statement)
                print(f"This is meta after the update_meta function, showing meta: {meta}.")
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

        if 'similar_year_meta' not in meta:
            meta['similar_year_meta'] = {
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': [],
                'recommended_movies_list': [],
            }

        return meta

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'similar_year_meta' in meta:
            meta['similar_year_meta']['movies_list'].clear()
            meta['similar_year_meta']['shown_movie'].clear()
            meta['similar_year_meta']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def update_user_conversation_meta(self, user_conversation, meta):
        print("Before updating meta:", user_conversation[0].meta)
        user_conversation[0].meta = json.dumps(meta)
        print("After updating meta:", user_conversation[0].meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)

    def update_meta_based_on_user_input(self, meta, statement):
        user_response = statement.text.strip().lower()
        invalid_input = False

        if user_response.isdigit() and 1902 <= int(user_response) <= 2018:
            self.year = int(user_response)
            recommended_movies = recommend_movies_based_on_year(self.year, self.user_id)
            meta['similar_year_meta']['movies_list'] = recommended_movies
            meta['similar_year_meta']['current_movie_index'] = 0
        elif user_response == 'yes' and len(meta['similar_year_meta']['movies_list']) > 0:
            meta['similar_year_meta']['recommended_movies_list'].append(meta['similar_year_meta']['shown_movie'])
        elif user_response == 'no' and len(meta['similar_year_meta']['movies_list']) > 0:
            meta['similar_year_meta']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['similar_year_meta']['movies_list'].clear()
            meta['similar_year_meta']['shown_movie'].clear()
            meta['similar_year_meta']['current_movie_index'] = 0
        else:
            invalid_input = True

        print(f"Update meta based on user input {print(meta)}")
        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        global next_movie_title
        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['similar_year_meta']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['similar_year_meta']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more similar movie recommendations. Please enter another " \
                            "movie title or enter 0 to go back to the recommendation menu."
            self.movie_image_url = None
            meta['similar_year_meta']['current_movie_index'] = 0

        else:
            try:
                if len(meta['similar_year_meta']['movies_list']) > 0:
                    next_movie_title = meta['similar_year_meta']['movies_list'][current_movie_index][1]
                    shown_movie = meta['similar_year_meta']['movies_list'][current_movie_index]
                    meta['similar_year_meta']['shown_movie'] = shown_movie

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


# TODO when I type 0 it changes the recommend movies list, it now does take me back to the recommendation list. However an it does not prompt me to enter title and the movie changes!
# TODO issue includes control flow, after I have rated a movie, I should be allowed to rate another movie straight away,but I am unable too as once I supply a title it takes me back to the menu. However this works after a rating has been accepted.


class RecommendMovieBasedOnSimilarTitleAdapter(LogicAdapter):

    def __init__(self, chatbot, **kwargs):
        super().__init__(chatbot, **kwargs)
        self.user_id = None
        self.movie_image_url = None
        self.first_interaction = True
        self.isPromptMessage = True
        self.active = False
        self.title = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):
        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMovieBasedOnSimilarTitleAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMovieBasedOnSimilarTitleAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 5 ")
        if (statement.text.strip() == '5' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
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

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'similar_title_meta' in meta:
            meta['similar_title_meta']['movies_list'].clear()
            meta['similar_title_meta']['shown_movie'].clear()
            meta['similar_title_meta']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

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
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': [],
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
        self.isPromptMessage = True
        self.active = False
        self.title = ''

    def set_user_id(self, user_id):
        self.user_id = user_id

    def can_process(self, statement):

        bridge_adapter_activate_status = False
        num_rated_movies = count_rated_movies_for_user(self.user_id)
        print(
            f"Debug: RecommendMoviesBasedOnUserAdapter can_process called, statement: {statement.text.strip()}, self.active: {self.active}")
        for adapter in self.chatbot.logic_adapters:
            if isinstance(adapter, BridgeLogicAdapter):
                bridge_adapter_activate_status = adapter.activate

            if hasattr(adapter, "is_active") and adapter.is_active:
                if isinstance(adapter, RecommendMoviesBasedOnUserAdapter) and adapter.is_active:
                    return True
                else:
                    return False

        print("Before the check to see if the input is equal to 6 ")
        if (statement.text.strip() == '6' and num_rated_movies >= 10) and not bridge_adapter_activate_status:
            self.active = True
            print(f"Debug: RecommendMovieBasedOnSimilarTitleAdapter can_process returning True")
            return True
        print("After the check to see if the input is equal to 6 ")
        return False

    def process(self, statement, additional_response_selection_parameters=None):
        print(
            f"Debug: RecommendMovieBasedOnSimilarUserAdapter process called, statement: {statement.text.strip()}, "
            f"self.active: {self.active}")
        user_conversation = self.get_or_create_user_conversation()
        self.store_user_input(statement)
        meta = self.initialize_meta(user_conversation)
        if len(meta['SimilarUsersRecommendation']['recommended_movies_list']) > 0 is not None:
            print(f"DEBUG: WE NEED TO CHECK ACTIVE STATUS: {self.active}")
            recommended_movie = meta['SimilarUsersRecommendation']['recommended_movies_list'][0]
            # Check if the user has provided a rating for the movie
            user_rating = statement.text.strip()
            print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
            if user_rating.isdigit() and 1 <= int(user_rating) <= 5 and not self.first_interaction:
                # Call the store_rating function to store the user's rating
                success = store_rating(self.user_id, recommended_movie[0], int(user_rating))

                if success:
                    # Remove the rated movie from the list and update the user_conversation meta
                    meta['SimilarUsersRecommendation']['recommended_movies_list'].pop(0)
                    meta['SimilarUsersRecommendation']['movies_list'].clear()
                    meta['SimilarUsersRecommendation']['shown_movie'].clear()
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
                    meta['SimilarUsersRecommendation']['recommended_movies_list'].pop(0)
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
                recommended_movies = recommend_movies_based_on_user(self.user_id)
                meta = self.initialize_meta(user_conversation)
                meta['SimilarUsersRecommendation']['current_movie_index'] = 0
                meta, invalid_input = self.update_meta_based_on_user_input(meta, statement, recommended_movies)
                response_text = self.generate_next_movie_recommendation(meta, statement, invalid_input)
                self.isPromptMessage = False
                self.update_user_conversation_meta(user_conversation, meta)
            else:
                print(f"DEBUG: printing first_interaction for testing purposes {self.first_interaction}")
                print(f"DEBUG: What is isPromptMessage value {self.isPromptMessage}")
                recommended_movies = recommend_movies_based_on_user(self.user_id)
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

    def reset(self):
        user_conversation = self.get_or_create_user_conversation()
        meta = self.initialize_meta(user_conversation)
        self.isPromptMessage = True
        self.active = False

        if 'SimilarUsersRecommendation' in meta:
            meta['SimilarUsersRecommendation']['movies_list'].clear()
            meta['SimilarUsersRecommendation']['shown_movie'].clear()
            meta['SimilarUsersRecommendation']['current_movie_index'] = 0

        self.update_user_conversation_meta(user_conversation, meta)

    def get_or_create_user_conversation(self):
        user_conversation = self.chatbot.storage.get_conversation(self.user_id)
        if not user_conversation:
            user_conversation = self.chatbot.storage.create_conversation(self.user_id)
        return user_conversation

    def store_user_input(self, statement):
        statement.conversation = f"user_id:{self.user_id}"
        self.chatbot.storage.update(statement)

    def initialize_meta(self, user_conversation):

        print(f"User conversation: {user_conversation}")
        meta = user_conversation[0].meta or "{}"
        print(f"Meta after initial assignment: {meta}")
        if not isinstance(meta, dict):
            meta = json.loads(meta)
            print(f"Meta after json.loads: {meta}")

        if 'SimilarUsersRecommendation' not in meta:
            meta['SimilarUsersRecommendation'] = {
                'movies_list': [],
                'current_movie_index': 0,
                'shown_movie': None,
                'recommended_movies_list': [],
            }

        return meta

    def update_meta_based_on_user_input(self, meta, statement, recommended_movies):
        invalid_input = False
        user_response = statement.text.strip().lower()
        movie_list = meta['SimilarUsersRecommendation']['movies_list']

        if len(movie_list) == 0:
            meta['SimilarUsersRecommendation']['movies_list'] = recommended_movies

        if self.isPromptMessage:
            pass
        elif user_response == 'yes' and len(meta['SimilarUsersRecommendation']['movies_list']) > 0:
            meta['SimilarUsersRecommendation']['recommended_movies_list'].append(
                meta['SimilarUsersRecommendation']['shown_movie'])
        elif user_response == 'no' and len(meta['SimilarUsersRecommendation']['movies_list']) > 0:
            meta['SimilarUsersRecommendation']['current_movie_index'] += 1
        elif user_response == '0':
            self.active = False
            meta['SimilarUsersRecommendation']['movies_list'].clear()
            meta['SimilarUsersRecommendation']['shown_movie'].clear()

        # TODO issue with this part of code as it does not allow me to enter an invalid input it simply never reaches
        #  the else statement BIG PROBLEM!
        else:
            invalid_input = True

        print(f"Update meta based on user input {print(meta)}")
        return meta, invalid_input

    def generate_next_movie_recommendation(self, meta, statement, invalid_input=False):

        user_response = statement.text.strip().lower()

        print("Meta data in generate_next_movie_recommendation:", meta)
        current_movie_index = meta['SimilarUsersRecommendation']['current_movie_index']
        print(
            f"checking if current_movie_index is correct in generate_next_movie_recommendation: {current_movie_index}")

        if current_movie_index >= len(meta['SimilarUsersRecommendation']['movies_list']) != 0:
            response_text = "I'm sorry, I don't have any more movies to recommend. Please rate more movies using the " \
                            "other recommendation suggestions and come back! "
            self.movie_image_url = None
            meta['SimilarUsersRecommendation']['current_movie_index'] = 0

        else:
            next_movie_title = ''

            if len(meta['SimilarUsersRecommendation']['movies_list']) > 0:
                next_movie_title = meta['SimilarUsersRecommendation']['movies_list'][current_movie_index][1]
                shown_movie = meta['SimilarUsersRecommendation']['movies_list'][current_movie_index]
                meta['SimilarUsersRecommendation']['shown_movie'] = shown_movie

                # TODO - Test this, see if once you say yes does it allow you to rate the movie then, does it allow
                #  you to suggest another movie title.

            if self.isPromptMessage:
                response_text = f"I plan on showing you the best movies, I think you would like based of similar " \
                                f"users to you ..." \
                                f"Here's the first one:  {next_movie_title}. Please let me know by replying with 'yes' " \
                                f"if you'd like to watch it, or 'no' if you'd like another recommendation "

                self.movie_image_url = image_url(next_movie_title)


            elif user_response == 'yes':
                response_text = 'Awesome, I''m so glad you loved my recommendation! I hope you enjoy watching the ' \
                                'movie. ' \
                                'Once you''re done watching, you''ll be promoted to rate the movie! Your feedback ' \
                                'is ' \
                                'valuable and will help me make even better suggestions in the future. '
                self.active = False
                self.movie_image_url = None
                self.isPromptMessage = True
            elif invalid_input:
                response_text = f"Sorry, I didn't understand that. Please reply with 'yes' or 'no' for {next_movie_title}" \
                                f" or 0 to go back to the recommendation menu."
                self.movie_image_url = None

                # TODO potentially might need to set first_interaction to TRUE
            elif user_response == '0':
                response_text = "Great, I'll take you back to the recommendation menu, hope that is okay?"
                self.movie_image_url = None
                self.isPromptMessage = True
            else:
                response_text = f"I really think you'll enjoy {next_movie_title}. Would you like to watch it now, " \
                                f"or would you prefer another recommendation? Please let me know by replying with " \
                                f"'yes' if you'd like to watch it, or 'no' if you'd like another recommendation, " \
                                f"or enter 0 to go back to the recommendation menu 😁"

                self.movie_image_url = image_url(next_movie_title)

        return response_text

    @property
    def is_active(self):
        return self.active

    def update_user_conversation_meta(self, user_conversation, meta):
        user_conversation[0].meta = json.dumps(meta)
        self.chatbot.storage.update_conversation(self.user_id, user_conversation)
