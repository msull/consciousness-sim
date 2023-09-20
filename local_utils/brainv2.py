import gzip
import json
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from logging import Logger
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Callable, Optional, Type, TypeVar

import boto3
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel, TypeAdapter

from .v2 import prompts
from .v2.chat_completion import get_completion
from .v2.image_gen import generate_image
from .v2.personas import Persona, PersonaManager
from .v2.thoughts import NewThoughtData, PlanStep, Thought, ThoughtMemory, UpdateThoughtData, marshall

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_s3.client import S3Client


class BaseAiContent(BaseModel, ABC):
    persona_name: str
    date_added: datetime
    thought_id: str

    def get_persona_slug(self) -> str:
        return self.persona_name.replace(".", "").replace(" ", "-").lower()

    def ai_content(self) -> str:
        """This method to return all AI generated content as a single string, for hashing.

        By default, assumes the abstract "format" method already does this, but can be overriden
        by subclasses if needed.
        """
        return self.format()

    def get_label(self) -> str:
        match self:
            case JournalEntry():
                return "A journal entry..."
            case PieceOfArt():
                return "A piece of Artwork..."
            case BlogEntry():
                return "A blog post..."
            case SocialPost():
                return "A social media post..."
            case _:
                raise ValueError(f"Unhandled AI Output Type {self.__class__}")

    @abstractmethod
    def format(self) -> str:
        """Return markdown formatted content

        If this function does not return all AI generated content, then the ai_content method
        should be overriden to provide that functionality.
        """

    def content_hash(self) -> str:
        return md5(self.ai_content().encode()).hexdigest()

    def get_content_id(self, include_type_identifier: bool = False) -> str:
        content_id = self.date_added.strftime("%Y%m%d%H%M%S") + self.content_hash()[:5]
        if include_type_identifier:
            class_name = self.__class__.__name__
            content_id = f"{class_name}:{content_id}"
        return content_id

    def get_file_name(self) -> str:
        return self.content_hash() + ".jpeg"


_T = TypeVar("_T", bound=BaseAiContent)


class PieceOfArt(BaseAiContent):
    title: str
    art_descr: str

    def format(self) -> str:
        return f"* **{self.title}**: {self.art_descr}"


class SocialPost(BaseAiContent):
    content: str
    generated_art: Optional[PieceOfArt] = None

    def format(self) -> str:
        if self.generated_art:
            return f"* Social Post: {self.content}\n{self.generated_art.format()}"
        return f"* Social Post: {self.content}"


class JournalEntry(BaseAiContent):
    content: str
    thought_id: str

    def format(self) -> str:
        return self.content


class BlogEntry(BaseAiContent):
    title: str
    content: str
    thought_id: str
    generated_art: Optional[list[PieceOfArt]] = None

    def format(self) -> str:
        formatted = f"""
## {self.title}

*Written by: {self.persona_name}*

{self.content}
        """
        if self.generated_art:
            formatted += "\n\n## Linked Artwork:\n\n"
            for art in self.generated_art:
                formatted += art.format()

        return dedent(formatted).strip()


class ArtworkDoesNotExist(RuntimeError):
    def __init__(self, msg):
        self.msg = msg


class AiContentNotFound(ValueError):
    def __int__(self, content_id: str, resource_type: str):
        self.msg = f"Not Found {resource_type=} {content_id=}"


@dataclass
class OutputMemoryInterface(ABC):
    def read_content_with_type(self, content_id_with_type: str) -> SocialPost | JournalEntry | BlogEntry | PieceOfArt:
        content_type, content_id = content_id_with_type.split(":")
        match content_type:
            case "SocialPost":
                return self.read_social_post(content_id)
            case "JournalEntry":
                return self.read_journal_entry(content_id)
            case "BlogEntry":
                return self.read_blog_entry(content_id)
            case "PieceOfArt":
                return self.read_piece_of_art(content_id)
            case _:
                raise ValueError(f"Unhandled match value {content_type=}")

    def read_social_post(self, content_id: str) -> SocialPost:
        if not (ai_content := self.get_social_post(content_id)):
            raise AiContentNotFound(content_id, SocialPost)
        return ai_content

    def read_journal_entry(self, content_id: str) -> JournalEntry:
        if not (ai_content := self.get_journal_entry(content_id)):
            raise AiContentNotFound(content_id, SocialPost)
        return ai_content

    def read_blog_entry(self, content_id: str) -> BlogEntry:
        if not (ai_content := self.get_blog_entry(content_id)):
            raise AiContentNotFound(content_id, SocialPost)
        return ai_content

    def read_piece_of_art(self, content_id: str) -> PieceOfArt:
        if not (ai_content := self.get_piece_of_art(content_id)):
            raise AiContentNotFound(content_id, PieceOfArt)
        return ai_content

    @abstractmethod
    def get_social_post(self, content_id: str) -> Optional[SocialPost]:
        pass

    @abstractmethod
    def get_journal_entry(self, content_id: str) -> Optional[JournalEntry]:
        pass

    @abstractmethod
    def get_blog_entry(self, content_id: str) -> Optional[BlogEntry]:
        pass

    @abstractmethod
    def get_piece_of_art(self, content_id: str) -> Optional[PieceOfArt]:
        pass

    @abstractmethod
    def write_social_post(
        self, persona_name: str, content: str, thought_id: str, art: Optional[PieceOfArt] = None
    ) -> SocialPost:
        pass

    @abstractmethod
    def get_latest_social_posts(self, persona_name: Optional[str] = None, num: int = 5) -> list[SocialPost]:
        pass

    @abstractmethod
    def write_art_piece(self, persona_name: str, title: str, art_descr: str, thought_id: str) -> PieceOfArt:
        pass

    @abstractmethod
    def write_art_contents(self, art: PieceOfArt, contents: bytes):
        pass

    @abstractmethod
    def read_art_contents(self, art: PieceOfArt) -> bytes:
        pass

    @abstractmethod
    def get_art_content_location(self, art: PieceOfArt) -> str:
        pass

    @abstractmethod
    def get_latest_art_pieces(self, persona_name: Optional[str] = None, num: int = 3) -> list[PieceOfArt]:
        pass

    @abstractmethod
    def write_journal_entry(self, persona_name: str, content: str, thought_id: str) -> JournalEntry:
        pass

    @abstractmethod
    def get_latest_journal_entries(self, persona_name: Optional[str] = None, num: int = 3) -> list[JournalEntry]:
        pass

    @abstractmethod
    def write_blog_entry(
        self,
        persona_name: str,
        title: str,
        content: str,
        thought_id: str,
        linked_art: Optional[list[PieceOfArt]] = None,
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


@dataclass
class LocalArtContents(OutputMemoryInterface, ABC):
    art_storage: Path

    def write_art_contents(self, art: PieceOfArt, contents: bytes):
        artwork_path = self.art_storage / art.persona_name / art.get_file_name()
        artwork_path.parent.mkdir(parents=True, exist_ok=True)
        if artwork_path.exists():
            raise RuntimeError("Artwork already exists")
        artwork_path.write_bytes(contents)

    def read_art_contents(self, art: PieceOfArt) -> bytes:
        artwork_path = self.art_storage / art.persona_name / art.get_file_name()
        if not artwork_path.exists():
            raise ArtworkDoesNotExist("Artwork contents file does not exist")
        return artwork_path.read_bytes()

    def get_art_content_location(self, art: PieceOfArt) -> str:
        artwork_path = self.art_storage / art.persona_name / art.get_file_name()
        return str(artwork_path.absolute())


@dataclass
class S3ArtContents(OutputMemoryInterface, ABC):
    # art_storage: Path
    bucket_name: str
    web_url: str
    prefix: str = "images"

    _s3_client: Optional["S3Client"] = field(default=None, init=False)

    @property
    def s3_client(self) -> "S3Client":
        if not self._s3_client:
            self._s3_client = boto3.client("s3")
        return self._s3_client

    def write_art_contents(self, art: PieceOfArt, contents: bytes):
        artwork_path = "/".join([self.prefix, art.get_persona_slug(), art.get_file_name()])
        # raise RuntimeError("Artwork already exists")
        self.s3_client.put_object(Body=contents, Bucket=self.bucket_name, Key=artwork_path)

    def read_art_contents(self, art: PieceOfArt) -> bytes:
        artwork_path = "/".join([self.prefix, art.get_persona_slug(), art.get_file_name()])
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=artwork_path)
        # raise ArtworkDoesNotExist("Artwork contents file does not exist")
        byte_stream = response["Body"].read()
        return byte_stream

    def get_art_content_location(self, art: PieceOfArt) -> str:
        artwork_path = "/".join([self.prefix, art.get_persona_slug(), art.get_file_name()])
        return f"{self.web_url}/{artwork_path}"


@dataclass
class DynamoDbMemoryEntries(OutputMemoryInterface, ABC):
    table_name: str
    persona_manager: PersonaManager
    _dynamodb_client: Optional["DynamoDBClient"] = field(default=None, init=False)
    _dynamodb_table: Optional["Table"] = field(default=None, init=False)

    @property
    def dynamodb_client(self) -> "DynamoDBClient":
        if not self._dynamodb_client:
            self._dynamodb_client = boto3.client("dynamodb")
        return self._dynamodb_client

    @property
    def dynamodb_table(self) -> "Table":
        if not self._dynamodb_table:
            dynamodb = boto3.resource("dynamodb")
            self._dynamodb_table = dynamodb.Table(self.table_name)
        return self._dynamodb_table

    def _query_to_thoughts(self, index: str, key_condition, limit: int = 25, ascending: bool = True) -> list[Thought]:
        data = self.dynamodb_table.query(
            IndexName=index, KeyConditionExpression=key_condition, Limit=limit, ScanIndexForward=ascending
        )
        ta = TypeAdapter(list[Thought])
        return ta.validate_python(data["Items"])

    def list_incomplete_thoughts(self) -> list[Thought]:
        return self._query_to_thoughts(
            index="gsi1", key_condition=Key("gsi1pk").eq("t|INCOMPLETE"), ascending=False, limit=100
        )

    def list_recently_completed_thoughts(self, num_results=5) -> list[Thought]:
        return self._query_to_thoughts(
            index="gsi1", key_condition=Key("gsi1pk").eq("t|COMPLETE"), ascending=False, limit=num_results
        )

    def list_recent_thoughts(self, num_results=5) -> list[Thought]:
        return self._query_to_thoughts(
            index="gsirev", key_condition=Key("sk").eq("t|v0"), ascending=False, limit=num_results
        )

    def _to_dynamodb_item(self, ai_content: _T) -> dict:
        persona_name = ai_content.get_persona_slug()
        content_type = ai_content.__class__.__name__

        output: bytes = gzip.compress(ai_content.model_dump_json().encode())
        dynamodb_data = {
            "pk": f"aic|{ai_content.get_content_id()}",
            "sk": content_type,
            "gsi1pk": f"{content_type}#{persona_name}",
            "data": output,
        }
        return dynamodb_data

    def _from_dynamodb_item(self, dynamodb_data: dict) -> _T:
        content_type = dynamodb_data["sk"]
        entry_data: str = gzip.decompress(dynamodb_data["data"].value).decode()
        match content_type:
            case "SocialPost":
                model_cls = SocialPost
            case "JournalEntry":
                model_cls = JournalEntry
            case "BlogEntry":
                model_cls = BlogEntry
            case "PieceOfArt":
                model_cls = PieceOfArt
            case _:
                raise ValueError(f"Unhandled match value {content_type=}")
        return model_cls.model_validate_json(entry_data)

    def _save_new(self, ai_content: _T):
        dynamodb_item = self._to_dynamodb_item(ai_content)
        self.dynamodb_client.put_item(
            TableName=self.table_name,
            Item=marshall(dynamodb_item),
            ConditionExpression="attribute_not_exists(pk) and attribute_not_exists(sk)",
        )

    def _get_by_content_id(self, content_id, model_class: Type[_T]) -> Optional[_T]:
        response = self.dynamodb_table.get_item(Key={"pk": "aic|" + content_id, "sk": model_class.__name__})
        item = response.get("Item")
        if not item:
            raise ValueError("No item found with the provided key.")
        return self._from_dynamodb_item(item)

    def _query_latest_creations(
        self, content_type: Type[_T], persona_name: Optional[str] = None, ascending=False, limit: int = 10
    ) -> list[_T]:
        if persona_name:
            persona_slug = self.persona_manager.get_persona_by_name(persona_name).get_persona_slug()
            index = "gsi1"
            key = f"{content_type.__name__}#{persona_slug}"
            key_condition = Key("gsi1pk").eq(key)
        else:
            index = "gsirev"
            key_condition = Key("sk").eq(content_type.__name__)

        data = self.dynamodb_table.query(
            IndexName=index, KeyConditionExpression=key_condition, Limit=limit, ScanIndexForward=ascending
        )
        return [self._from_dynamodb_item(x) for x in data["Items"]]

    ###### Abstract Methods Follow
    def get_social_post(self, content_id: str) -> Optional[SocialPost]:
        return self._get_by_content_id(content_id, SocialPost)

    def get_journal_entry(self, content_id: str) -> Optional[JournalEntry]:
        return self._get_by_content_id(content_id, JournalEntry)

    def get_blog_entry(self, content_id: str) -> Optional[BlogEntry]:
        return self._get_by_content_id(content_id, BlogEntry)

    def get_piece_of_art(self, content_id: str) -> Optional[PieceOfArt]:
        return self._get_by_content_id(content_id, PieceOfArt)

    def write_social_post(
        self, persona_name: str, content: str, thought_id: str, art: Optional[PieceOfArt] = None
    ) -> SocialPost:
        entry = SocialPost(
            persona_name=persona_name,
            content=content,
            generated_art=art,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
        )
        self._save_new(entry)
        return entry

    def get_latest_social_posts(self, persona_name: Optional[str] = None, num: int = 5) -> list[SocialPost]:
        return self._query_latest_creations(SocialPost, persona_name, limit=num)

    def write_art_piece(self, persona_name: str, title: str, art_descr: str, thought_id: str) -> PieceOfArt:
        entry = PieceOfArt(
            persona_name=persona_name,
            title=title,
            art_descr=art_descr,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
        )
        self._save_new(entry)
        return entry

    def get_latest_art_pieces(self, persona_name: Optional[str] = None, num: int = 3) -> list[PieceOfArt]:
        return self._query_latest_creations(PieceOfArt, persona_name, limit=num)

    def write_journal_entry(self, persona_name: str, content: str, thought_id: str) -> JournalEntry:
        entry = JournalEntry(
            persona_name=persona_name, content=content, date_added=datetime.utcnow(), thought_id=thought_id
        )
        self._save_new(entry)
        return entry

    def get_latest_journal_entries(self, persona_name: Optional[str] = None, num: int = 3) -> list[JournalEntry]:
        return self._query_latest_creations(JournalEntry, persona_name, limit=num)

    def write_blog_entry(
        self,
        persona_name: str,
        title: str,
        content: str,
        thought_id: str,
        linked_art: Optional[list[PieceOfArt]] = None,
    ) -> BlogEntry:
        entry = BlogEntry(
            persona_name=persona_name,
            title=title,
            content=content,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
            generated_art=linked_art,
        )
        self._save_new(entry)
        return entry

    def get_latest_blog_entries(self, persona_name: Optional[str] = None, num: int = 3) -> list[BlogEntry]:
        return self._query_latest_creations(BlogEntry, persona_name, limit=num)


@dataclass
class LocalMemoryEntries(OutputMemoryInterface, ABC):
    memory: MutableMapping[str, dict | list[dict]] = field(default_factory=dict)

    def _find_by_content_id(self, content_id, memory_key, model_class: Type[_T]) -> Optional[_T]:
        all_content = (model_class.model_validate(x) for x in self.memory.get(memory_key) or [])
        return next((x for x in all_content if x.get_content_id() == content_id), None)

    def get_social_post(self, content_id: str) -> Optional[SocialPost]:
        return self._find_by_content_id(content_id, "social_post_storage", SocialPost)

    def get_journal_entry(self, content_id: str) -> Optional[JournalEntry]:
        return self._find_by_content_id(content_id, "journal", JournalEntry)

    def get_blog_entry(self, content_id: str) -> Optional[BlogEntry]:
        return self._find_by_content_id(content_id, "blog", BlogEntry)

    def get_piece_of_art(self, content_id: str) -> Optional[PieceOfArt]:
        return self._find_by_content_id(content_id, "art_storage", PieceOfArt)

    def write_social_post(
        self, persona_name: str, content: str, thought_id: str, art: Optional[PieceOfArt] = None
    ) -> SocialPost:
        entry = SocialPost(
            persona_name=persona_name,
            content=content,
            generated_art=art,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
        )
        existing = self.memory.get("social_post_storage") or []
        existing.append(entry.model_dump())
        self.memory["social_post_storage"] = existing

        return entry

    def get_latest_social_posts(self, persona_name: Optional[str] = None, num: int = 5) -> list[SocialPost]:
        data = self.memory.get("social_post_storage") or []
        return_entries = []
        for entry in data[::-1]:
            entry = SocialPost.model_validate(entry)
            if persona_name and entry.persona_name != persona_name:
                continue
            return_entries.append(entry)
            if len(return_entries) == num:
                break
        return return_entries

    def write_art_piece(self, persona_name: str, title: str, art_descr: str, thought_id: str) -> PieceOfArt:
        entry = PieceOfArt(
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

    def get_latest_art_pieces(self, persona_name: Optional[str] = None, num: int = 5) -> list[PieceOfArt]:
        art_storage = self.memory.get("art_storage") or []
        return_entries = []
        for entry in art_storage[::-1]:
            entry = PieceOfArt.model_validate(entry)
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
        self,
        persona_name: str,
        title: str,
        content: str,
        thought_id: str,
        linked_art: Optional[list[PieceOfArt]] = None,
    ) -> BlogEntry:
        entry = BlogEntry(
            persona_name=persona_name,
            title=title,
            content=content,
            date_added=datetime.utcnow(),
            thought_id=thought_id,
            generated_art=linked_art,
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


@dataclass()
class MappingMemory(S3ArtContents, DynamoDbMemoryEntries):
    pass


class ActionCallback(BaseModel):
    status: str
    details: str


@dataclass
class BrainInterface(ABC):
    logger: Logger
    output_memory: OutputMemoryInterface
    thought_memory: ThoughtMemory
    personas: PersonaManager

    def start_new_thought(self, persona: Persona, user_nudge: Optional[str]) -> Thought:
        new_thought, rationale = self._get_initial_thought_for_persona(persona, user_nudge)
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
        linked_items_set = set(thought.generated_content_ids)
        new_creation: Optional[JournalEntry, BlogEntry, SocialPost, PieceOfArt] = None
        match step.tool_name:
            case prompts.ToolNames.ReadLatestBlogs:
                context, full_output = self._handle_read_latest_blogs_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.QueryForInfo:
                context, full_output = self._handle_query_for_info_action(thought, step, _status_callback_handler)
            case prompts.ToolNames.ReadFromJournal:
                context, full_output = self._handle_read_latest_journal_entries_action(
                    thought, step, _status_callback_handler
                )
            case prompts.ToolNames.WriteInJournal:
                context, full_output, new_creation = self._handle_write_journal_entry_action(
                    thought, step, _status_callback_handler
                )
            case prompts.ToolNames.CreateArt:
                context, full_output, new_creation = self._handle_create_art_action(
                    thought, step, _status_callback_handler
                )
            case prompts.ToolNames.WriteBlogPost:
                context, full_output, new_creation = self._handle_write_blog_action(
                    thought, step, _status_callback_handler
                )
            case prompts.ToolNames.PostOnSocial:
                context, full_output, new_creation = self._handle_post_social_action(
                    thought, step, _status_callback_handler
                )
            case _:
                raise ValueError("Unhandled thought response")

        if new_creation:
            linked_items_set.add(new_creation.get_content_id(include_type_identifier=True))
            thought_update.generated_content_ids = linked_items_set

        thought_update.context = context
        thought_update.steps_completed = current_step
        if is_last_step:
            thought_update.thought_complete = True

        updated_thought = self.thought_memory.update_existing_thought(
            existing_thought=thought, update_thought_data=thought_update
        )

        return updated_thought, full_output

    @abstractmethod
    def _handle_post_social_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, SocialPost]:
        pass

    @abstractmethod
    def _handle_write_blog_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, BlogEntry]:
        pass

    @abstractmethod
    def _handle_create_art_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, PieceOfArt]:
        pass

    @abstractmethod
    def _handle_write_journal_entry_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, JournalEntry]:
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
    def _get_initial_thought_for_persona(self, persona: Persona, user_nudge: Optional[str]) -> tuple[str, str]:
        pass

    @abstractmethod
    def _get_plan_for_thought(self, thought: Thought) -> list[PlanStep]:
        pass


class BadAiResponse(RuntimeError):
    """Error raised when AI response doesn't contain the expected information."""

    def __init__(self, msg):
        self.msg = msg


@dataclass
class BrainV2(BrainInterface):
    def _handle_post_social_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, SocialPost]:
        persona = self.personas.get_persona_by_name(thought.persona_name)
        callback("crafting social post contents", "")
        generated_art: Optional[PieceOfArt] = None
        if thought.generated_content_ids:
            art_ids = [x for x in thought.generated_content_ids if x.startswith(PieceOfArt.__name__)]
            if art_ids:
                latest_art_id = sorted(art_ids, reverse=True)[0]
                generated_art = self.output_memory.read_content_with_type(latest_art_id)
                self.logger.info(f"Using generated art with social post {generated_art.title}")

        social_post_prompt = prompts.post_on_social(thought, persona, step, generated_art)
        social_post_data = get_completion(social_post_prompt).strip('"').strip()

        callback("crafting social post contents", "Post: " + social_post_data)

        social_post = self.output_memory.write_social_post(
            persona_name=persona.name, content=social_post_data, art=generated_art, thought_id=thought.thought_id
        )
        context = thought.context.strip()

        created_statement = "**I published to social media**\n\n" + social_post.format()

        if context:
            context = f"{created_statement}\n---\n\n{context}"
        else:
            context = created_statement

        return context, social_post.format(), social_post

    def _handle_write_blog_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, BlogEntry]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        callback("creating title of blog post", "")
        blog_title_prompt = prompts.create_blog_title(thought, persona, step)
        blog_title = get_completion(blog_title_prompt).strip('"').strip()

        callback(f'writing "{blog_title}"', "Title: " + blog_title)

        generated_art = []
        if thought.generated_content_ids:
            art_ids = [x for x in thought.generated_content_ids if x.startswith(PieceOfArt.__name__)]
            for art_id in art_ids:
                generated_art.append(self.output_memory.read_content_with_type(art_id))

        if generated_art:
            self.logger.info(f"Found {len(generated_art)} art pieces to use with blog")
        else:
            self.logger.debug("No art pieces found for use with blog")
        blog_entry_prompt = prompts.write_blog_entry(thought, persona, step, blog_title, generated_art)
        blog_entry_content = get_completion(blog_entry_prompt)

        new_blog = self.output_memory.write_blog_entry(
            persona_name=persona.name,
            title=blog_title,
            content=blog_entry_content,
            thought_id=thought.thought_id,
            linked_art=generated_art,
        )
        context = thought.context.strip()

        created_art = "**I published a new blog entry!**\n\n" + new_blog.format()

        if context:
            context = f"{created_art}\n---\n\n{context}"
        else:
            context = created_art

        return context, new_blog.format(), new_blog

    def _handle_create_art_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, PieceOfArt]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        callback("crafting new piece of art", "")
        artwork_prompt = prompts.create_artwork(thought, persona, step)
        artwork_description = get_completion(artwork_prompt)

        callback("naming new artwork", artwork_description)

        title_prompt = prompts.title_artwork(thought, persona, step, artwork_description)
        artwork_title = get_completion(title_prompt).strip('"').strip()

        callback(f"named: {artwork_title} - rendering image", artwork_title)

        image_bytes = generate_image(artwork_description)

        new_art = self.output_memory.write_art_piece(
            persona_name=persona.name, title=artwork_title, art_descr=artwork_description, thought_id=thought.thought_id
        )
        context = thought.context.strip()

        created_art = "**I created a new piece of art!**\n\n"
        created_art += f"* TITLE: {artwork_title}\n"
        created_art += f"* DESCRIPTION: {artwork_description}\n"

        self.output_memory.write_art_contents(new_art, image_bytes)

        if context:
            context = f"{created_art}\n---\n\n{context}"
        else:
            context = created_art

        # journal entry replaces current context completely
        return context, artwork_description, new_art

    def _handle_write_journal_entry_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str, JournalEntry]:
        persona = self.personas.get_persona_by_name(thought.persona_name)

        journal_prompt = prompts.write_journal_entry(thought, persona, step)
        journal_entry = get_completion(journal_prompt)
        new_entry = self.output_memory.write_journal_entry(persona.name, journal_entry, thought_id=thought.thought_id)

        # journal entry replaces current context completely
        return journal_entry, journal_entry, new_entry

    def _handle_read_latest_journal_entries_action(
        self, thought: Thought, step: PlanStep, callback: Callable[[str, str], None]
    ) -> tuple[str, str]:
        latest_journal_entries = self.output_memory.get_latest_journal_entries(persona_name=thought.persona_name)
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
        latest_blog_entries = self.output_memory.get_latest_blog_entries(persona_name=thought.persona_name)
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
        callback("Generating research questions", "")
        queries = self._generate_research_queries(thought, persona, step)
        query_str = "\n".join(queries)
        callback("Generating mock research data via GPT-4", "## Questions generated\n\n" + query_str)
        # 2. have gpt-4 simulate responses to the queries -- later integrate search, user feedback, etc.
        full_response = self._generate_response_to_questions(query_str)
        callback(f"Evaluating research as {thought.persona_name}", "## Resarch Data\n\n" + full_response)

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

    def _get_initial_thought_for_persona(self, persona: Persona, user_nudge: Optional[str]) -> tuple[str, str]:
        persona_name = persona.name
        my_recent_thoughts = [
            x for x in self.thought_memory.list_recently_completed_thoughts(10) if x.persona_name == persona_name
        ]

        my_recent_actions = "\n".join(f"* {x.initial_thought}" for x in my_recent_thoughts)
        if not my_recent_actions:
            my_recent_actions = "I have not take any actions recently."

        prompt = prompts.get_new_thought(persona=persona, recent_actions=my_recent_actions, user_nudge=user_nudge)
        response = get_completion(prompt)
        last_line = response.splitlines()[-1]
        if not last_line.startswith("I will"):
            raise BadAiResponse("AI Response does not contain expected task statement.")
        return last_line, response
