import datetime
import json
import logging
import os
import time
import pandas as pd
import pytest
import re


import cohere
from i18n_translator import I18nTranslator

@pytest.fixture(scope="module")
def logger():
    """
    A global pytest fixture that provides a logger instance for all tests.
    The logger is configured once per test session.
    """
    # Configure the logger
    logger = logging.getLogger("pytest_global_logger")
    logger.setLevel(logging.DEBUG)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create a formatter and add it to the handler
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # Add the handler to the logger (if not already added)
    if not logger.hasHandlers():
        logger.addHandler(console_handler)

    yield logger

    # Cleanup: Remove handlers after the session to avoid duplicates
    logger.handlers.clear()


@pytest.fixture(scope='module')
def resource_dir():
    # prepare the result directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    resource_dir = os.path.join(test_dir, '..', 'examples')

    return resource_dir


@pytest.fixture(scope='module')
def result_dir():

    # prepare the result directory
    today = datetime.datetime.now()
    test_dir = os.path.dirname(os.path.abspath(__file__))
    result_dir = os.path.join(test_dir, 'results', today.strftime('%Y%m%d'))
    os.makedirs(result_dir, exist_ok=True)

    return result_dir


@pytest.fixture(scope='module')
def co():

    # Connect to cohere
    cohere_api_key = os.environ.get("COHERE_API_KEY")
    co = cohere.ClientV2(cohere_api_key)

    return co



def test_i18n_translator(co, resource_dir, result_dir, logger):

    input_path = os.path.join(resource_dir, 'kaipplication-en.json')

    translator = I18nTranslator(co, logger, inference_delay = 0)

    translator.load_json_file(input_path)
    translator.check_translation()

    # dump the results
    today = datetime.datetime.now()
    suffix = today.strftime('%Y%m%d_%H%M%S')

    excel_path = os.path.join(result_dir, f'kaipplication-jp_{suffix}.xlsx')
    json_path = os.path.join(result_dir, f'kaipplication-jp.{suffix}.json')

    translator.dump_to_excel(excel_path)
    translator.dump_to_json(json_path)
