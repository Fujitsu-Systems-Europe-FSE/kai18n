

import json
import re
import time
import pandas as pd


class I18nTranslator():

    def __init__(self, co, logger, inference_delay = 6):
        self.co = co
        self.logger = logger
        self.last_inference_ts = 0
        self.inference_delay = inference_delay

    def load_json_file(self, path):
        """
        Translates the JSON file at the given path and returns the translated nested JSON.
        """
        with open(path, 'r') as file:
            nested_properties = json.load(file)

        # Convert nested dictionary to a flattened dictionary
        self.property_df = self.nested_to_df(nested_properties) 
        self.property_df['japanese'] = 'not translated'
        self.property_df['comment'] = ''

        # Translate the flattened dictionary
        self.translate_properties()

        return 

    @staticmethod
    def escape_special_characters(text):
        """
        Escapes special characters (\n and \") as //n and //".
        :param text: The input text to escape.
        :return: The escaped text.
        """
        if not isinstance(text, str):
            return text
        return text.replace('\n', '\\n').replace('\"', '\\"')

    @staticmethod
    def unescape_special_characters(text):
        """
        De-escapes special characters (//n and //") back to \n and \".
        :param text: The input text to de-escape.
        :return: The de-escaped text.
        """
        if not isinstance(text, str):
            return text
        return text.replace('\\n', '\n').replace('\\"', '\"')

    @staticmethod
    def nested_to_df(nested_dict, parent_key='', sep='.'):
        """
        Converts a nested dictionary to a flattened dictionary with dot-separated keys.
        """
        flat_dicts = []
        def recurse(d, parent_key):
            
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    recurse(v, new_key)
                else:
                    flat_dicts.append({'key': new_key, 'english': v})

        recurse(nested_dict, parent_key)

        df = pd.DataFrame(flat_dicts).set_index('key')

        return df

    def dump_to_excel(self, path):
        """
        """
        self.property_df.to_excel(path)

        return


    def dump_to_json(self, path, sep='.'):
        """
        """
        nested_dict = {}

        for key, row in self.property_df.iterrows():
            keys = key.split(sep)
            d = nested_dict
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = row['japanese']

        with open(path, "w", encoding="utf-8") as json_file:
            json.dump(nested_dict, json_file, ensure_ascii=False, indent=4)

        return

    def translate_properties(self, page_size=20):
        """
        Splits the flat dictionary into pages, translates them, and combines the results.
        """
        total_pages = (len(self.property_df) + page_size - 1) // page_size  # Calculate total number of pages
        for page in range(total_pages):
            # if page > 2:
            #     break

            start = page * page_size
            end = start + page_size
            page_df = self.property_df.iloc[start:end]  # Yield a page (slice of the DataFrame)
            self.logger.info(f'Translating page {page} : {start} -> {end-1}')
            try:
                translated_page_df = self.translate_properties_page(page_df)
            except Exception as e:
                page_df['japanese'] = page_df['english']
                page_df['comment'] = str(e)

        return self.property_df

    def translate_properties_page(self, df):
        """
        Translates all entries in the dictionary using the `co.chat` translation API.
        """
        prompt_messages = [
            {"role": "user", "content": "You will be translating an internationalization properties file from English to Japanese."},
            {'role': 'user', 'content': 'The file contains nested keys and placeholders. Translate only the text values while leaving the structure, keys, and placeholders intact. '},
            {'role': 'user', 'content': 'If a direct translation feels unnatural, adapt it to sound more natural in Japanese while preserving the meaning.'},
            {'role': 'user', 'content': 'Answer simply with the properties key:value without comments or introduction text.'}
        ]

        # Prepare the content for translation
        properties_content = ''
        for key, row in df.iterrows():
            escaped_value = self.escape_special_characters(row['english'])
            properties_content += f'{key}: "{escaped_value}"'

        # Add translation-specific instructions
        messages = prompt_messages + [
            {'role': 'user', 'content': f'Translate this internationalization properties from English to Japanese:\n{properties_content}'}
        ]

        # Ensure the inference delay if any (to be used with Cohere testing token) 
        if self.inference_delay > 0:
            current_ts = time.time()
            if current_ts < self.last_inference_ts + self.inference_delay:
                time.sleep(current_ts + self.inference_delay)
            self.last_inference_ts = current_ts

        # Call the translation API
        response = self.co.chat(
            model="command-r-plus-08-2024",
            messages=messages
        )

        # Parse the response
        properties_text = response.message.content[0].text
        property_list = properties_text.split('\n')

        for prop in property_list:
            if ":" in prop:
                try:
                    key, value = prop.split(":", 1)
                    value = self.unescape_special_characters(value)
                    value = value.strip().strip('"')
                    self.property_df.at[key, 'japanese'] = value
                except Exception as e:
                    if key in self.property_df:
                        self.property_df.at[key, 'comment'] = str(e)
                    else:
                        self.logger.error(f'Cannot parse response element, {e} : {prop}')
            else:
                self.logger.error(f'Cannot parse response element, missing colon : {prop}')

        return


    def check_translation(self):
        """
        Checks that all entries have been translated and placeholders are preserved.
        """
        for key, row in self.property_df.iterrows():
            translated_value = row['japanese']
            original_value = row['english']

            # Check that the translation exists
            if translated_value is None or translated_value == 'not translated':
                self.property_df.at[key, 'comment'] = f"Missing translation"
                continue
            
            # Check that placeholders are consistent
            # Regular expression to find words between braces
            pattern = r"\{(.*?)\}"
            original_placeholders = re.findall(pattern, original_value)
            translated_placeholders = re.findall(pattern, translated_value)
            
            if original_placeholders != translated_placeholders:
                self.property_df.at[key, 'comment'] = f"Placeholder mismatch"

