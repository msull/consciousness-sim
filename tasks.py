from contextlib import contextmanager
from pathlib import Path

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
def run_streamlit(c):
    with Paths.cd(c, Paths.repo_root):
        c.run(
            "python -m streamlit run streamlit_app.py",
            pty=True,
        )
