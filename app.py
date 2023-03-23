from System import app, db

# TODO need to get logic adapter working correctly
# TODO need to sort out view to index/chat correct
# TODO logic adapter should then wait for a rating from the user based for the given movie or if the user has not watched the suggested movie should process this to show the next movie in the list, iterating through this list until the user has rated 10 movies.


# from System.models import create_admin_account, Reading
#
# with app.app_context():
#
#     # Bind the declarative base to the engine
#     db.Model.metadata.bind = db.engine
#
#     # Reflect metadata from the database
#     db.Model.metadata.reflect()
# create_admin_account(email='gse@shangrilla.gov.un', password='gse@energy')

if __name__ == '__main__':
    app.run(debug=True)
