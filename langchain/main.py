from langchain.llms import OpenAI
from langchain.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts.prompt import PromptTemplate
from dotenv import load_dotenv
import json
import os

from multisql.multi_sql import MultiSqlChain
from multisql.multi_sql import MULTI_SQL_ROUTER_TEMPLATE

from langchain.llms import OpenAI
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.chains.router.llm_router import LLMRouterChain, RouterOutputParser
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE

load_dotenv()

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

# r = chain("What was the date, location, and actual workout of 'Rabbit' first Q?")
print(chain.run("What was the date, location, and actual workout of 'Rabbit' first Q?"))
# print(r)

# print(chain.run("How many workouts has Rabbit attended?"))

# print(chain.run("What are good warmup stretches to avoid getting inHow many workouts has Rabbit attended?"))