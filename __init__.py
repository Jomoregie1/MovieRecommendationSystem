import mysql.connector

from RecommendationEngine.recommendationEngine import combined_data

# Connect to the database
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movierecommendation"
)
cursor = mydb.cursor()

for index, row in combined_data.iterrows():
    sql = "INSERT INTO ratings (userId, movieId,rating) VALUES (%s,%s, %s)"
    values = (row['userId'], row['movieId'], row['rating'])
    cursor.execute(sql, values)

print("finished executing........................................")

mydb.commit()
cursor.close()
mydb.close()
