# [START functions_slack_setup]
import os

import base64
from flask import jsonify
import functions_framework
import googleapiclient.discovery
import openai
import mysql.connector
import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, Decimal):
      return str(obj)
    return json.JSONEncoder.default(self, obj)


# Function to generate SQL query from input text using ChatGPT
def generate_sql_query(text):
    prompt = """You are a ChatGPT language model that can generate SQL queries. Please provide a natural language input text, and I will generate the corresponding SQL query for you. There are three tables. bd_attendance is one table that has four columns: user_id, date, ao_id, and q_user_id. The four columsn are described as such. The date column in bd_attendance is stored as YYYY-MM-DD. The ao_id references a record in the table `aos`, and its value is found under the column 'channel_id' within the table `aos`. That table aos also has a column called `ao`, which gives the human readable name of the ao_id/channel_id. The user_id and q_user_id columns within the bd_attendance are matched by the user_id in the table users, which table also contains a user_name which is a human readable name of the user_id. When possible, return user_name instead of user_id and ao instead of channel_id \nInput: {}\nSQL Query:""".format(text)

    request = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0301",
        messages=[
            {"role": "user", "content": prompt},
        ]
    )
    sql_query = request['choices'][0]['message']['content']
    return sql_query

# Function to execute SQL query on SQLite database
def execute_sql_query(cursor, query):
    cursor.execute(query)
    result = cursor.fetchall()
    return result

# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def worker(cloud_event):
    # Build our Slack Client to communicate back with the request
    slack_token = os.getenv("SLACK_TOKEN")
    client = WebClient(token=slack_token)
    
    # Parse incomign slack event data
    data = json.loads(base64.b64decode(cloud_event.data["message"]["data"]))

    # Retrieve the text.
    request_text = data["data"]["message"]["text"]
    channel_id = data["data"]["message"]["channel_id"]

    response = client.chat_postMessage(
        channel=channel_id,
        text=f'F3 GPT Acting on Input: {request_text}'
    )

    # Mark the threadID within the channel for threading future replies.
    ts = response["ts"]

    # Generate SQL Query if stats keyword exists
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


        response = client.chat_postMessage(
                channel=channel_id,
                text=f'SQL query Generated: {f3_gpt_response}',
                thread_ts=ts
            )

        result = execute_sql_query(cursor, f3_gpt_response)
        
        # Close database connection
        cursor.close()
        conn.close()

        try:
            response = client.chat_postMessage(
                channel=channel_id,
                text=f'Response: {json.dumps(result)}',
                thread_ts=ts
            )
        except Exception as e:
            response = client.chat_postMessage(
                channel=channel_id,
                text=f'Response: {json.dumps(result, cls=DecimalEncoder)}',
                thread_ts=ts
            )
    else:
        prompt = """You are a ChatGPT language model. In addition to your normal capabilities and ability to answer prompts, you specialize in acting as a personal trainer developing workouts. \nInput: {}""".format(request_text)

        request = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0301",
            messages=[
                {"role": "user", "content": prompt},
            ]
        )
        f3_gpt_response = request['choices'][0]['message']['content']    

        print(f3_gpt_response)

        response = client.chat_postMessage(
                channel=channel_id,
                text=f'Response: {f3_gpt_response}',
                thread_ts=ts
            )  
        
# [END functions_slack_search]
