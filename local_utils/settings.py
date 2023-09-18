from pathlib import Path

import streamlit as st
from pydantic import BaseModel, Field, SecretStr, field_validator


class StreamlitAppSettings(BaseModel):
    clarifai_pat: SecretStr = Field(default_factory=lambda: st.secrets["CLARIFAI_PAT"], validate_default=True)
    openai_api_key: SecretStr = Field(default_factory=lambda: st.secrets["OPENAI_API_KEY"], validate_default=True)

    app_data: Path = Field(default_factory=lambda: Path(st.secrets["APP_DATA"]))
    session_data: Path = Field(default_factory=lambda: Path(st.secrets["SESSION_DIR"]))

    dynamodb_thoughts_table: str = Field(default_factory=lambda: st.secrets["DYNAMODB_THOUGHTS_TABLE"])
    s3_data_bucket: str = Field(default_factory=lambda: st.secrets["S3_DATA_BUCKET"])
    s3_web_address: str = Field(default_factory=lambda: st.secrets["S3_WEB_ADDRESS"])

    @field_validator("clarifai_pat", mode="before")
    @classmethod
    def clarifai_pat_is_secret(cls, v: str | SecretStr) -> SecretStr:
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def key_is_secret(cls, v: str | SecretStr) -> SecretStr:
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @staticmethod
    @st.cache_resource
    def load():
        return StreamlitAppSettings()
