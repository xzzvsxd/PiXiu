import os
import subprocess
from flask import request, session, jsonify
from flask_babel import Babel

def get_languages_from_dir(directory):
    """Return a list of directory names in the given directory, with zh_Hans_CN first."""
    languages = [name for name in os.listdir(directory) if os.path.isdir(os.path.join(directory, name))]
    return languages


LANGUAGES_DIR = 'frontend/translations'
BABEL_DEFAULT_LOCALE = 'zh_Hans_CN'
BABEL_LANGUAGES = get_languages_from_dir(LANGUAGES_DIR)

def create_babel(app):
    """Create and initialize a Babel instance with the given Flask app."""
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = LANGUAGES_DIR

    babel = Babel(app)
    app.config['BABEL_DEFAULT_LOCALE'] = BABEL_DEFAULT_LOCALE
    app.config['BABEL_LANGUAGES'] = BABEL_LANGUAGES

    babel.init_app(app, locale_selector=get_locale)
    compile_translations()


def get_locale():
    """Get the user's locale from the session or the request's accepted languages."""

    # print(f"Getting locale from session or request, {BABEL_DEFAULT_LOCALE}, {request.accept_languages.best_match(BABEL_LANGUAGES)}")
    # print(f"Getting locale from session: {session.get('language')}")
    return session.get('language', BABEL_DEFAULT_LOCALE) or request.accept_languages.best_match(BABEL_LANGUAGES)


def get_languages():
    """Return a list of available languages in JSON format."""
    return jsonify(BABEL_LANGUAGES)


def compile_translations():
    """Compile the translation files."""
    result = subprocess.run(
        ['pybabel', 'compile', '-d', LANGUAGES_DIR],
        # stdout=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if result.returncode != 0:
        raise Exception(
            f'Compiling translations failed:\n{result.stdout.decode()}')

    # print('Translations compiled successfully')
