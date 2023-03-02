from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer
from chatterbot.conversation import Statement
from System import mydb

chatbot = ChatBot('Buddy', storage_adapter='chatterbot.storage.SQLStorageAdapter'
                  , database_uri='mysql+mysqlconnector://root:root@localhost:3306/chatbot'
                  , logic_adapters=[{

    }])


