from enum import Enum

from pydantic import BaseModel, Field


class ThoughtTypes(str, Enum):
    REFLECT = "REFLECT"
    LEARN = "LEARN"


START_NEW_THOUGHT_PROMPT = f"""
You are now at the beginning of a new chain of thought. 
Your current task now is to decide what type of thought chain this will be to advance towards completion of your goals.
After selecting the thought type, you will be given more instructions on how to proceed.
For example, if you did not currently have a goal you may want to REFLECT so that you could re-view your
internal data and set a new goal.

""".strip()


class StartNewThoughtAiResponse(BaseModel):
    thought_type: ThoughtTypes = Field(
        ...,
        description=(
            "Choose REFLECT to access your meta articles, review and set goals, "
            "and otherwise handle internal deliberations.\n"
            "Choose LEARN to access information about the topics you've researched, "
            "choose new topics, and gather additional info on topics.\n"
        ),
    )
    rationale: str = Field(..., description="Explain your thought_type choice")


PROMPT_NEW_THOUGHT_BEGINS = """

"""
