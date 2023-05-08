import mysql.connector


def connect_db():
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="movierecommendation"
    )
    return mydb
