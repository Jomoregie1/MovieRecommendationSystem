from System import app, db

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
