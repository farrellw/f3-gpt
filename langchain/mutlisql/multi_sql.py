from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from langchain.chains.llm import LLMChain
from typing import List, Mapping

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
