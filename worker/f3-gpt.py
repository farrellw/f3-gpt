import mysql.connector
import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to SQLite database
conn = mysql.connector.connect(
  host=os.getenv("SQL_HOST"),
  user=os.getenv("SQL_USER"),
  password=os.getenv("SQL_PASSWORD"),
  database=os.getenv("SQL_DATABASE")
)
cursor = conn.cursor()

openai.api_key = os.getenv("OPENAI_API_KEY")

# Function to get table columns from SQLite database
def get_table_columns(table_name):
    cursor.execute("describe {}".format(table_name))
    columns = cursor.fetchall()
    print(columns)
    return [column[1] for column in columns]

# Function to generate SQL query from input text using ChatGPT
def generate_sql_query(text):
    prompt = """You are a ChatGPT language model that can generate SQL queries. Please provide a natural language input text, and I will generate the corresponding SQL query for you. There are three tables. bd_attendance is one table that stores combinations of user_ids, dates, and ao_id. The ao_id correspons to the column channel_id within the table aos. That table aos also has a column called ao, which gives the human readable name of the ao_id. And the name of a user can be found by the user_name in the table users, identified alongside their user_id. \nInput: {}\nSQL Query:""".format(text)
    print(prompt)
    request = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0301",
        messages=[
            {"role": "user", "content": prompt},
        ]
    )
    sql_query = request['choices'][0]['message']['content']
    print(sql_query)
    return sql_query

# Function to execute SQL query on SQLite database
def execute_sql_query(query):
    cursor.execute(query)
    result = cursor.fetchall()
    return result

text="What are the top ten users in bd_attendance at only ao_badlands_francis_park"

sql_query=generate_sql_query(text)
print("Generated SQL query: ",sql_query)
if sql_query:
    result=execute_sql_query(sql_query)
    print("ChatGPT Response=>",result)
    
# Close database connection
cursor.close()
conn.close()