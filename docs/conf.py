import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'ERDDAPUtil'
copyright = '2023, Erin Turnbull'
author = 'Erin Turnbull'
release = '0.2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx_toolbox.collapse',
    'sphinx_toolbox.confval',
    'sphinx_click',

]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'pika': ('https://pika.readthedocs.io/en/stable/', None),
}


def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    return "https://github.com/dfo-meds/erddaputil/tree/main/%s.py" % filename



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinxdoc'
html_static_path = ['_static']
