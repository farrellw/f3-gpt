# [START functions_slack_setup]
import os

import base64
import requests
from flask import jsonify
import functions_framework
import googleapiclient.discovery
import openai
import mysql.connector
import json

from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, Decimal):
      return str(obj)
    return json.JSONEncoder.default(self, obj)

# [START functions_slack_format]
def format_slack_message(thingToRespond):

    message = {
        "response_type": "in_channel",
        "text": thingToRespond,
        "attachments": [],
    }
    return message


# [END functions_slack_format]


# [START generate_sql_query]
# Function to generate SQL query from input text using ChatGPT
def generate_sql_query(text):
    prompt = """You are a ChatGPT language model that can generate SQL queries. Please provide a natural language input text, and I will generate the corresponding SQL query for you. There are three tables. bd_attendance is one table that stores combinations of user_id, date, and ao_id. The date column in bd_attendance is stored as YYYY-MM-DD. The ao_id corresponds to the column channel_id within the table aos. That table aos also has a column called ao, which gives the human readable name of the ao_id. And the name of a user can be found by the user_name in the table users, identified alongside their user_id. \nInput: {}\nSQL Query:""".format(text)

    request = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0301",
        messages=[
            {"role": "user", "content": prompt},
        ]
    )
    sql_query = request['choices'][0]['message']['content']
    return sql_query


# [END functions_slack_request]

# Function to execute SQL query on SQLite database
def execute_sql_query(cursor, query):
    cursor.execute(query)
    result = cursor.fetchall()
    return result

# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def worker(cloud_event):
    print(cloud_event)
    data = json.loads(base64.b64decode(cloud_event.data["message"]["data"]))

    # Print out the data from Pub/Sub, to prove that it worked
    request_text = data["data"]["message"]["text"]
    response_url = data["data"]["message"]["url"]

    print(request_text)
    print(response_url)
    if "[stats]" in request_text.lower():
        # Connect to SQLite database
        conn = mysql.connector.connect(
            host=os.getenv("SQL_HOST"),
            user=os.getenv("SQL_USER"),
            password=os.getenv("SQL_PASSWORD"),
            database=os.getenv("SQL_DATABASE")
        )
        cursor = conn.cursor()    

        f3_gpt_response = generate_sql_query(request_text)

        r = requests.post(response_url, data=json.dumps(format_slack_message(f3_gpt_response)))
        print(r)

        result=execute_sql_query(cursor, f3_gpt_response)
        
        response = format_slack_message(result)

        print("Slack response=>",response)

        # Close database connection
        cursor.close()
        conn.close()

        print("Sending message back now")
        
        r2 = requests.post(response_url, data=json.dumps(response, cls=DecimalEncoder))
        print(r2)
    else:
        prompt = """You are a ChatGPT language model with knowledge of the F3 Workout Group and can act as a personal trainer developing workouts. \nInput: {}""".format(request_text)

        request = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0301",
            messages=[
                {"role": "user", "content": prompt},
            ]
        )
        f3_gpt_response = request['choices'][0]['message']['content']    

        print(f3_gpt_response)
        
        requests.post(response_url, data=json.dumps(format_slack_message(f3_gpt_response)))
    
    


# [END functions_slack_search]
