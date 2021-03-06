import requests
from flask import Flask, request, jsonify
import json
import time, os
import psycopg2

app = Flask(__name__)
config_table = 'config'
query_table = 'unresponsed_queries'


def database_do(action='None', userid='None', auth_tok='None', query='None'):

    try:
        con = psycopg2.connect(os.environ["DATABASE_URL"], sslmode='require')
        cur = con.cursor()

        # force copy_init_config when table not present.
        cur.execute("select exists(select * from information_schema.tables where table_name=%s)", (config_table,))

        if cur.fetchone()[0] is False:
            print('Table not present, forcing create new table..')
            action = 'copy_init_config'

        print('Invoking', action, 'for userid', userid, 'with auth_token', auth_tok)

        if action == 'get_auth':
            cur.execute("SELECT * FROM "+ config_table +" WHERE userid = '" + userid + "'")

            while True:
                row = cur.fetchone()

                if row == None:
                    print('auth_tok is', auth_tok)
                    break
                auth_tok = str(row[0])
                print("Fetching auth_tok... {} ".format(auth_tok))

        elif action == 'update_uid':
            cur.execute("SELECT * FROM "+ config_table +" WHERE auth_tok = '" + str(auth_tok) + "'")
            cur.execute("UPDATE "+ config_table +" SET userid='" + userid + "' WHERE auth_tok='" + str(auth_tok) + "'")
            con.commit()
            print("Linked {} with {}".format(auth_tok, userid))

        elif action == 'copy_init_config':
            cur.execute("select exists(select * from information_schema.tables where table_name=%s)", (config_table,))

            if cur.fetchone()[0] is False:
                print("created new table named {}".format(config_table))
                cur.execute("CREATE TABLE "+ config_table +"(auth_tok INT PRIMARY KEY, userid VARCHAR(200))")

            cur.execute("DELETE FROM "+ config_table +" WHERE auth_tok='" + str(auth_tok) + "'")
            cur.execute("INSERT INTO "+ config_table +" VALUES('" + str(auth_tok) + "','" +  userid + "')")
            con.commit()
            print("Inserted {} in {}".format(auth_tok, config_table))

        elif action == 'unresponsed_query':
            cur.execute("select exists(select * from information_schema.tables where table_name=%s)", (query_table,))

            if cur.fetchone()[0] is False:
                print("created new table named {}".format(query_table))
                cur.execute("CREATE TABLE " + query_table + "(query VARCHAR(500) PRIMARY KEY)")

            cur.execute("INSERT INTO " + query_table + " VALUES('" + query + "')")
            con.commit()
            print("Inserted {} in {}".format(query, query_table))

    except psycopg2.DatabaseError as e:
        if con:
            con.rollback()

        print ('Error %s' % e  )

    finally:
        if con:
            con.close()

            if action == 'get_auth':
                return str(auth_tok)

def return_text(text):
    response = {'payload': {
                'google': {
                'expectUserResponse': 'true',
                'richResponse': {
                    'items': [
                    {
                        'simpleResponse': {
                        'textToSpeech': text
                        }
                    }
                    ]
                }
                }
            }
            }
    return str(response)


@app.route("/", methods=["POST", "GET"])
def process_df_api():
    # get dialog-flow's POST request and send a POST request to the client side.
    if request.method == "GET":
        return "Heroku GOT a request", 200

    if request.method == "POST":
        if request.authorization["username"] != os.environ['post_usr'] or request.authorization["password"] != os.environ['post_pwd']:
            return "authentication failure", 401

        default_POST_response = "GOT a DF API POST request."
        json_request = request.get_json()
        print('\n', json_request, '\n')

        if 'action' not in json_request['queryResult']:
            return return_text('Request not understood. Try again..'), 200

        elif json_request['queryResult']['action'] == 'input.unknown':
            database_do(action='unresponsed_query', query=json_request['queryResult']['queryText'])

        elif json_request['queryResult']['action'] == 'authenticate':
            auth_tok = str(json_request['queryResult']['parameters']['auth_tok'])
            userid = json_request['originalDetectIntentRequest']['payload']['user']['userId']

            if auth_tok != '':
                database_do(action='update_uid', auth_tok=auth_tok, userid=userid)
                return return_text("I have added the authentication token {}".format(" ".join(list(str(auth_tok))))), 200

            else:
                print("Wont link empty keys")

        else:
            userid = json_request['originalDetectIntentRequest']['payload']['user']['userId']
            auth_tok = database_do(action='get_auth', userid=userid)

            if auth_tok is 'None':
                return return_text('You are not authenticated. Try saying authenticate me.'), 200
            url = 'https://' + auth_tok + '.serveo.net'
            headers = {'content-type': 'application/json'}

            query = json_request['queryResult']['queryText']
            parameters = json_request['queryResult']['parameters']
            action = json_request['queryResult']['action']

            print("Sending query {} with params {} and action {} to {}".format(query, parameters, action, url))
            requests.post(url=url, data=json.dumps(json_request), headers=headers)

        return return_text(json_request['queryResult']['fulfillmentText']), 200


@app.route("/config", methods=["POST"])
def process_config():

    # saves the POSTED user configuration in conf folder
    if request.method == "POST":
        print(request, "request")
        config = request.get_json()

        print(config)
        database_do(action='copy_init_config', auth_tok=config['auth_tok'])

        return "saved the new configuration", 200

if __name__ == '__main__':
    app.run(debug = True)
