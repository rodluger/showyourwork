from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from plumbum import local

from showyourwork import exceptions
from showyourwork.merge import RebaseConflict, Repo

git = local["git"]


TEST_FILE = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}

\title{blank project}
\author{Rodrigo Luger}
\date{April 2022}

\begin{document}

\maketitle

\section{Introduction}

\end{document}
"""


def _new_repo(path, branch):
    with local.cwd(path):
        git("init", "-b", branch)
        git("add", ".")
        git("config", "user.name", "test")
        git("config", "user.email", "test")
        git("commit", "--allow-empty", "-am", "initial", retcode=None)


@contextmanager
def overleaf_like(empty=False):
    with TemporaryDirectory() as d:
        if not empty:
            p = Path(d)
            with open(p / "ms.tex", "w") as f:
                f.write(TEST_FILE)
            with open(p / "bib.bib", "w") as f:
                f.write("This is bib.bib\n")
            (p / "figures").mkdir(parents=True)
            with open(p / "figures" / "figure.png", "w") as f:
                pass

        _new_repo(d, "master")
        repo = Repo(url=f"file://{d}", branch="master", path=Path(d))
        yield repo._replace(base_sha=repo.current_sha())


@contextmanager
def syw_like(empty=False):
    with TemporaryDirectory() as d:
        if not empty:
            p = Path(d) / "src" / "tex"
            p.mkdir(parents=True)
            with open(p / "ms.tex", "w") as f:
                f.write(TEST_FILE)
            with open(p / "bib.bib", "w") as f:
                f.write("This is bib.bib\n")

        _new_repo(d, "main")
        repo = Repo(
            url=f"file://{d}",
            branch="main",
            path=Path(d),
            subdirectory="src/tex",
        )
        yield repo._replace(base_sha=repo.current_sha())


@contextmanager
def repo_pair(order, syw_empty=False, ovl_empty=False):
    with syw_like(empty=syw_empty) as local_repo, overleaf_like(
        empty=ovl_empty
    ) as remote_repo:
        if order:
            yield local_repo, remote_repo
        else:
            yield remote_repo, local_repo


@pytest.mark.parametrize("order", [True, False])
def test_dirty_repo(order):
    with repo_pair(order=order) as (syw, ovl):
        with open(syw.source_path / "ms.tex", "a") as f:
            f.write("This is an additional line\n")
        with pytest.raises(exceptions.OverleafError):
            syw.merge_or_rebase(ovl)


@pytest.mark.parametrize("order", [True, False])
def test_fast_forward(order):
    with repo_pair(order) as (syw, ovl):
        fn = ovl.source_path / "ms.tex"
        open(fn, "a").write("This is an additional line\n")
        expected = open(fn, "r").read()
        ovl.git("commit", "-am", "additional line")
        syw.merge_or_rebase(ovl)
        assert open(syw.source_path / "ms.tex", "r").read() == expected


@pytest.mark.parametrize("order", [True, False])
@pytest.mark.parametrize("exclude", ["figures/*", "figures/*.png"])
def test_exclude(order, exclude):
    with repo_pair(order, syw_empty=order, ovl_empty=not order) as (syw, ovl):
        syw.merge_or_rebase(ovl._replace(base_sha=None), exclude=[exclude])
        assert (
            open(syw.source_path / "ms.tex", "r").read()
            == open(ovl.source_path / "ms.tex", "r").read()
        )
        assert not (syw.source_path / "figures").exists()


@pytest.mark.parametrize("order", [True, False])
def test_merge_same_file(order):
    with repo_pair(order) as (syw, ovl):
        ovl_fn = ovl.source_path / "ms.tex"
        open(ovl_fn, "a").write("This is an additional line\n")
        ovl.git("commit", "-am", "additional line: ovl")

        syw_fn = syw.source_path / "ms.tex"
        current = open(syw_fn, "r").read()
        open(syw_fn, "w").write("This is a new first line\n" + current)
        syw.git("commit", "-am", "additional line: syw")

        expected = open(syw_fn, "r").read() + open(ovl_fn, "r").readlines()[-1]

        ff, _ = syw.merge_or_rebase(ovl)
        assert ff
        assert open(syw_fn, "r").read() == expected


@pytest.mark.parametrize("order", [True, False])
def test_merge_different_files(order):
    with repo_pair(order) as (syw, ovl):
        ovl_fn = ovl.source_path / "ms.tex"
        open(ovl_fn, "a").write("This is an additional line\n")
        ovl.git("commit", "-am", "additional line: ovl")
        expected_ms = open(ovl_fn, "r").read()

        syw_fn = syw.source_path / "bib.bib"
        open(syw_fn, "a").write("This is an additional line in the bib\n")
        syw.git("commit", "-am", "additional line: syw")
        expected_bib = open(syw_fn, "r").read()

        ff, _ = syw.merge_or_rebase(ovl)
        assert ff
        assert open(syw.source_path / "ms.tex", "r").read() == expected_ms
        assert open(syw.source_path / "bib.bib", "r").read() == expected_bib


@pytest.mark.parametrize("order", [True, False])
def test_conflict(order):
    with repo_pair(order) as (syw, ovl):
        ovl_fn = ovl.source_path / "ms.tex"
        open(ovl_fn, "a").write("This is an additional line\n")
        ovl.git("commit", "-am", "additional line: ovl")

        syw_fn = syw.source_path / "ms.tex"
        open(syw_fn, "a").write("This is a different additional line\n")
        syw.git("commit", "-am", "additional line: syw")

        with pytest.raises(RebaseConflict):
            syw.merge_or_rebase(ovl)

        expected = TEST_FILE + "This is an additional line\n"
        open(syw_fn, "w").write(expected)
        syw.git("add", syw_fn)
        syw.git("rebase", "--continue")
        assert open(syw_fn, "r").read() == expected
