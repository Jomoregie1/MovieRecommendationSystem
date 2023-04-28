from flask import Flask, render_template, request, session, jsonify, Blueprint, make_response
from flask_login import current_user
from sqlalchemy.orm import sessionmaker
from System.RecommendationEngine.recommendationEngine import recommend_movies_to_rate_for_new_users
from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer
from chatterbot.conversation import Statement
from System.Chatbot.logicadapter import UserConversationLogicAdapter, BridgeLogicAdapter, \
    RecommendMoviesBasedOnUserAdapter, RecommendMovieBasedOnSimilarTitleAdapter, RecommendMovieBasedOnGenreAdapter, \
    RecommendMoviesBasedOnTagAdapter, RecommendMoviesBasedOnYearAdapter, RecommendMoviesBasedOnYearAndGenreAdapter

bot = Blueprint('chatbot', __name__)

chatbot = ChatBot(
    'Buddy',
    storage_adapter='System.Chatbot.logicadapter.CustomSQLStorageAdapter',
    database_uri='mysql+mysqlconnector://root:root@localhost:3306/chatbot',
    logic_adapters=[
        {
            'import_path': 'System.Chatbot.logicadapter.UserConversationLogicAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.BridgeLogicAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMoviesBasedOnYearAndGenreAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMoviesBasedOnTagAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMovieBasedOnGenreAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMoviesBasedOnYearAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMovieBasedOnSimilarTitleAdapter',
        },
        {
            'import_path': 'System.Chatbot.logicadapter.RecommendMoviesBasedOnUserAdapter',
        }
    ]
)
trainer = ChatterBotCorpusTrainer(chatbot)
trainer.train('chatterbot.corpus.english')

print("Logic Adapters:", chatbot.logic_adapters)


def reset_adapters(chatbot):
    for adapter in chatbot.logic_adapters:
        if hasattr(adapter, 'reset'):
            adapter.reset()


def get_first_matching_adapter(adapters, statement):
    for adapter in adapters:
        print(f"Debug: Checking if {adapter.__class__.__name__} can process the statement: {statement}")
        if adapter.can_process(statement):
            print(f"Debug: {adapter.__class__.__name__} can process the statement: {statement}")
            return adapter
    return None


def get_response_and_image_url(chatbot, user_message, conversation, user_id):
    chatbot.set_user_id_for_adapters(user_id)

    chatbot_response = None
    movie_image_url = None
    movie_image_url_adapters = (
        UserConversationLogicAdapter,
        RecommendMoviesBasedOnYearAndGenreAdapter,
        RecommendMoviesBasedOnTagAdapter,
        RecommendMovieBasedOnGenreAdapter,
        RecommendMoviesBasedOnYearAdapter,
        RecommendMovieBasedOnSimilarTitleAdapter,
        RecommendMoviesBasedOnUserAdapter,
    )

    # Create a Statement object with the user_message
    statement = Statement(user_message)

    # Find the first matching adapter
    matching_adapter = get_first_matching_adapter(chatbot.logic_adapters, statement)

    if matching_adapter is not None:
        # Process the statement with the matching adapter
        response = matching_adapter.process(statement, additional_response_selection_parameters={
            'conversation': conversation})

        if isinstance(matching_adapter, movie_image_url_adapters):
            if hasattr(matching_adapter, 'movie_image_url') and matching_adapter.movie_image_url is not None:
                movie_image_url = matching_adapter.movie_image_url
                print(f"Adapter {type(matching_adapter).__name__} movie_image_url: {movie_image_url}")

        chatbot_response = response.text

    return chatbot_response, movie_image_url


@bot.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_id = current_user.get_id()  # Get the current user ID from Flask-Login

        # Get the user's message from the request data
        user_message = request.form.get('message')

        print(user_message)

        # Create a new conversation or get an existing one for the user
        conversation = chatbot.storage.get_conversation(user_id)
        if not conversation:
            conversation = chatbot.storage.create_conversation(user_id)

        chatbot_response, movie_image_url = get_response_and_image_url(chatbot, user_message, conversation, user_id)

        print(f"Chatbot response: {str(chatbot_response)}")

        return jsonify({'status': 'success', 'response': str(chatbot_response), 'movie_image_url': movie_image_url})

    return render_template('index.html')
