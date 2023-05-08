from System import app
from System.models import create_admin_account

# TODO WHEN REFACTORING CODE PLEASE IMPLEMENT APPLICATION FACTORY PATTERN
# TODO NEED TO REFACTOR CODE IN RECOMMENDATION ENGINE TO FOLLOW OPP PRINCIPALS AND CLEAN CODE PRINCIPALS
# TODO NEED TO REFACTOR CODE IN LOGIC ADAPTER TO FOLLOW SOLID PRINCIPALS
# TODO TAKES A WHILE TO LOGOUT (NEED TO FIGURE OUT A QUICKER WAY TO ACCOMPLISH THAT.
# TODO remember to remove the comments from chatterbot.py


# from System.models import create_admin_account, Reading

if __name__ == '__main__':
    app.run(debug=True)
