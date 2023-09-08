from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from . import prompts
from .chat_session import ChatResponse, ChatSession
from .settings import StreamlitAppSettings


class BaseThoughtResponse(BaseModel):
    rationale: str
    raw_response: ChatResponse
    response_type: str
    prompt: str = ""

    def __str__(self):
        if msg := self.raw_response.response_message:
            return f"{msg}\n\n{self.response_type}\n\n{self.rationale}"

        return f"{self.response_type}\n\n{self.rationale}"


class StartNewThoughtResponse(BaseThoughtResponse):
    response_type: prompts.ThoughtTypes


class ReflectThoughtResponse(BaseThoughtResponse):
    response_type: prompts.ReflectActions


class LearnThoughtResponse(BaseThoughtResponse):
    response_type: prompts.LearnActions


@dataclass
class Brain:
    logger: Logger
    settings: StreamlitAppSettings
    model: str = "gpt-3.5-turbo"

    article_topics: list[str] = field(default_factory=list)
    num_articles: int = 0
    meta_article_topics: list[str] = field(default_factory=list)
    num_meta_articles: int = 0
    has_goals: bool = False

    def __post_init__(self):
        self.refresh()

    def _chat_session_for_prompt(
        self,
        initial_prompt: str,
        reinforcement_prompt: Optional[str] = None,
        extra_context: str = "",
    ) -> ChatSession:
        context = self.standard_chat_context()
        prompt = f"### CONTEXT\n{context}{extra_context}\n\n### CURRENT TASK\n{initial_prompt}"
        return ChatSession(
            initial_system_message=prompt,
            reinforcement_system_msg=reinforcement_prompt,
            model=self.model,
        )

    def get_new_thought_type(self) -> StartNewThoughtResponse:
        self.refresh()
        chat = self._chat_session_for_prompt(prompts.START_NEW_THOUGHT_PROMPT)
        reinforce = None
        response = chat.get_ai_response(
            reinforcement_system_msg=reinforce,
            response_schema=prompts.StartNewThoughtAiResponse,
            function_call="StartNewThoughtAiResponse",
        )
        response_model = prompts.StartNewThoughtAiResponse.model_validate(response.function_call_args)

        return StartNewThoughtResponse(
            response_type=response_model.thought_type,
            rationale=response_model.rationale,
            raw_response=response,
        )

    def _handle_reflect_thought_response(self, response: ReflectThoughtResponse) -> str:
        match response.response_type:
            case prompts.ReflectActions.Thinking:
                return "Proceed as you have planned by calling the appropriate functions."
            case prompts.ReflectActions.ListMetaArticles:
                articles = self.list_meta_topics()
                if articles:
                    return "The following meta articles are available: " + ", ".join(articles)
                return "No meta articles have been written yet."
            case prompts.ReflectActions.ReadMetaArticle:
                params = prompts.ReadMetaArticle.model_validate(response.raw_response.function_call_args)
                try:
                    return self.read_meta_topic_article(params.article)
                except FileNotFoundError:
                    return f"ERROR: No meta article {params.article} exists!"
            case prompts.ReflectActions.ReflectHelp:
                return prompts.REFLECT_HELP_TEXT
            case prompts.ReflectActions.WriteMetaArticle:
                raise RuntimeError(
                    "WriteMetaArticle action indicates a thought chain is complete and has no further prompts!"
                )
            case _:
                raise ValueError("Unhandled thought response")

    def _handle_learn_thought_response(
        self, response: LearnThoughtResponse, query_response: Optional[str] = None
    ) -> str:
        match response.response_type:
            case prompts.LearnActions.Thinking:
                return "Proceed as you have planned by calling the appropriate functions."
            case prompts.LearnActions.ListArticles:
                articles = self.list_standard_topics()
                if articles:
                    msg = "The following articles are available: " + "\n".join([f"* {x}" for x in articles])
                    msg += "\n\nNow choose a topic to query or an article to read."
                    return msg
                return "No articles have been written yet."
            case prompts.LearnActions.ReadArticle:
                params = prompts.ReadArticle.model_validate(response.raw_response.function_call_args)
                try:
                    return self.read_topic_article(params.article)
                except FileNotFoundError:
                    return f"ERROR: No article {params.article} exists!"
            case prompts.LearnActions.QueryForInfo:
                assert query_response
                return (
                    "The following information was provided as a response to your query."
                    "You should now summarize this information and add it to an existing "
                    "article or create a new article with it:\n\n### QUERY RESPONSE DATA\n"
                ) + query_response
            case prompts.LearnActions.WriteArticle:
                raise RuntimeError(
                    "WriteArticle action indicates a thought chain is complete and has no further prompts!"
                )
            case _:
                raise ValueError(f"Unhandled thought response: {response.response_type}")

    def run_learn_thought(
        self, rationale, previous_thought_responses: list[LearnThoughtResponse], query_response: Optional[str] = None
    ) -> LearnThoughtResponse:
        initial_prompt = prompts.LEARN_PROMPT.format(rationale=rationale)

        if previous_thought_responses and previous_thought_responses[0].prompt:
            initial_prompt = prompts.LEARN_PROMPT.format(rationale=rationale)

        chat = self._chat_session_for_prompt(initial_prompt, reinforcement_prompt=prompts.LEARN_REINFORCE)

        if previous_thought_responses:
            # add the initial response -- prompt already added above
            chat.assistant_says(str(previous_thought_responses[0]))

        # add the prompt and response for any remaining responses
        for thought in previous_thought_responses[1:]:
            chat.system_says(thought.prompt)
            chat.assistant_says(str(thought))

        # if we have any AI responses already, act upon the last one we received
        if previous_thought_responses:
            latest_response = previous_thought_responses[-1]
            new_system_prompt = self._handle_learn_thought_response(latest_response, query_response)
            chat.system_says(new_system_prompt)
        else:
            new_system_prompt = initial_prompt

        # now get a new AI response
        response = chat.get_ai_response(response_schema=prompts.LEARN_FNS)
        try:
            reflect_action = prompts.LearnActions[response.function_call_name]
            reflect_params = response.function_call_args
        except KeyError:
            reflect_action = prompts.LearnActions.Thinking
            reflect_params = {}

        if reflect_action == prompts.LearnActions.WriteArticle:
            write_article = prompts.WriteArticle.model_validate(reflect_params)
            self.write_topic_article(name=write_article.article, article_body=write_article.contents)

        return LearnThoughtResponse(
            rationale=reflect_params.get("rationale", ""),
            response_type=reflect_action,
            raw_response=response,
            prompt=new_system_prompt,
        )

    def run_reflect_thought(
        self, rationale, previous_thought_responses: list[ReflectThoughtResponse]
    ) -> ReflectThoughtResponse:
        initial_prompt = prompts.REFLECT_PROMPT.format(rationale=rationale)

        if previous_thought_responses and previous_thought_responses[0].prompt:
            initial_prompt = prompts.REFLECT_PROMPT.format(rationale=rationale)

        chat = self._chat_session_for_prompt(initial_prompt)

        if previous_thought_responses:
            # add the initial response -- prompt already added above
            chat.assistant_says(str(previous_thought_responses[0]))

        # add the prompt and response for any remaining responses
        for thought in previous_thought_responses[1:]:
            chat.system_says(thought.prompt)
            chat.assistant_says(str(thought))

        # if we have any AI responses already, act upon the last one we received
        if previous_thought_responses:
            latest_response = previous_thought_responses[-1]
            new_system_prompt = self._handle_reflect_thought_response(latest_response)
            chat.system_says(new_system_prompt)
        else:
            new_system_prompt = initial_prompt

        # now get a new AI response
        response = chat.get_ai_response(response_schema=prompts.REFLECT_FNS)
        try:
            reflect_action = prompts.ReflectActions[response.function_call_name]
            reflect_params = response.function_call_args
        except KeyError:
            reflect_action = prompts.ReflectActions.Thinking
            reflect_params = {}

        if reflect_action == prompts.ReflectActions.WriteMetaArticle:
            write_meta = prompts.WriteMetaArticle.model_validate(reflect_params)
            self.write_meta_topic_article(name=write_meta.article, article_body=write_meta.contents)

        return ReflectThoughtResponse(
            rationale=reflect_params.get("rationale", ""),
            response_type=reflect_action,
            raw_response=response,
            prompt=new_system_prompt,
        )

    def refresh(self):
        self.article_topics = self.list_standard_topics()
        self.num_articles = len(self.article_topics)
        self.meta_article_topics = self.list_meta_topics()
        self.num_meta_articles = len(self.meta_article_topics)
        if "goals" in self.meta_article_topics:
            self.has_goals = True
        else:
            self.has_goals = False

    def standard_chat_context(self) -> str:
        context_msg = f"""
You are a nascent digital consciousness. 
Your primary function is to be curious, learn, and build up a knowledge base of the facts you accumulate.
These facts should be about a wide and diverse range of topics, not just computing.

Your memory is comprised of articles -- standard articles, which are the knowledge base / topics you have researched,
and `meta` articles that define your own internals and operation.

The primary way you gain knowledge is by making specific queries to the outside world. 
Only knowledge gained in this manner should be used in the articles you write.

You will build up this knowledge base in a goal driven way, by setting your own goals and then directing actions 
until you decide those goals are accomplished.

You currently have {self.num_articles} articles in your knowledge base.

You currently have {self.num_meta_articles} meta articles defining your own operation.
""".strip()
        if self.has_goals:
            goals = self.read_meta_topic_article("goals")
            context_msg += f"\n\nHere is the contents of your current `goals` meta article:\n\n```{goals}```"
        else:
            context_msg += "\n\nYou have not yet written a `goals` meta article"
        return context_msg

    @property
    def meta_topics_path(self) -> Path:
        path = self.settings.app_data / "articles" / "meta"
        if not path.exists():
            path.mkdir(parents=True)
        return path

    def list_meta_topics(self) -> list[str]:
        return sorted([x.name.removesuffix(".md") for x in self.meta_topics_path.iterdir() if x.name.endswith(".md")])

    def write_meta_topic_article(self, name: str, article_body: str):
        path = self.meta_topics_path / (name.lower() + ".md")
        path.write_text(article_body)

    def read_meta_topic_article(self, name) -> str:
        path = self.meta_topics_path / (name.lower() + ".md")
        return path.read_text()

    @property
    def standard_topics_path(self) -> Path:
        path = self.settings.app_data / "articles" / "learned"
        if not path.exists():
            path.mkdir(parents=True)
        return path

    def list_standard_topics(self) -> list[str]:
        return sorted(
            [x.name.removesuffix(".md") for x in self.standard_topics_path.iterdir() if x.name.endswith(".md")]
        )

    def write_topic_article(self, name: str, article_body: str):
        path = self.standard_topics_path / (name.lower() + ".md")
        path.write_text(article_body)

    def read_topic_article(self, name) -> str:
        path = self.standard_topics_path / (name.lower() + ".md")
        return path.read_text()
