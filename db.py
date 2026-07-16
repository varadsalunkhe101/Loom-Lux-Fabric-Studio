import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",          # Change if your MySQL has a password
        database="right_fabrics_db"
    )
    return connection