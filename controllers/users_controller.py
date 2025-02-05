
from flask import Flask, request, send_from_directory
from flask_restplus import Api, Resource, fields, inputs
from minimal import sfa_app
import pyodbc as p
from senhas import *
import secrets
from datetime import date,timedelta
from werkzeug.security import generate_password_hash,check_password_hash
from validator_collection import validators, errors

#########################################################################################
# Importing import sfa_app from minimal.py and storing in local variables
#########################################################################################

APP, SFA = sfa_app.app,sfa_app.api
# self.api =>> to configure all the API components - the routes, endpoints, methods, etc.
# self.app =>> deals with the application - checking in which door it is running, the rates, user login, etc.
# sfa_app ==> objet of the class API

#################################################################################################################
#
#   v0.3.0 - Version 3 - Contains one endpoint that allows user registration (HTTP Request Type -> POST)
#
##################################################################################################################


#########################################################################################
# First step => Creating a new namespace: users
#########################################################################################

users_namespace = SFA.namespace('Users', description='User operations')

# Here we create a namespace for users' operations.
# Namespaces are intended for organising REST endpoints within the API.

#########################################################################################
# Creating user model
#########################################################################################

user_model_request = SFA.model("user model",{
    'First Name': fields.String,
    'Last Name': fields.String,
    'email': fields.String,
    'Password': fields.String})

user_model_response = SFA.model("response",{'API Key': fields.String,'Expiration Date':fields.String} )

#############################################################################################
# Here we place the namespace decorator .route to define the endpoint path within the API
#############################################################################################
@users_namespace.route('/api/v1/register', doc={"description": 'user authentication'})
class Registration(Resource):
    # Resources are built on top of Flask pluggable views, giving you easy access to multiple HTTP methods
    # Here are the response methods, the possible responses in the documentation:
    @users_namespace.response(200, 'Success')
    @users_namespace.response(400, 'Request Error')
    @users_namespace.response(500, 'Server Error')
    @users_namespace.marshal_with(user_model_response)
    @users_namespace.expect(user_model_request)

    #################################################################################################################
    #
    #   ==> Decorator marshal_with() : will show the response model on swagger
    #       Note -> It will check if the function created on the endpoint respects the model.
    #
    #   ==> Decorator expect(): allows you to specify the expected input fields in the endpoint.
    #       Note -> It will show in swagger the file it is expecting to receive
    ##################################################################################################################

    def post(self):
        # Variable new user receives a dictionary. I'll use it to insert values into the DB.
        new_user=request.get_json()

        #####################################################################################################
        # ==>> OWASP C5: Validate All Inputs
        # ==>> OWASP C10: Handle All Errors and Exceptions
        #
        # NOTE: Here we use try-except statement for input validation.
        #####################################################################################################

        try:
            new_user["email"] = validators.email(new_user["email"])
            new_user["First Name"] = validators.not_empty(new_user["First Name"])
            new_user["Last Name"] = validators.not_empty(new_user["Last Name"])
        except errors.EmptyValueError:
            print("Missing Input")
            return {"Error:": "Missing Input"}, 422 # Unprocessable Entity
        except errors.InvalidEmailError:  # More handling logic goes here
            print("Invalid Input")
            return {"Error:": "Invalid Input"}, 422 # Unprocessable Entity

        #########################################################################################################
        # ==> OWASP C6: Implement Digital Identity (Level 1 : Passwords)
        #
        # NOTE: Blocking the top 1000 most common passwords and determinining password length
        # We ensure that the password created by the user is not amongst the most commonly used passwords
        #########################################################################################################

        with open("useful/common_passwords") as data:
            linhas = data.readlines()
        senhas_comuns = [senha.split("\n")[0] for senha in linhas]
        if new_user['Password'] in senhas_comuns or len(new_user['Password']) < 8:
            return {"Error:": "Invalid Password. Too weak!"}, 422 # Unprocessable entity

        # NOTICE ==>> We used with open() to open the file. Could also be:  data = open("useful/common_passwords")"
        # We don’t have to write “file.close()”. That will automatically be called.

        ############################################################################################################
        # ==>> OWASP C6:Implement Digital Identity
        # NOTE: We use libraries werkzeug (for password hashing) and secrets (to generate authentication key).
        #
        # ==>> C7: Enforce Access Controls
        #  The multi-factor authentication in 2 layers of protection: hashing passwords and authentication key.
        #  Here the authentication key is following these rules:
        #  a) expiration date – SFA-API has an expiration date, which is done using pyodbc;
        #  b) user IP – The system creates a key that corresponds the client’s IP.
        ############################################################################################################

        # Using library Secrets to generate the API Key with 30 byte token:
        apikey=secrets.token_urlsafe(30)
        # Creating an expiration date of the APY Key
        expiration_date=date.today()+ timedelta(days=30)
        # Variable to store is a certain user is blocked or not
        is_blocked=False
        # Capturing the IP from where the request comes from
        access_ip=request.remote_addr
        # Before storing the IP, it is necessary to see if it is in the list
        password_hash= generate_password_hash(new_user['Password'])
        # to check is the password is correct what we do is: check_password_hash(hash," - senha recebida p/ verificação - ")

        #########################################################################################################
        # ==> OWASP C3:Secure Database Access
        #
        # NOTE: Here we comply with OWASP by securing the access to the database considering:
        # a) Secure queries: To protect against SQL injection we use ‘Query Parameterization’
        # b) Secure configuration: we run the database in a docker container, which has connectivity restrictions
        # c) Secure communication: we use Pyodbc, an open source Python module to communicate with the database.
        #
        #########################################################################################################

        """User Registration"""
        cnxn = p.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='
                         +username+';PWD='+ password)
        cursor = cnxn.cursor()
        sql = f""" INSERT INTO TB_SFA_Registration (Reg_Name,Reg_LastName,Reg_Email,Reg_Authentication_Key,
        Reg_Password,Reg_Expiration_Date,Reg_Last_Access_Ip,Reg_Is_Blocked) 
        values (?,?,?,?,?,?,?,?)"""
        # Base query ==>> this is a generic query. The real data will be in the "???????"
        cursor.execute(sql, (new_user['First Name'],new_user['Last Name'],new_user['email'],apikey,
                             password_hash,expiration_date,access_ip,is_blocked))
        cursor.commit() # To execute the command. (note: .commit is needed because here we're making changes in the DB)
        return {"API Key": apikey,"Expiration Date":expiration_date}, 200 # Success

