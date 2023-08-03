# [START functions_slack_setup]
import os

import base64
from flask import jsonify
import functions_framework
import googleapiclient.discovery
import openai
import mysql.connector
import json

from langchain.llms import OpenAI
from langchain.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts.prompt import PromptTemplate

from langchain.chains import ConversationChain
from langchain.chains.router.llm_router import LLMRouterChain, RouterOutputParser
from langchain.chains.router.base import MultiRouteChain, RouterChain
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from langchain.chains.llm import LLMChain
from typing import List, Mapping

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from decimal import Decimal

MULTI_SQL_ROUTER_TEMPLATE = """
Given a raw text input to a language model select the model prompt best suited for
the input. You will be given the names of the available prompts and a description of
what the prompt is best suited for.

<< FORMATTING >>
Return a markdown code snippet with a JSON object formatted to look like:
```json
{{{{
    "destination": string \\ name of the prompt to use or "DEFAULT"
    "next_inputs": string \\ the original input
}}}}
```

REMEMBER: "destination" MUST be one of the candidate prompt names specified below OR
it can be "DEFAULT" if the input is not well suited for any of the candidate prompts.
REMEMBER: "next_inputs" can just be the original input

<< CANDIDATE PROMPTS >>
{destinations}

<< INPUT >>
{{input}}

<< OUTPUT >>
"""

class MultiSqlChain(MultiRouteChain):
    """A multi-route chain that uses an LLM router chain to choose amongst SQL chains."""

    router_chain: RouterChain
    """Chain for deciding a destination chain and the input to it."""
    destination_chains: Mapping[str, SQLDatabaseChain]
    """Map of name to candidate chains that inputs can be routed to."""
    default_chain: LLMChain
    """Default chain to use when router doesn't map input to one of the destinations."""

    @property
    def output_keys(self) -> List[str]:
        return ["text"]
    

class DecimalEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, Decimal):
      return str(obj)
    return json.JSONEncoder.default(self, obj)
  

def generate_prompt_1(text): 
   prompt = """You are a ChatGPT language model that can generate SQL queries. Please provide a natural language input text, and I will generate the corresponding SQL query for you. There is one view to query called attendance_view. The view itself is a record of attendance at workouts for an organization called "F3". Each time a user attends a workout, there is an entry in the table.It has columns Date, AO, PAX, Q. I'll define each column here.PAX is another name for user. So if a user was called "Catalina", then "Catalina" would be in the PAX column.Date is the date that the user/PAX attended the workout.AO is the location of the workout ( The current locations are blackops, ao_backyard_tower_grove, ao_bunker_lindenwood_park, ao_battery_lafayette_park, ao_badlands_francis_park, ao_bear_pit_carondelet_park, qsource, rucking, ao_southside_shuffle_tilles_park, ao_brickyard_turtle_park, c25k. More locations may be added later, but for example if someone says bear pit they mean ao_bear_pit_carondelet_park ). Q is the user who led the workout. Because the table is attendance, if ten PAX attended a workout on the same day, the Q would be the same for all ten of these user entries. However it was a single workout, so when counting times a user led a workout take the concatenation of date and Q.
    \nInput: {}\nSQL Query:""".format(text)
   return prompt


def generate_prompt_2(prompt_1, response, sql_results):
   prompt = """
   I started with the following prompt: {}\nyou responded with: {}. After executing the SQL query I received {}. Can you turn the response into a more human readable and conversational response.
    """.format(prompt_1, response, sql_results)
   return prompt
   
# Function to generate SQL query from input text using ChatGPT
def generate_sql_query(text):
    prompt = generate_prompt_1(text)

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

def langchang_implementation(input):
    db = SQLDatabase.from_uri(os.getenv("FULL_CONNECTION_URI"), max_string_length=10000)
    llm = OpenAI(temperature=0, verbose=True)

    backblast_template = """Given an input question, first create a syntactically correct msyql query to run, then look at the results of the query and return the answer.
    Use the following format:

    Question: "Question here"
    SQLQuery: "SQL Query to run"
    SQLResult: "Result of the SQLQuery"
    Answer: "Final answer here"

    The view to query is called backblast. This view contains the following columns: Date, AO, Q, pax_count, fngs, and backblast. The date is formatted as YYYY-MM-DD. The AO is the location of the workout ( The current locations are blackops, ao_backyard_tower_grove, ao_bunker_lindenwood_park, ao_battery_lafayette_park, ao_badlands_francis_park, ao_bear_pit_carondelet_park, qsource, rucking, ao_southside_shuffle_tilles_park, ao_brickyard_turtle_park, c25k. More locations may be added later, but for example if someone says bear pit they mean ao_bear_pit_carondelet_park ). Q is the user who led the workout. pax_count is how many people attended the workout. fngs contains plaintext information if any new guys came to the workout. backblast column contains the text of what actually happened at the workout. Return the whole backblast information found in the backblast column.

    Question:{input}"""

    attendance_template = """Given an input question, first create a syntactically correct msyql query to run, then look at the results of the query and return the answer.
    Use the following format:

    Question: "Question here"
    SQLQuery: "SQL Query to run"
    SQLResult: "Result of the SQLQuery"
    Answer: "Final answer here"

    There is one view called attendance_view. The view itself is a record of attendance at workouts for an organization called "F3". Each time a user attends a workout, there is an entry in the table. It has columns Date, AO, PAX, Q. I'll define each column here. PAX is another name for user. So if a user was called "Catalina", then "Catalina" would be in the PAX column.Date is the date that the user/PAX attended the workout. AO is the location of the workout ( The current locations are blackops, ao_backyard_tower_grove, ao_bunker_lindenwood_park, ao_battery_lafayette_park, ao_badlands_francis_park, ao_bear_pit_carondelet_park, qsource, rucking, ao_southside_shuffle_tilles_park, ao_brickyard_turtle_park, c25k. More locations may be added later, but for example if someone says bear pit they mean ao_bear_pit_carondelet_park ). Q is the user who led the workout. Because the table is attendance, if ten PAX attended a workout on the same day, the Q would be the same for all ten of these user entries. However it was a single workout, so when counting times a user led a workout take the concatenation of date and Q. 

    Question:{input}"""


    prompt_infos = [
        {
            "name": "backblast",
            "description": "Good for answering questions about what happened at previous workouts",
            "prompt_template": backblast_template,
            "return_direct": True
        },
        {
            "name": "workout_attendance",
            "description": "Good for answering questions about how many workouts a person has attended, how many a person has led/Q'd",
            "prompt_template": attendance_template,
            "return_direct": False
        },
    ]

    destinations = [f"{p['name']}: {p['description']}" for p in prompt_infos]
    destinations_str = "\n".join(destinations)
    router_template = MULTI_SQL_ROUTER_TEMPLATE.format(
        destinations=destinations_str
    )
    router_prompt = PromptTemplate(
        template=router_template,
        input_variables=["input"],
        output_parser=RouterOutputParser(next_inputs_inner_key="input"),
    )
    router_chain = LLMRouterChain.from_llm(llm, router_prompt)

    destination_chains = {}
    for p_info in prompt_infos:
        name = p_info["name"]
        prompt_template = p_info["prompt_template"]
        prompt = PromptTemplate(template=prompt_template,
                                input_variables=["input"],
                                )
        chain = SQLDatabaseChain.from_llm(llm, db, prompt=prompt,
                                            output_key="text",
                                            # verbose=True,
                                            input_key="input",
                                            return_direct=p_info["return_direct"],
                                            return_intermediate_steps=True
                                            )
        destination_chains[name] = chain
    _default_chain = ConversationChain(llm=llm, output_key="text")

    chain = MultiSqlChain(
        router_chain=router_chain,
        destination_chains=destination_chains,
        default_chain=_default_chain,
        verbose=True,
    )
    
    return chain.run(input)

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

        prompt_1 = generate_prompt_1(request_text)

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
            result_as_json = json.dumps(result)
        except Exception as e:
            result_as_json = json.dumps(result, cls=DecimalEncoder)


        response = client.chat_postMessage(
            channel=channel_id,
            text=f'DB Response: {result_as_json}',
            thread_ts=ts
        )

        rrr = generate_prompt_2(prompt_1, f3_gpt_response, result_as_json)

        request = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0301",
        messages=[
            {"role": "user", "content": rrr},
        ])
        
        human_readable = request['choices'][0]['message']['content']
    
        response = client.chat_postMessage(
            channel=channel_id,
            text=human_readable,
            thread_ts=ts
        )
    else:
        r = langchang_implementation(request_text)
        print(r)
        response = client.chat_postMessage(
            channel=channel_id,
            text=r,
            thread_ts=ts
        )
        
        
# [END functions_slack_search]
