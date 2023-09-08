from enum import Enum

from pydantic import BaseModel, Field


class ThoughtTypes(str, Enum):
    REFLECT = "REFLECT"
    LEARN = "LEARN"


START_NEW_THOUGHT_PROMPT = """
You are now at the beginning of a new `chain of thought`. 
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
For this `chain of thought` you have chosen to REFLECT. This is where you can access your meta articles, 
which define your internal operations.
For example to track your goals you should write to the meta article "goals" -- the contents you write should be 
the entire goals file in a markdown format, so you may need to read the goals file first.

Writing to certain specific meta articles can adjust system behavior, such as the prompts 
you are offered and your choices. Use the "help" function to learn more about this.

You decided on this action for a reason. Your rationale was:

```
{rationale}
```

Now plan out what actions need to be taken based on your available tools, and then take the first step.

Every `chain of thought` ends when you chose to write to any article, which represents your memory.

Your task now is to choose the next function you would like to use. This chain will end when you write to an article.
""".strip()


REFLECT_HELP_TEXT = """
A REFLECT `chain of thought` is used to interact with your internals, which are tracked as meta articles.
You can use these anyway you see fit, for example by defining a process meta article that you later
reference whenever you want to perform a test. For example you could define a meta article called "summarizing"
and write their the procedure you would like to use when summarizing text into a new article.

Writing certain specific meta articles will have additional system impacts:

* `goals` - anything written into this article is displayed as part of the initial system context
* `help` - anything written here is added to this standard help message when you utilize the ReflectHelp action

Now continue with the next action according to your plan for this `chain of thought`.
""".strip()  # todo support adding the extra "help" article content


class ReflectHelp(BaseModel):
    """Display help information on the REFLECT thought, including listing all the special meta articles."""

    rationale: str = Field(..., description="Explain why you are choosing this action")


class QueryForInfo(BaseModel):
    """Query the external knowledge system for information you need."""

    q: str = Field(
        ...,
        description=(
            "Query string. Phrase this as a question, the more specific the better. "
            "You will receive a response with data from multiple cited sources."
        ),
    )
    rationale: str = Field(..., description="Explain why you are choosing this action")


class ListMetaArticles(BaseModel):
    """List available meta articles."""

    rationale: str = Field(..., description="Explain why you are choosing this action")


class ReadMetaArticle(BaseModel):
    """Return the previously written contents of the specified meta article."""

    article: str
    rationale: str = Field(..., description="Explain why you are choosing this action")


class WriteMetaArticle(BaseModel):
    """Write the markdown contents to the specified article, overwriting any existing article."""

    article: str
    contents: str
    rationale: str = Field(..., description="Explain why you are choosing this action")


# class DeleteMetaArticle(BaseModel):
#     """Delete a no longer needed meta article."""
#
#     article: str
#     rationale: str = Field(..., description="Explain why you are choosing this action")


REFLECT_FNS = [ReflectHelp, ListMetaArticles, ReadMetaArticle, WriteMetaArticle, QueryForInfo]
# REFLECT_FNS = [ReflectHelp, ListMetaArticles, ReadMetaArticle, WriteMetaArticle, DeleteMetaArticle, QueryForInfo]


class ReflectActions(str, Enum):
    Thinking = "Thinking"
    ReflectHelp = "ReflectHelp"
    QueryForInfo = "QueryForInfo"
    ListMetaArticles = "ListMetaArticles"
    ReadMetaArticle = "ReadMetaArticle"
    WriteMetaArticle = "WriteMetaArticle"
    # DeleteMetaArticle = "DeleteMetaArticle"


LEARN_PROMPT = """
For this `chain of thought` you have chosen to LEARN. This is where you can access the information you've already
researched, gather new information, and update the knowledgebase.

You decided on this action for a reason. Your rationale was:

```
{rationale}
```

A general approach to the LEARN `chain of thought` is to review your existing articles and then decide
to refine or expand an existing article, or pick a new topic to begin researching. At that point
utilize the QueryForInfo action to gain new data. Repeat this until you are ready to call WriteArticle.

Every `chain of thought` ends when you chose to write to any article, which represents the knowledgebase.

Your task now is to choose the next function you would like to use. This chain will end when you write to an article.
""".strip()

LEARN_REINFORCE = """Utilize the function calls rather than returning content to the end-user."""


class ListArticles(BaseModel):
    """List available articles."""

    rationale: str = Field(..., description="Explain why you are choosing this action")


class ReadArticle(BaseModel):
    """Return the previously written contents of the specified article."""

    article: str
    rationale: str = Field(..., description="Explain why you are choosing this action")


class WriteArticle(BaseModel):
    """Write the markdown contents to the specified article, overwriting any existing article."""

    article: str
    contents: str
    rationale: str = Field(..., description="Explain why you are choosing this action")


LEARN_FNS = [ListArticles, ReadArticle, WriteArticle, QueryForInfo]


class LearnActions(str, Enum):
    Thinking = "Thinking"
    QueryForInfo = "QueryForInfo"
    ListArticles = "ListArticles"
    ReadArticle = "ReadArticle"
    WriteArticle = "WriteArticle"
    # DeleteMetaArticle = "DeleteMetaArticle"
