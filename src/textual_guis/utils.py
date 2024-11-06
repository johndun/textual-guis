from dataclasses import dataclass
from typing import List, Union, Dict
import re

import polars as pl


@dataclass
class Template:
    """A string template with keys marked by double curly braces."""

    template: str  #: A string template

    def format(self, **kwargs) -> str:
        """Replace template keys with `kwarg` values."""
        template = self.template
        for k, v in kwargs.items():
            kk = "{{" + k + "}}"
            if kk in template:
                template = template.replace(kk, str(v) or "")
        return template


import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class XmlBlock:
    tag: str
    content: str

    def __repr__(self):
        return f"<{self.tag}>{self.content}</{self.tag}>"


def read_data(path: str, as_df: bool = False, **kwargs) -> List[Dict]:
    """Reads tab separated (with header, .txt) or json lines (.jsonl) data from disk.

    Args:
        path: Path to the data file
        as_df: If true, return a polars dataframe
        kwargs: Arguments based to polars read data function

    Returns:
        List[Dict]: Data records/samples as a list of dictionaries
    """
    if path.endswith(".jsonl"):
        df = pl.read_ndjson(path, infer_schema_length=100000, **kwargs)
    elif path.endswith(".txt"):
        if "utf16" in path:
            df = pl.read_csv(path, infer_schema_length=100000, separator="\t", encoding="utf16", **kwargs)
        else:
            df = pl.read_csv(path, infer_schema_length=100000, separator="\t", **kwargs)
    else:
        raise ValueError("Unsupported file type, try .txt (tab-separated) or .jsonl (json lines)")
    if as_df:
        return df
    return df.to_dicts()


def write_data(samples: List[Dict], path: str):
    """Writes data as tab separated (with header, .txt) or json lines (.jsonl) to disk.

    Args:
        samples: Data records/samples as a list of dictionaries
        path: Path to the data file
    """
    if path.endswith(".jsonl"):
        pl.from_dicts(samples).write_ndjson(path)
    elif path.endswith(".txt"):
        pl.from_dicts(samples).write_csv(path, separator="\t")
    else:
        raise ValueError("Unsupported file type, try .txt (tab-separated) or .jsonl (json lines)")


def parse_text_for_tags(text: str) -> List[XmlBlock]:
    """Extracts the text within all the outermost XML/HTML tags.

    Args:
        text (str): A string with XML tags

    Returns:
        List[XmlBlock]: A list of XmlBlock objects, each containing the tag name and the content inside the tag block
    """
    if not text:
        return []
    pattern = r'<([^<>]+)>((?:(?!</?\1>)[\s\S])*)</\1>'
    matches = re.finditer(pattern, text, re.DOTALL)
    return [XmlBlock(match.group(1), match.group(2)) for match in matches]


def parse_text_for_tag(text: str, tag: str) -> List[str]:
    """Extracts the text within all the outermost specified XML/HTML tag.

    Args:
        text (str): A string with XML tags
        tag (str): The tag, without angle braces, to extract

    Returns:
        List[str]: A list of strings, each representing the content inside a tag block
    """
    return [x.content for x in parse_text_for_tags(text) if x.tag == tag]


def parse_text_for_one_tag(text: str, tag: str) -> str:
    """Extracts the (last) text contained in the specified XML/HTML tag.

    Args:
        text (str): A string with XML tags
        tag (str): The tag, without angle braces, to extract

    Returns:
        List[str]: A list of strings, each representing the content inside a tag block
    """
    results = parse_text_for_tag(text, tag)
    return results[-1] if results else ""