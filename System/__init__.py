import mysql.connector

# Connect to the database
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)
cursor = mydb.cursor()
mydb.commit()
cursor.close()
mydb.close()
