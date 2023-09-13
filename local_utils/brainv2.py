from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, Field, field_validator

from . import ai_actions
from .helpers import date_id
from .v2.personas import PersonaManager
from .v2.thoughts import Thought, ThoughtMemory


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


@dataclass
class GoalMemoryInterface(ABC):
    @abstractmethod
    def list_goals(self, include_completed=False) -> list[Goal]:
        pass

    @abstractmethod
    def get_goal(self, goal_id: str) -> Optional[Goal]:
        pass

    @abstractmethod
    def save_new_goal(self, new_goal: CreateNewGoal) -> Goal:
        pass


@dataclass()
class MappingMemory(GoalMemoryInterface):
    memory: MutableMapping[str, Goal] = field(default_factory=dict)

    def list_goals(self, include_completed=False) -> list[Goal]:
        return sorted(
            [x for x in self.memory.values() if include_completed or not x.completed_at],
            key=lambda x: x.added_at,
        )

    def save_new_goal(self, new_goal: CreateNewGoal) -> Goal:
        goal = Goal(
            text=new_goal.text,
            rationale=new_goal.rationale,
            added_at=datetime.utcnow(),
            completed_at=None,
            goal_progress=[],
        )
        assert goal.goal_id not in self.memory
        self.memory[goal.goal_id] = goal
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self.memory.get(goal_id)

    def add_progress_note_to_goal(self, goal_id: str, note: str, goal_complete: bool) -> Goal:
        goal = self.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal not found {goal_id=}")
        if goal.completed_at:
            raise RuntimeError("Cannot update already completed goal")
        now = datetime.utcnow()
        goal.goal_progress.append(GoalProgress(note=note, added_at=now))
        if goal_complete:
            goal.completed_at = now

        self.memory[goal.goal_id] = goal

        return goal


class AnswerTrueFalse(BaseModel):
    """Answer the specified true/false question"""

    answer: bool
    rationale: str = Field(..., description="Explain why you have made this choice")


@dataclass
class BrainInterface(ABC):
    logger: Logger
    goal_memory: GoalMemoryInterface
    thought_memory: ThoughtMemory
    personas: PersonaManager

    def start_new_thought(self, force_id: Optional[str] = None) -> Thought:
        goals = self.goal_memory.list_goals()
        # must always have at least one goal
        if not goals:
            kwargs = {
                "thought_complete": False,
                "task": Task(
                    text="Create my first goal",
                    rationale="As I currently have no goals, I should first set a goal for myself to focus my actions.",
                    plan=[TaskStep(action_name=ai_actions.CreateNewGoal, rationale="Establish my goal")],
                ),
            }
            if force_id:
                kwargs["thought_id"] = force_id

            return Thought.model_validate(kwargs)
        else:
            raise RuntimeError("Not implemented")

    def continue_thought(self, thought: Thought) -> Thought:
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


@dataclass
class BrainV2(BrainInterface):
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
