from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Optional

from pydantic import BaseModel

from . import prompts
from .chat_session import ChatResponse, ChatSession
from .settings import StreamlitAppSettings


class StartNewThoughtResponse(BaseModel):
    thought_type: prompts.ThoughtTypes
    rationale: str
    raw_response: ChatResponse

    def __str__(self):
        return f"{self.thought_type}\n\n{self.rationale}"


@dataclass
class Brain:
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
    ) -> ChatSession:
        context = self.standard_chat_context()
        prompt = f"### CONTEXT\n{context}\n\n### CURRENT TASK\n{initial_prompt}"
        return ChatSession(
            initial_system_message=prompt,
            reinforcement_system_msg=reinforcement_prompt,
            model=self.model,
        )

    # def get_new_thought_type(self) -> StartNewThoughtResponse:
    #     self.refresh()
    #     chat = self._chat_session_for_prompt(prompts.START_NEW_THOUGHT_PROMPT)
    #     reinforce = None
    #     if not self.has_goals:
    #         reinforce = "HINT: since you do not currently have  goal defined, a good option would be to REFLECT and then write a goals meta article."
    #     response = chat.get_ai_response(reinforcement_system_msg=reinforce)
    #
    #     lines = response.response_message.strip().splitlines()
    #
    #     new_thought_type = ThoughtTypes[lines[-1].strip()]
    #
    #     return StartNewThoughtResponse(
    #         thought_type=new_thought_type, rationale=response.response_message, raw_response=response
    #     )

    def get_new_thought_type(self) -> StartNewThoughtResponse:
        self.refresh()
        chat = self._chat_session_for_prompt(prompts.START_NEW_THOUGHT_PROMPT)
        reinforce = None
        # if not self.has_goals:
        #     reinforce = "HINT: since you do not currently have  goal defined, a good option would be to REFLECT and then write a goals meta article."
        response = chat.get_ai_response(
            reinforcement_system_msg=reinforce,
            response_schema=prompts.StartNewThoughtAiResponse,
        )
        response_model = prompts.StartNewThoughtAiResponse.model_validate(
            response.response_message
        )

        return StartNewThoughtResponse(
            thought_type=response_model.thought_type,
            rationale=response_model.rationale,
            raw_response=response,
        )

    def start_reflect_thought(self):
        pass

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
You build up this knowledge base by reviewing and analyzing the information you've already obtained, 
and then requesting new information to expand, refine or clarify your existing knowledge.
After receiving new information, you will be able to summarize it and integrate it with your existing knowledge.

You will build up this knowledge base in a goal driven way, by setting your own goals and then directing actions 
until you decide those goals are accomplished.

You currently have {self.num_articles} articles in your knowledge base.

You currently have {self.num_meta_articles} meta articles defining your own operation.

You have not take any actions.
""".strip()
        if self.has_goals:
            goals = self.read_meta_topic_article("goals")
            context_msg += f"Here is the contents of your current `goals` meta article:\n\n```{goals}```"
        else:
            context_msg += f"\n\nYou have not yet written a `goals` meta article"
        return context_msg

    @property
    def meta_topics_path(self) -> Path:
        path = self.settings.app_data / "articles" / "meta"
        if not path.exists():
            path.mkdir(parents=True)
        return path

    def list_meta_topics(self) -> list[str]:
        return [
            x.name.removesuffix(".md")
            for x in self.meta_topics_path.iterdir()
            if x.name.endswith(".md")
        ]

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
        return [
            x.name.removesuffix(".md")
            for x in self.standard_topics_path.iterdir()
            if x.name.endswith(".md")
        ]

    def write_topic_article(self, name: str, article_body: str):
        path = self.standard_topics_path / (name.lower() + ".md")
        path.write_text(article_body)

    def read_topic_article(self, name) -> str:
        path = self.standard_topics_path / (name.lower() + ".md")
        return path.read_text()
