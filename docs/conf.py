project = "pylithiumsso3"
copyright = "2022 Khoros, LLC, Austin, Texas, U.S.A. All Rights Reserved"
author = ""

version = ""
release = ""

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

html_theme = "sphinx_rtd_theme"
html_static_path = []
