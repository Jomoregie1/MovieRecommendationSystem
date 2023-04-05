from flask import Flask, render_template, request, session, jsonify, Blueprint, make_response
from flask_login import current_user
from sqlalchemy.orm import sessionmaker

from System.RecommendationEngine.recommendationEngine import recommend_movies_to_rate_for_new_users
from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer
from chatterbot.conversation import Statement
from System.Chatbot.logicadapter import UserConversationLogicAdapter, CustomSQLStorageAdapter

bot = Blueprint('chatbot', __name__)

chatbot = ChatBot(
    'Buddy',
    storage_adapter='System.Chatbot.logicadapter.CustomSQLStorageAdapter',  # Update this line
    database_uri='mysql+mysqlconnector://root:root@localhost:3306/chatbot',
    logic_adapters=[
        {
            'import_path': 'System.Chatbot.logicadapter.UserConversationLogicAdapter',
            'USER_CONVERSATION_LOGIC_ADAPTER': 'System.Chatbot.logicadapter.UserConversationLogicAdapter'
        }
    ]
)

trainer = ChatterBotCorpusTrainer(chatbot)
trainer.train('chatterbot.corpus.english')


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

        chatbot_response = None
        movie_image_url = None
        for adapter in chatbot.logic_adapters:
            if isinstance(adapter, UserConversationLogicAdapter):
                adapter.set_user_id(user_id)
                chatbot_response = chatbot.get_response(user_message, additional_response_selection_parameters={
                    'conversation': conversation})
                movie_image_url = adapter.movie_image_url
                break

        print(f"Chatbot response: {str(chatbot_response)}")  # Add this line

        return jsonify({'status': 'success', 'response': str(chatbot_response), 'movie_image_url': movie_image_url})

    return render_template('index.html')
