import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Type, TypeVar

import openai
from logzero import logger
from pydantic import BaseModel, model_validator

_T = TypeVar("_T", bound=BaseModel)


class ChatMessage(BaseModel):
    role: str
    content: str | None
    function_call: dict | None

    @model_validator(mode="after")
    @classmethod
    def content_or_function_call(cls, obj):
        assert obj.content or obj.function_call
        return obj


class ChatResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    object: str
    created: datetime
    model: str
    choices: list[ChatResponseChoice]
    usage: ChatUsage

    @property
    def response_message(self) -> _T | str:
        assert self.choices
        choice = self.choices[0]
        return choice.message.content or json.loads(
            choice.message.function_call["arguments"]
        )

    @property
    def was_response_complete(self) -> bool:
        assert self.choices
        return self.choices[0].finish_reason == "stop"


@dataclass
class ChatSession:
    initial_system_message: Optional[str] = None
    reinforcement_system_msg: Optional[str] = None
    history: list = field(default_factory=list)
    model: str = "gpt-3.5-turbo"
    openai_api_key: Optional[str] = None

    def user_says(self, message, flagged_input_check=False):
        if flagged_input_check:
            check_for_flagged_content(message)
        self.history.append({"role": "user", "content": message})

    def system_says(self, message):
        self.history.append({"role": "system", "content": message})

    def assistant_says(self, message):
        self.history.append({"role": "assistant", "content": message})

    def get_ai_response(
        self,
        initial_system_msg: Optional[str] = None,
        reinforcement_system_msg: Optional[str] = None,
        response_schema: Optional[Type[_T]] = None,
    ) -> ChatResponse:
        initial_system_msg = initial_system_msg or self.initial_system_message
        reinforcement_system_msg = (
            reinforcement_system_msg or self.reinforcement_system_msg
        )

        chat_history = self.history[:]
        # add the initial system message describing the AI's role
        if initial_system_msg:
            chat_history.insert(0, {"role": "system", "content": initial_system_msg})

        if reinforcement_system_msg:
            chat_history.append({"role": "system", "content": reinforcement_system_msg})
        logger.info("Generating AI ChatCompletion")
        logger.debug(chat_history)
        extra_kwargs = {}
        if response_schema:
            extra_kwargs["functions"] = [
                {
                    "name": "respond_as_expected",
                    "description": "return a response in the expected format",
                    "parameters": response_schema.model_json_schema(
                        mode="serialization"
                    ),
                }
            ]
            extra_kwargs["function_call"] = {"name": "respond_as_expected"}
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=chat_history,
            api_key=self.openai_api_key,
            **extra_kwargs
        )
        logger.debug(response)
        response_kwargs = json.loads(json.dumps(response))
        if response_schema:
            response_kwargs["response_schema"] = response_schema

        return ChatResponse.model_validate(response_kwargs)


class FlaggedInputError(RuntimeError):
    pass


def check_for_flagged_content(msg: str):
    response = openai.Moderation.create(msg)
    if response.results[0].flagged:
        raise FlaggedInputError()
