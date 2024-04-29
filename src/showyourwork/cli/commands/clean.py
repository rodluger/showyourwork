import shutil

from ... import paths
from .run_snakemake import run_snakemake


def clean(force, deep, snakemake_args=(), cores=1, conda_frontend="conda"):
    """Clean the article build.

    Args:
        force (bool): If True, forcefully delete files in output directories.
        deep (bool): If True, delete all temporary Snakemake and showyourwork
            directories.
        options (str, optional): Additional options to pass to Snakemake.

    """
    if (paths.user().repo / ".snakemake" / "incomplete").exists():
        shutil.rmtree(paths.user().repo / ".snakemake" / "incomplete")
    for file in ["build.smk", "prep.smk"]:
        snakefile = paths.showyourwork().workflow / file
        run_snakemake(
            snakefile.as_posix(),
            run_type="clean",
            cores=cores,
            conda_frontend=conda_frontend,
            extra_args=list(snakemake_args) + ["--delete-all-output"],
            check=False,
        )
    if (paths.user().repo / "arxiv.tar.gz").exists():
        (paths.user().repo / "arxiv.tar.gz").unlink()
    if paths.user().temp.exists():
        shutil.rmtree(paths.user().temp)
    if force:
        for file in paths.user().figures.rglob("*.*"):
            if file.name != ".gitignore":
                file.unlink()
        for file in paths.user().data.rglob("*.*"):
            if file.name != ".gitignore":
                file.unlink()
    if deep:
        if (paths.user().repo / ".snakemake").exists():
            shutil.rmtree(paths.user().repo / ".snakemake")
        if (paths.user().repo / ".showyourwork").exists():
            shutil.rmtree(paths.user().repo / ".showyourwork")
