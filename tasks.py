import json
from contextlib import contextmanager
from pathlib import Path
from time import sleep

from invoke import Context, task


class Paths:
    here = Path(__file__).parent
    repo_root = here

    @staticmethod
    @contextmanager
    def cd(c: Context, p: Path):
        with c.cd(str(p)):
            yield


@task
def compile_requirements(c, install=False):
    with Paths.cd(c, Paths.repo_root):
        c.run("pip-compile -v -o requirements.txt")
        if install:
            c.run("pip install -r requirements.txt")
            c.run("pip install -r requirements.dev.txt")


@task
def create_thoughts_table(c, name="thoughts-table", delete_first=False):
    if delete_first:
        c.run(f"aws dynamodb delete-table --table-name {name}")
        print("Sleeping 5 seconds to wait for deletion")
        sleep(5)

    attributes = {"pk": "S", "sk": "S", "gsi1pk": "S"}
    # AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S
    attribute_def = " ".join(f"AttributeName={k},AttributeType={v}" for k, v in attributes.items())

    global_indexes = [
        # gsirev is used to query for all Thoughts by specifying the v0 thought identifier for sk
        {
            "IndexName": "gsirev",
            "KeySchema": [{"AttributeName": "sk", "KeyType": "HASH"}, {"AttributeName": "pk", "KeyType": "RANGE"}],
            "Projection": {"ProjectionType": "ALL"},
        },
        # gsi1 is currently used to query thoughts by status, either complete or not, and is sparsely populated on
        # v0 objects thought
        {
            "IndexName": "gsi1",
            "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"}, {"AttributeName": "pk", "KeyType": "RANGE"}],
            "Projection": {"ProjectionType": "ALL"},
        },
    ]
    index_json = json.dumps(global_indexes)

    cmd = f"aws dynamodb create-table --table-name {name}"
    cmd += " --billing-mode PAY_PER_REQUEST"
    cmd += f" --attribute-definitions {attribute_def}"
    cmd += " --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE"
    cmd += f" --global-secondary-indexes '{index_json}'"
    c.run(cmd)


@task
def run_streamlit(c):
    with Paths.cd(c, Paths.repo_root):
        c.run(
            "python -m streamlit run streamlit_app.py",
            pty=True,
        )


@task
def lint(c: Context):
    with Paths.cd(c, Paths.repo_root):
        c.run("isort .")
        c.run("black .")
        c.run("ruff . --fix")
