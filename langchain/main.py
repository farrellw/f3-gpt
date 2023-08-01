from langchain.llms import OpenAI
from langchain.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts.prompt import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

db = SQLDatabase.from_uri(os.getenv("FULL_CONNECTION_URI"))
llm = OpenAI(temperature=0, verbose=True)

_DEFAULT_TEMPLATE = """Given an input question, first create a syntactically correct msyql query to run, then look at the results of the query and return the answer.
Use the following format:

Question: "Question here"
SQLQuery: "SQL Query to run"
SQLResult: "Result of the SQLQuery"
Answer: "Final answer here"

There is one view to query called attendance_view. The view itself is a record of attendance at workouts for an organization called "F3". Each time a user attends a workout, there is an entry in the table.It has columns Date, AO, PAX, Q. I'll define each column here.PAX is another name for user. So if a user was called "Catalina", then "Catalina" would be in the PAX column.Date is the date that the user/PAX attended the workout.AO is the location of the workout ( The current locations are blackops, ao_backyard_tower_grove, ao_bunker_lindenwood_park, ao_battery_lafayette_park, ao_badlands_francis_park, ao_bear_pit_carondelet_park, qsource, rucking, ao_southside_shuffle_tilles_park, ao_brickyard_turtle_park, c25k. More locations may be added later, but for example if someone says bear pit they mean ao_bear_pit_carondelet_park ). Q is the user who led the workout. Because the table is attendance, if ten PAX attended a workout on the same day, the Q would be the same for all ten of these user entries. However it was a single workout, so when counting times a user led a workout take the concatenation of date and Q.

Question: {input}"""
PROMPT = PromptTemplate(
    input_variables=["input"], template=_DEFAULT_TEMPLATE
)

db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True, prompt = PROMPT, use_query_checker=True)

r = db_chain.run("How many PAX are there?")