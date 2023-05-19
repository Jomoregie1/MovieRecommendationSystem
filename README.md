# Movie Recommendation Chatbot System

This repository contains a chatbot that can provide movie recommendations based on user's preferences.

## Features
- Real-time movie recommendations
- Uses advanced NLP models to understand user preferences
- Conversational interface for easy and natural interactions
- Trained on a large dataset for better and diverse recommendations
- High performance with low latency

## Setup and Installation
To use this chatbot, you need to have Python 3.7 or later installed on your system.

1. **Clone the Repository:**

```bash
git clone https://campus.cs.le.ac.uk/gitlab/jo181/MovieRecommendationSystem.git
```
2. **Navigate to the project directory:**

```bash
cd MovieRecommendationSystem
```
3. **Install Dependencies:**

The project requires several Python libraries. 
These dependencies are listed in the `requirements.txt` file. 
You can install them using pip:

```bash
pip install -r requirements.txt
```
Please note that some libraries may require additional system dependencies. You may also need to download specific language models for some libraries like Spacy.

## Usage

After installing the dependencies, you can run the application by running:
```bash
python app.py
```
Follow the instructions in the terminal to open the application to the correct port.

## Running Tests

This project contains unit tests that you can run to verify the functionality of the chatbot and recommendation system. Tests are located in the MovieRecommendationSystem/test directory.

You can run the tests as follows:

1. Navigate to the test directory:

```bash
cd MovieRecommendationSystem/test
```
2. Run the chatbot Test:

```bash
python chatbot_test.py
```
3. Run the Recommendation System Test:

```bash
python recommendation_system_test.py
```
These tests should pass without any errors if everything is set up correctly. If you encounter any errors while running these tests, please create an issue in the project repository.

Please replace the paths with the correct ones if the project's structure is different.

## Database Setup

The project uses two databases: `chatbot_DB` and `MovieRecommendation_DB`. Both databases are provided as SQL dumps in ZIP files. You need to import these dumps into your local MySQL database system.

1. Download Database Dumps:

Download the ZIP files containing the SQL dumps of `chatbot_DB` and `MovieRecommendation_DB`.

2. Import Databases:

Unzip the files and import them into your MySQL database system. If you are using MySQL Workbench, you can do this by going to `Server > Data Import`. Then, select Import from `Self-Contained File` and choose the SQL file.

3. Replace Database Connection String:

In your project, look for the line where the database connection strings are defined, this should be located in `database.py`

```bash
db_connection_string_mr = "mysql+mysqlconnector://root:root@localhost:3306/movierecommendation"
db_connection_string_cb = "mysql+mysqlconnector://root:root@localhost:3306/chatbot"
```
Replace `root:root` with your MySQL username and password. Replace `localhost:3306` with your MySQL host and port if they are different. If you imported the databases with different names, replace `movierecommendation` with the name of your database.

Now, your project should be connected to your local databases.

Note: Make sure to keep your database connection string confidential, and avoid pushing it to public repositories for security reasons.


