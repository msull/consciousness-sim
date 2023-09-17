import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from pydantic import BaseModel, Field, TypeAdapter

from local_utils.helpers import date_id

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import Table


class PlanStep(BaseModel):
    tool_name: str
    purpose: str

    def format(self):
        return f"{self.tool_name}: {self.purpose}"


class NewThoughtData(BaseModel):
    persona_name: str
    initial_thought: str
    it_rationale: str
    user_nudge: Optional[str] = None


class UpdateThoughtData(BaseModel):
    plan: Optional[list[PlanStep]] = None
    thought_complete: Optional[bool] = None
    context: Optional[str] = None
    steps_completed: Optional[int] = None
    generated_content_ids: Optional[set[str]] = None


class Thought(BaseModel):
    thought_id: str
    version: int
    thought_complete: bool = False
    persona_name: str
    user_nudge: Optional[str] = None

    # initial thought
    initial_thought: str
    it_rationale: str

    # thought plan
    plan: Optional[list[PlanStep]] = None

    # plan execution
    steps_completed: int = 0
    context: str = ""
    last_full_response: str = ""
    generated_content_ids: set[str] = Field(default_factory=set)

    created_at: datetime
    updated_at: datetime

    def display_dict(self):
        return self.model_dump()

    @classmethod
    def new_from_thought_data(cls, thought_data: NewThoughtData) -> "Thought":
        kwargs = thought_data.model_dump()
        now = datetime.utcnow()
        kwargs.update(
            {
                "version": 1,
                "thought_id": date_id(),
                "created_at": now,
                "updated_at": now,
            }
        )
        return Thought.model_validate(kwargs)

    def update_thought(self, update: UpdateThoughtData) -> "Thought":
        now = datetime.utcnow()
        kwargs = self.model_dump()
        kwargs.update(update.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True))
        kwargs.update(
            {
                "version": self.version + 1,
                "thought_id": self.thought_id,
                "created_at": self.created_at,
                "updated_at": now,
            }
        )
        return Thought.model_validate(kwargs)


def unmarshall(dynamo_obj: dict) -> dict:
    """Convert a DynamoDB dict into a standard dict."""
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in dynamo_obj.items()}


def marshall(python_obj: dict) -> dict:
    """Convert a standard dict into a DynamoDB ."""
    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in python_obj.items()}


@dataclass
class ThoughtMemory:
    table_name: str
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

    def write_new_thought(self, thought_data: NewThoughtData) -> Thought:
        return self._save_new_thought(thought_data)

    def update_existing_thought(self, existing_thought: Thought, update_thought_data: UpdateThoughtData) -> Thought:
        latest_version_of_thought = self.read_thought(thought_id=existing_thought.thought_id)
        if existing_thought != latest_version_of_thought:
            raise ValueError("Cannot update from old Thought version")

        updated_thought = existing_thought.update_thought(update_thought_data)
        self._update_existing_versioned(updated_thought, previous_version=latest_version_of_thought.version)
        return self.read_thought(updated_thought.thought_id, updated_thought.version)

    def read_thought(self, thought_id: str, version: int = 0) -> Thought:
        response = self.dynamodb_table.get_item(Key={"pk": "t|" + thought_id, "sk": f"t|v{version}"})
        item = response.get("Item")
        if not item:
            raise ValueError("No item found with the provided key.")
        return Thought(**item)

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

    def _to_dynamodb_item(self, thought: Thought) -> dict:
        output: dict = json.loads(thought.model_dump_json())
        output.update(
            {
                "pk": f"t|{thought.thought_id}",
                "sk": f"t|v{thought.version}",
            }
        )
        if thought.version == 0:
            # add in special attributes on the v0 version
            output.update(
                {
                    "gsi1pk": "t|COMPLETE" if thought.thought_complete else "t|INCOMPLETE",
                }
            )
        return output

    def _save_new_thought(self, thought_data: NewThoughtData) -> Thought:
        thought = Thought.new_from_thought_data(thought_data)
        main_item = self._to_dynamodb_item(thought)
        # copy the resource, set version to zero, and generate the db item again
        v0_resource = thought.model_copy()
        v0_resource.version = 0
        v0_item = self._to_dynamodb_item(v0_resource)
        # restore the version in the final item, so we only have the 0 version in the item keys
        v0_item["version"] = main_item["version"]

        try:
            self.dynamodb_client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self.table_name,
                            "Item": marshall(main_item),
                            "ConditionExpression": "attribute_not_exists(pk) and attribute_not_exists(sk)",
                        }
                    },
                    {
                        "Put": {
                            "TableName": self.table_name,
                            "Item": marshall(v0_item),
                            "ConditionExpression": "attribute_not_exists(pk) and attribute_not_exists(sk)",
                        }
                    },
                ]
            )
        except Exception as e:
            print(e)
        return self.read_thought(thought.thought_id, thought.version)

    def _update_existing_versioned(self, thought: Thought, previous_version: int):
        main_item = self._to_dynamodb_item(thought)

        # copy the resource, set version to zero, and generate the db item again
        v0_resource = thought.model_copy()
        v0_resource.version = 0
        v0_item = self._to_dynamodb_item(v0_resource)
        # restore the version in the final item, so we only have the 0 version in the item keys
        v0_item["version"] = main_item["version"]

        self.dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": self.table_name,
                        "Item": marshall(main_item),
                        "ConditionExpression": "attribute_not_exists(pk) and attribute_not_exists(sk)",
                    }
                },
                {
                    "Put": {
                        "TableName": self.table_name,
                        "Item": marshall(v0_item),
                        "ConditionExpression": "attribute_exists(pk) and attribute_exists(sk) and #version = :version",
                        "ExpressionAttributeNames": {"#version": "version"},
                        "ExpressionAttributeValues": marshall({":version": previous_version}),
                    }
                },
            ]
        )
