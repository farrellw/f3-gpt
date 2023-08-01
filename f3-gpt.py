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
    prompt = """You are a ChatGPT language model that can generate SQL queries. Please provide a natural language input text, and I will generate the corresponding SQL query for you. There is one view to query called attendance_view. The view itself is a record of attendance at workouts for an organization called "F3". Each time a user attends a workout, there is an entry in the table.It has columns Date, AO, PAX, Q. I'll define each column here.PAX is another name for user. So if a user was called "Catalina", then "Catalina" would be in the PAX column.Date is the date that the user/PAX attended the workout.AO is the location of the workout.Q is the user who led the workout.
    \nInput: {}\nSQL Query:""".format(text)
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

text="Who led the most workouts at ao_badlands_francis_park since January 1st of 2023?"

sql_query=generate_sql_query(text)
print("Generated SQL query: ",sql_query)
if sql_query:
    result=execute_sql_query(sql_query)
    print("ChatGPT Response=>",result)
    
# Close database connection
cursor.close()
conn.close()