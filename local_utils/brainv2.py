import json
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from logging import Logger
from pathlib import Path
from textwrap import dedent
from typing import Callable, Optional, Type, TypeVar

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from . import ai_actions
from .helpers import date_id
from .v2 import prompts
from .v2.chat_completion import get_completion
from .v2.image_gen import generate_image
from .v2.personas import Persona, PersonaManager
from .v2.thoughts import NewThoughtData, PlanStep, Thought, ThoughtMemory, UpdateThoughtData


class GoalProgress(BaseModel):
    note: str
    added_at: datetime


class CreateNewGoal(BaseModel):
    text: str
    rationale: str


class Goal(BaseModel):
    goal_id: str = Field(default_factory=date_id)
    text: str
    rationale: str
    added_at: datetime
    completed_at: Optional[datetime] = None
    goal_progress: list[GoalProgress]


_T = TypeVar("_T", bound=BaseModel)


class TaskStep(BaseModel):
    action_name: str | Type[_T]
    rationale: str

    @field_validator("action_name")
    @classmethod
    def validate_action_name(cls, value: str | Type[_T]) -> str:
        if not isinstance(value, str) and issubclass(value, BaseModel):
            value = value.__name__
        if value not in ai_actions.EVERY_ACTION_NAME:
            raise ValueError(f"Invalid action: {value}; must be one of {', '.join(ai_actions.EVERY_ACTION_NAME)}")
        return value


class ActionResult(BaseModel):
    action_name: str


TaskStep(action_name=ai_actions.CreateNewGoal, rationale="")


class PlanATask(BaseModel):
    text: str
    rationale: str
    plan: list[TaskStep] = Field(..., max_items=15)


class Task(BaseModel):
    task_id: str = Field(default_factory=date_id)
    text: str
    rationale: str
    plan: list[TaskStep] = Field(..., max_items=15)
    action_result: list[ActionResult] = Field(default_factory=list)


class GeneratedArt(BaseModel):
    persona_name: str
    date_added: datetime
    title: str
    art_descr: str
    thought_id: str

    def get_file_name(self) -> str:
        return md5(self.art_descr.encode()).hexdigest() + ".jpeg"


class JournalEntry(BaseModel):
    persona_name: str
    date_added: datetime
    content: str
    thought_id: str


class BlogEntry(BaseModel):
    persona_name: str
    date_added: datetime
    title: str
    byline: str
    content: str
    image_descr: str
    thought_id: str

    def format(self) -> str:
        formatted = f"""
            # {self.title}
            
            *Written by: {self.byline}*
            
            Date: {self.date_added.isoformat()}
            
            Image: {self.image_descr}
            
            {self.content}
        """
        return dedent(formatted)


class ArtworkDoesNotExist(RuntimeError):
    def __init__(self, msg):
        self.msg = msg


@dataclass
class GoalMemoryInterface(ABC):
    @abstractmethod
    def write_art_piece(self, persona_name: str, title: str, art_descr: str, thought_id: str) -> GeneratedArt:
        pass

    @abstractmethod
    def write_art_contents(self, art: GeneratedArt, contents: bytes):
        pass

    @abstractmethod
    def read_art_contents(self, art: GeneratedArt) -> bytes:
        pass

    @abstractmethod
    def get_latest_art_pieces(self, persona_name: Optional[str] = None, num: int = 3) -> list[GeneratedArt]:
        pass

    @abstractmethod
    def write_journal_entry(self, persona_name: str, content: str, thought_id: str) -> JournalEntry:
        pass

    @abstractmethod
    def get_latest_journal_entries(self, persona_name: Optional[str] = None, num: int = 3) -> list[JournalEntry]:
        pass

    @abstractmethod
    def write_blog_entry(
        self, persona_name: str, title: str, byline: str, image_descr: str, content: str, thought_id: str
    ) -> BlogEntry:
        pass

    @abstractmethod
    def get_latest_blog_entries(self, persona_name: Optional[str] = None, num: int = 3) -> list[BlogEntry]:
        pass

    # @abstractmethod
    # def list_goals(self, include_completed=False) -> list[Goal]:
    #     pass
    #
    # @abstractmethod
    # def get_goal(self, goal_id: str) -> Optional[Goal]:
    #     pass
    #
    # @abstractmethod
    # def save_new_goal(self, new_goal: CreateNewGoal) -> Goal:
    #     pass


@dataclass()
class MappingMemory(GoalMemoryInterface):
    art_storage: Path
    memory: MutableMapping[str, dict | list[dict]] = field(default_factory=dict)

    def write_art_piece(self, persona_name: str, title: str, art_descr: str, thought_id: str) -> GeneratedArt:
        entry = GeneratedArt(
            persona_name=persona_name,
            title=title,
            art_descr=art_descr,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
        )
        art_storage = self.memory.get("art_storage") or []
        art_storage.append(entry.model_dump())
        self.memory["art_storage"] = art_storage

        return entry

    def write_art_contents(self, art: GeneratedArt, contents: bytes):
        artwork_path = self.art_storage / art.persona_name / art.get_file_name()
        artwork_path.parent.mkdir(parents=True, exist_ok=True)
        if artwork_path.exists():
            raise RuntimeError("Artwork already exists")
        artwork_path.write_bytes(contents)

    def read_art_contents(self, art: GeneratedArt) -> bytes:
        artwork_path = self.art_storage / art.persona_name / art.get_file_name()
        if not artwork_path.exists():
            raise ArtworkDoesNotExist("Artwork contents file does not exist")
        return artwork_path.read_bytes()

    def get_latest_art_pieces(self, persona_name: Optional[str] = None, num: int = 5) -> list[GeneratedArt]:
        art_storage = self.memory.get("art_storage") or []
        return_entries = []
        for entry in art_storage[::-1]:
            entry = GeneratedArt.model_validate(entry)
            if persona_name and entry.persona_name != persona_name:
                continue
            return_entries.append(entry)
            if len(return_entries) == num:
                break
        return return_entries

    def write_journal_entry(self, persona_name: str, content: str, thought_id: str) -> JournalEntry:
        entry = JournalEntry(
            persona_name=persona_name, content=content, date_added=datetime.utcnow(), thought_id=thought_id
        )
        journal = self.memory.get("journal") or []
        journal.append(entry.model_dump())
        self.memory["journal"] = journal
        return entry

    def get_latest_journal_entries(self, persona_name: Optional[str] = None, num: int = 5) -> list[JournalEntry]:
        journal = self.memory.get("journal") or []
        return_entries = []
        for entry in journal[::-1]:
            entry = JournalEntry.model_validate(entry)
            if persona_name and entry.persona_name != persona_name:
                continue
            return_entries.append(entry)
            if len(return_entries) == num:
                break
        return return_entries

    def write_blog_entry(
        self, persona_name: str, title: str, byline: str, image_descr: str, content: str, thought_id: str
    ) -> BlogEntry:
        entry = BlogEntry(
            persona_name=persona_name,
            title=title,
            content=content,
            date_added=datetime.utcnow(),
            image_descr=image_descr,
            byline=byline,
            thought_id=thought_id,
        )

        blog = self.memory.get("blog") or []
        blog.append(entry.model_dump())
        self.memory["blog"] = blog
        return entry

    def get_latest_blog_entries(self, persona_name: Optional[str] = None, num: int = 5) -> list[BlogEntry]:
        blog = self.memory.get("blog") or []
        return_entries = []
        for entry in blog[::-1]:
            entry = BlogEntry.model_validate(entry)
            if persona_name and entry.persona_name != persona_name:
                continue
            return_entries.append(entry)
            if len(return_entries) == num:
                break
        return return_entries

    # def list_goals(self, include_completed=False) -> list[Goal]:
    #     return sorted(
    #         [x for x in self.memory.values() if include_completed or not x.completed_at],
    #         key=lambda x: x.added_at,
    #     )
    #
    # def save_new_goal(self, new_goal: CreateNewGoal) -> Goal:
    #     goal = Goal(
    #         text=new_goal.text,
    #         rationale=new_goal.rationale,
    #         added_at=datetime.utcnow(),
    #         completed_at=None,
    #         goal_progress=[],
    #     )
    #     assert goal.goal_id not in self.memory
    #     self.memory[goal.goal_id] = goal
    #     return goal
    #
    # def get_goal(self, goal_id: str) -> Optional[Goal]:
    #     return self.memory.get(goal_id)
    #
    # def add_progress_note_to_goal(self, goal_id: str, note: str, goal_complete: bool) -> Goal:
    #     goal = self.get_goal(goal_id)
    #     if not goal:
    #         raise ValueError(f"Goal not found {goal_id=}")
    #     if goal.completed_at:
    #         raise RuntimeError("Cannot update already completed goal")
    #     now = datetime.utcnow()
    #     goal.goal_progress.append(GoalProgress(note=note, added_at=now))
    #     if goal_complete:
    #         goal.completed_at = now
    #
    #     self.memory[goal.goal_id] = goal
    #
    #     return goal


class AnswerTrueFalse(BaseModel):
    """Answer the specified true/false question"""

    answer: bool
    rationale: str = Field(..., description="Explain why you have made this choice")


class ActionCallback(BaseModel):
    status: str
    details: str


@dataclass
class BrainInterface(ABC):
    logger: Logger
    goal_memory: GoalMemoryInterface
    thought_memory: ThoughtMemory
    personas: PersonaManager

    def start_new_thought(self, persona: Persona, user_nudge: Optional[str]) -> Thought:
        new_thought, rationale = self._get_initial_thought_for_persona(persona)
        new_thought_data = NewThoughtData(
            persona_name=persona.name, user_nudge=user_nudge, initial_thought=new_thought, it_rationale=rationale
        )

        return self.thought_memory.write_new_thought(new_thought_data)

    def develop_thought_plan(self, thought: Thought) -> Thought:
        plan = self._get_plan_for_thought(thought)
        return self.thought_memory.update_existing_thought(
            existing_thought=thought, update_thought_data=UpdateThoughtData(plan=plan)
        )

    def continue_thought(
        self, thought: Thought, status_callback_fn: Callable[[ActionCallback], None] = None
    ) -> tuple[Thought, str]:
        def _status_callback_handler(status: str, details=""):
            if status_callback_fn:
                status_callback_fn(ActionCallback.model_validate({"status": status, "details": details}))

        current_step = thought.steps_completed + 1
        step = thought.plan[thought.steps_completed]
        is_last_step = current_step == len(thought.plan)
        thought_update = UpdateThoughtData()

        match step.tool_name:
            case prompts.ToolNames.ReadLatestBlogs:
                context, full_output = self._handle_read_latest_blogs_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.QueryForInfo:
                context, full_output = self._handle_query_for_info_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.WriteInJournal:
                context, full_output = self._handle_write_journal_entry_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.ReadFromJournal:
                context, full_output = self._handle_read_latest_journal_entries_action(
                    thought, step, _status_callback_handler
                )
            case prompts.ToolNames.CreateArt:
                context, full_output = self._handle_create_art_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.WriteBlogPost:
                breakpoint()
                context = thought.context
                full_output = "Published a new blog post"
            case _:
                raise ValueError("Unhandled thought response")

        thought_update.context = context
        thought_update.steps_completed = current_step
        if is_last_step:
            thought_update.thought_complete = True

        updated_thought = self.thought_memory.update_existing_thought(
            existing_thought=thought, update_thought_data=thought_update
        )

        return updated_thought, full_output

    @abstractmethod
    def _handle_create_art_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        pass

    @abstractmethod
    def _handle_write_journal_entry_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        pass

    @abstractmethod
    def _handle_read_latest_journal_entries_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        pass

    @abstractmethod
    def _handle_read_latest_blogs_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        pass

    @abstractmethod
    def _handle_query_for_info_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        pass

    @staticmethod
    def _generate_response_to_questions(questions: str) -> str:
        return get_completion(prompts.general_question_answer(questions))

    @abstractmethod
    def _get_initial_thought_for_persona(self, persona: Persona) -> tuple[str, str]:
        pass

    @abstractmethod
    def _get_plan_for_thought(self, thought: Thought) -> list[PlanStep]:
        pass

    @abstractmethod
    def _select_new_goal(self, existing_goals: list[Goal]) -> CreateNewGoal:
        pass

    @abstractmethod
    def _should_select_new_goal(self, existing_goals: list[Goal]) -> AnswerTrueFalse:
        pass

    ######## task actions

    @abstractmethod
    def _query_for_info(self, request: ai_actions.QueryForInfo) -> ai_actions.QueryForInfoResponse:
        pass

    @abstractmethod
    def _record_goal_progress(self, request: ai_actions.RecordGoalProgress) -> ai_actions.RecordGoalProgressResponse:
        pass

    @abstractmethod
    def _read_blog_post(self, request: ai_actions.ReadBlogPost) -> ai_actions.ReadBlogPostResponse:
        pass

    @abstractmethod
    def _write_blog_post(self, request: ai_actions.WriteBlogPost) -> ai_actions.WriteBlogPostResponse:
        pass

    @abstractmethod
    def _write_note(self, request: ai_actions.WriteNote) -> ai_actions.WriteNoteResponse:
        pass

    @abstractmethod
    def _similarity_search(self, request: ai_actions.SimilaritySearch) -> ai_actions.SimilaritySearchResponse:
        pass

    @abstractmethod
    def _link_blog_posts(self, request: ai_actions.LinkBlogPosts) -> ai_actions.LinkBlogPostsResponse:
        pass


class BadAiResponse(RuntimeError):
    """Error raised when AI response doesn't contain the expected information."""

    def __init__(self, msg):
        self.msg = msg


@dataclass
class BrainV2(BrainInterface):
    def _handle_create_art_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        callback("Crafting new piece of art", "")
        artwork_prompt = prompts.create_artwork(thought, persona, step)
        artwork_description = get_completion(artwork_prompt)

        callback("Naming new artwork", artwork_description)

        title_prompt = prompts.title_artwork(thought, persona, step, artwork_description)
        artwork_title = get_completion(title_prompt)

        callback(f"Named: {artwork_title} - rendering image", artwork_title)

        image_bytes = generate_image(artwork_description)

        new_art = self.goal_memory.write_art_piece(
            persona_name=persona.name, title=artwork_title, art_descr=artwork_description, thought_id=thought.thought_id
        )
        context = thought.context.strip()

        created_art = "**I created a new piece of art!**\n\n"
        created_art += f"* TITLE: {artwork_title}\n"
        created_art += f"* DESCRIPTION: {artwork_description}\n"

        self.goal_memory.write_art_contents(new_art, image_bytes)

        if context:
            context = f"{created_art}\n---\n\n{context}"
        else:
            context = created_art

        # journal entry replaces current context completely
        return context, artwork_description

    def _handle_write_journal_entry_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        journal_prompt = prompts.write_journal_entry(thought, persona, step)
        journal_entry = get_completion(journal_prompt)
        self.goal_memory.write_journal_entry(persona.name, journal_entry, thought_id=thought.thought_id)

        # journal entry replaces current context completely
        return journal_entry, journal_entry

    def _handle_read_latest_journal_entries_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        latest_journal_entries = self.goal_memory.get_latest_journal_entries(persona_name=thought.persona_name)
        if not latest_journal_entries:
            journal_contents = "You have not written any journal entries yet, your next entry will be your first."
        else:
            journal_contents = "\n\n---\n\n".join(x.content for x in latest_journal_entries)

        persona = self.personas.get_persona_by_name(thought.persona_name)

        prompt = prompts.summarize_for_context(thought, persona, step, journal_contents)
        response = get_completion(prompt)
        return response, journal_contents

    def _handle_read_latest_blogs_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        latest_blog_entries = self.goal_memory.get_latest_blog_entries(persona_name=thought.persona_name)
        if not latest_blog_entries:
            blog_contents = "You have not written any blog entries yet, your next entry will be your first."
        else:
            blog_contents = "\n\n---\n\n".join(x.format() for x in latest_blog_entries)

        persona = self.personas.get_persona_by_name(thought.persona_name)

        prompt = prompts.summarize_for_context(thought, persona, step, blog_contents)
        response = get_completion(prompt)
        # if not last_line.startswith("I will"):
        #     raise BadAiResponse("AI Response does not contain expected task statement.")
        return response, blog_contents

    def _handle_query_for_info_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        # 1. generate search queries
        queries = self._generate_research_queries(thought, persona, step)
        # 2. have gpt-4 simulate responses to the queries -- later integrate search, user feedback, etc.
        full_response = self._generate_response_to_questions("\n".join(queries))

        # 3. summarize for context
        summarize_prompt = prompts.summarize_for_context(thought, persona, step, full_response)
        new_context = get_completion(summarize_prompt)

        return new_context, full_response

    def _generate_research_queries(self, thought: Thought, persona: Persona, step: PlanStep) -> list[str]:
        response = get_completion(prompts.generate_questions(thought, persona, step))
        questions = [x for x in response.splitlines() if x.strip()]
        self.logger.debug("NEW QUESTIONS")
        self.logger.debug(questions)
        return questions

    def _get_plan_for_thought(self, thought: Thought) -> list[PlanStep]:
        prompt = prompts.plan_for_task(thought)
        response = get_completion(prompt)
        data = json.loads(response)
        ta = TypeAdapter(list[PlanStep])
        return ta.validate_python(data)

    def _get_initial_thought_for_persona(self, persona: Persona) -> tuple[str, str]:
        prompt = prompts.get_new_thought(
            persona=persona,
            # goals=(
            #     "You do not have any active goals. It's okay to not have specific goals, "
            #     "but sometimes you'll want to set one."
            # ),
            recent_actions="You have not take any actions recently.",
        )
        response = get_completion(prompt)
        last_line = response.splitlines()[-1]
        if not last_line.startswith("I will"):
            raise BadAiResponse("AI Response does not contain expected task statement.")
        return last_line, response

    def _should_select_new_goal(self, existing_goals: list[Goal]) -> AnswerTrueFalse:
        pass

    def _select_new_goal(self, existing_goals: list[Goal]) -> CreateNewGoal:
        pass

    def _query_for_info(self, request: ai_actions.QueryForInfo) -> ai_actions.QueryForInfoResponse:
        pass

    def _record_goal_progress(self, request: ai_actions.RecordGoalProgress) -> ai_actions.RecordGoalProgressResponse:
        pass

    def _read_blog_post(self, request: ai_actions.ReadBlogPost) -> ai_actions.ReadBlogPostResponse:
        pass

    def _write_blog_post(self, request: ai_actions.WriteBlogPost) -> ai_actions.WriteBlogPostResponse:
        pass

    def _write_note(self, request: ai_actions.WriteNote) -> ai_actions.WriteNoteResponse:
        pass

    def _similarity_search(self, request: ai_actions.SimilaritySearch) -> ai_actions.SimilaritySearchResponse:
        pass

    def _link_blog_posts(self, request: ai_actions.LinkBlogPosts) -> ai_actions.LinkBlogPostsResponse:
        pass
