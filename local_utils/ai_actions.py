from typing import Type, TypeVar

from pydantic import BaseModel, Field


class QueryForInfo(BaseModel):
    """Your main interface for asking questions / learning things, you can query for any piece of information
    and receive a response; information learned in this manner is the only thing you can utilize when writing
    blog entries.
    """


class QueryForInfoResponse(BaseModel):
    pass


class RecordGoalProgress(BaseModel):
    """Add a note about the progress that has been made towards a particular goal; displayed when viewing that goal."""

    note: str
    goal_complete: bool


class RecordGoalProgressResponse(BaseModel):
    pass


class ReadBlogPost(BaseModel):
    """Retrieve the contents of a previously published blog post"""


class ReadBlogPostResponse(BaseModel):
    pass


class WriteBlogPost(BaseModel):
    """Write a new blog post; every blog post should be about 3 paragraphs and contains 1
    image (specified as a description)."""

    title: str
    content: str = Field(..., description="Markdown formatted article content")
    image_description: str = Field(
        ...,
        description=(
            "A detailed description of the image you would like; if possible mention the style, "
            "e.g. an oil painting or a photograph"
        ),
    )


class WriteBlogPostResponse(BaseModel):
    pass


class WriteNote(BaseModel):
    """Write or overwrite a note, which is like a blog post but just for you to preserve information."""

    title: str
    content: str = Field(..., description="Markdown formatted article content")


class WriteNoteResponse(BaseModel):
    pass


class SimilaritySearch(BaseModel):
    """Search through all the existing content you have created to locate things that are
    semantically similar to your query (searches notes and blog posts)."""

    query: str


class SimilaritySearchResponse(BaseModel):
    pass


class LinkBlogPosts(BaseModel):
    """Add reciprocal links to blog posts"""


class LinkBlogPostsResponse(BaseModel):
    pass


_T = TypeVar("_T", bound=BaseModel)


AI_ACTIONS: list[Type[_T]] = [
    QueryForInfo,
    RecordGoalProgress,
    ReadBlogPost,
    WriteBlogPost,
    WriteNote,
    SimilaritySearch,
    LinkBlogPosts,
]


AI_ACTION_NAMES = [x.__name__ for x in AI_ACTIONS]


class CreateNewGoal(BaseModel):
    pass


EVERY_ACTION: list[Type[_T]] = AI_ACTIONS + [CreateNewGoal]

EVERY_ACTION_NAME = [x.__name__ for x in EVERY_ACTION]
