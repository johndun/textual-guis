from dataclasses import dataclass
from typing import List
import re


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
                template = template.replace(kk, v or "")
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


def parse_text_for_all_tags(text: str) -> List[XmlBlock]:
    """Extracts the text within all the outermost XML/HTML tags.

    Args:
        text (str): A string containing XML tags

    Returns:
        List[XmlBlock]: A list of XmlBlock objects, each containing the tag name and the content inside the tag block
    """
    # This pattern matches any XML tag, capturing the tag name
    pattern = r"<(/?)(\w+)(?:\s+[^>]*)?>"
    outermost_blocks = []
    stack = []

    for match in re.finditer(pattern, text, re.DOTALL):
        is_closing, tag_name = match.groups()

        if not is_closing:
            stack.append((tag_name, match.start()))
        elif stack and stack[-1][0] == tag_name:
            start_tag, start_index = stack.pop()
            if not stack:
                # We found a complete outermost tag block
                opening_tag_end = text.find('>', start_index) + 1
                content = text[opening_tag_end:match.start()]
                outermost_blocks.append(XmlBlock(start_tag, content))

    return outermost_blocks


def parse_text_for_tag(
        text: str,
        tag: str
) -> List[str]:
    """Extracts the text within all the outermost specified XML/HTML tags.

    Args:
        text (str): A string containing XML tags
        tag (str): The tag, without angle braces, to extract

    Returns:
        List[str]: A list of strings, each representing the content inside a tag block
    """
    return [x.content for x in parse_text_for_all_tags(text) if x.tag == tag]