from chatterbot import ChatBot
from chatterbot.logic import LogicAdapter
from chatterbot.conversation import Statement
from System.RecommendationEngine.recommendationEngine import recommend_movies_based_on_year_and_genre, \
    recommend_movies_based_on_tags, recommend_movies_based_on_user, recommend_movie_based_on_similar_title, \
    recommend_movie_based_on_genre, recommend_movies_based_on_year
from chatbot_adapter import RecommendBySimilarTitleAdapter, RecommendByUserAdapter, RecommendByTagsAdapter, \
    RecommendByYearAdapter, RecommendByGenreAdapter, RecommendationByYearAndGenreAdapter

EMBEDDING_MODEL = "text-embedding-ada-002"

# Create a ChatBot instance and add the custom logic adapter
chatbot = ChatBot("BuddyBot")
chatbot.logic_adapters = [
    RecommendationByYearAndGenreAdapter(chatbot=chatbot), RecommendByYearAdapter(chatbot=chatbot),
    RecommendByGenreAdapter(chatbot=chatbot),
    RecommendByTagsAdapter(chatbot=chatbot), RecommendByUserAdapter(chatbot=chatbot),
    RecommendBySimilarTitleAdapter(chatbot=chatbot)
]


# Define a function to generate movie recommendations
def get_movie_recommendations(year, genre):
    user = 1  # Replace with an actual user ID
    recommended_movies = recommend_movies_based_on_year_and_genre(year, genre, user)
    return recommended_movies


# Start a conversation with the chatbot
while True:
    try:
        # Get a response from the chatbot
        user_input = input("You: ")
        response = chatbot.get_response(user_input)

        # If the chatbot prompted the user for movie preferences, generate recommendations
        if "What year and genre" in response.text:
            year = int(input("Year: "))
            genre = input("Genre: ")
            recommended_movies = get_movie_recommendations(year, genre)
            response = Statement("Here are some recommended movies: " + ", ".join(recommended_movies))

        # Print the chatbot's response
        print("Bot:", response)

    except (KeyboardInterrupt, EOFError, SystemExit):
        break
