import mysql.connector


def connect_db():
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="movierecommendation"
    )
    return mydb


db_connection_string_mr = "mysql+mysqlconnector://root:root@localhost:3306/movierecommendation"
db_connection_string_cb = "mysql+mysqlconnector://root:root@localhost:3306/chatbot"
