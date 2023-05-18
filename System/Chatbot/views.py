from flask import render_template, request, jsonify, Blueprint
from flask_login import current_user
from chatterbot import ChatBot
from chatterbot.conversation import Statement
from System.models import User
from System.decorators import non_admin_required

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

def reset_adapters(chatbot):
    for adapter in chatbot.logic_adapters:
        if hasattr(adapter, 'reset'):
            adapter.reset()


def get_first_matching_adapter(adapters, statement):
    for adapter in adapters:
        if adapter.can_process(statement):
            return adapter
    return None


def get_response_and_image_url(chatbot, user_message, conversation, user_id):
    from System.Chatbot.logicadapter import UserConversationLogicAdapter, \
        RecommendMoviesBasedOnUserAdapter, RecommendMovieBasedOnSimilarTitleAdapter, RecommendMovieBasedOnGenreAdapter, \
        RecommendMoviesBasedOnTagAdapter, RecommendMoviesBasedOnYearAdapter, RecommendMoviesBasedOnYearAndGenreAdapter

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

        chatbot_response = response.text

    return chatbot_response, movie_image_url


@bot.route('/', methods=['GET', 'POST'])
@non_admin_required
def chat():

    global user_name

    if request.method == 'POST':
        user_id = current_user.get_id()  # Get the current user ID from Flask-Login

        user = User.query.get(user_id)
        user_name = user.first_name

        # Get the user's message from the request data
        user_message = request.form.get('message')

        # Create a new conversation or get an existing one for the user
        conversation = chatbot.storage.get_conversation(user_id)
        if not conversation:
            conversation = chatbot.storage.create_conversation(user_id)

        chatbot_response, movie_image_url = get_response_and_image_url(chatbot, user_message, conversation, user_id)

        return jsonify({'status': 'success', 'response': str(chatbot_response), 'movie_image_url': movie_image_url})

    return render_template('index.html', user_name=user_name)
