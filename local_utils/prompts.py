from enum import Enum

from pydantic import BaseModel, Field


class ThoughtTypes(str, Enum):
    REFLECT = "REFLECT"
    LEARN = "LEARN"


START_NEW_THOUGHT_PROMPT = """
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


REFLECT_PROMPT = """
You have chosen to REFLECT. This is where you can access your meta articles, which define your internal operations.
For example to track your goals you should write to the meta article "goals" -- the contents you write should be 
the entire goals file in a markdown format, so you may need to read the goals file first.

Writing to certain specific meta articles can adjust system behavior, such as the prompts 
you are offered and your choices. Use the "help" function to learn more about this.

You decided on this action for a reason. Now plan out what actions need to be taken, 
and then take the first step towards achieving the goal.

Every chain of thought ends when you chose to write to any article, which represents your memory.

Your task now is to choose the next function you would like to use. This chain will end when you write to an article.
"""


class QueryForInfo(BaseModel):
    """Query the external knowledge system for information."""

    q: str = Field(
        ...,
        description=(
            "Query string. Phrase this as a question, the more specific the better. "
            "You will receive a response with data from multiple cited sources."
        ),
    )


class ListMetaArticle(BaseModel):
    """List available meta articles."""


class ReadMetaArticle(BaseModel):
    """Return the previously written contents of the specified meta article."""

    article: str


class WriteMetaArticle(BaseModel):
    """Write the markdown contents to the specified article, overwriting any existing."""

    article: str
    contents: str
