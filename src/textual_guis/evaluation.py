import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class EvalResult:
    """An evaluation result"""
    field: str
    requirement: str
    evaluation_result: str
    reason: str = ""


@dataclass
class Evaluation:
    """A single field evaluation"""
    field: str = None
    requirement: str = None
    type: str = "deterministic"

    def __call__(self, **inputs) -> EvalResult:
        raise NotImplementedError


@dataclass
class MaxCharacters(Evaluation):
    """Evaluates a field for a maximum number of characters requirement"""
    max_chars: int = 50

    def __post_init__(self):
        if not self.requirement:
            self.requirement = f"Has at most {self.max_chars} characters"

    def __call__(self, **inputs):
        input = inputs[self.field]
        this_len = len(input)
        if this_len <= self.max_chars:
            return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")
        else:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"Should have at most {self.max_chars} chars, but has {this_len}"
            )


@dataclass
class NoSquareBrackets(Evaluation):
    """Ensure that a field contains no square bracket [placeholders]"""
    requirement: str = "Does not contain square bracket [placeholders]"

    def __call__(self, **inputs):
        input = inputs[self.field]
        brackets_pattern = r'\[.*?\]'
        matches_with_brackets = re.findall(brackets_pattern, input)

        if matches_with_brackets:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"Should not contain square brackets: {', '.join(matches_with_brackets)}"
            )
        return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")


@dataclass
class NoSlashes(Evaluation):
    """Ensure that a field contains no slash/constructions"""
    requirement: str = "Does not contain any slash/constructions"

    def __call__(self, **inputs):
        input = inputs[self.field]
        slash_pattern = r'\b\w+/\w+\b'
        matches_with_slashes = re.findall(slash_pattern, input)

        if matches_with_slashes:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"`{self.field}` should not contain slash constructions: {', '.join(matches_with_slashes)}"
            )
        return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")


@dataclass
class NoBlockedTerms(Evaluation):
    """Ensure that a field contains no blocked terms"""
    blocked_terms: List[str] = None
    blocked_terms_field: str = None

    def __post_init__(self):
        if not self.requirement and self.blocked_terms and not self.blocked_terms_field:
            self.requirement = f"Does not contain any of the following terms: {', '.join(self.blocked_terms)}"
        elif not self.requirement and not self.blocked_terms and self.blocked_terms_field:
            self.requirement = "Does not contain any of the following terms: {{" + self.blocked_terms_field + "}}"

    def __call__(self, **inputs) -> Dict:
        slash_pattern = r'\b\w+/\w+\b'
        text = inputs[self.field]
        words = text.lower().split()
        matches = []
        blocked_terms = self.blocked_terms.copy() if self.blocked_terms else []
        if self.blocked_terms_field is not None and self.blocked_terms_field in inputs:
            blocked_terms += inputs[self.blocked_terms_field]
        for term in blocked_terms:
            if len(term.split()) == 1 and term.lower() in words:
                matches.append(term)
            elif len(term.split()) > 1 and term.lower() in text:
                matches.append(term)
        if matches:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"Should not contain the blocked terms: {', '.join(matches)}"
            )
        return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")


@dataclass
class NotInBlockedList(Evaluation):
    """Ensure that a field is not in a blocked list

    Usage:

    ```python
    blocked_list1 = NotInBlockedList(field="color", blocked_list=["green"])
    print(blocked_list1(color="black"))
    print(blocked_list1(color="green"))

    blocked_list2 = NotInBlockedList(field="color", blocked_list_field="bad_colors")
    print(blocked_list2(color="black", bad_colors=["green"]))
    print(blocked_list2(color="green", bad_colors=["green"]))
    ```
    """
    blocked_list: List[str] = None
    blocked_list_field: str = None

    def __post_init__(self):
        if not self.requirement and self.blocked_list and not self.blocked_list_field:
            self.requirement = f"Is not identical to any of the following blocked values: {', '.join(self.blocked_list)}"
        elif not self.requirement and not self.blocked_list and self.blocked_list_field:
            self.requirement = "Is not identical to any of the following blocked values: {{" + self.blocked_list_field + "}}"

    def __call__(self, **inputs) -> Dict:
        slash_pattern = r'\b\w+/\w+\b'
        text = inputs[self.field].lower().strip()
        blocked_list = self.blocked_list.copy() if self.blocked_list else []
        if self.blocked_list_field is not None and self.blocked_list_field in inputs:
            blocked_list += inputs[self.blocked_list_field]

        blocked_list = [x.lower().strip() for x in blocked_list]

        if text in blocked_list:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"'{text}' is one of the blocked values"
            )
        return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")


@dataclass
class NoLongWords(Evaluation):
    """Evaluates that a field has no words with more than `max_chars` characters

    Usage:

    ```python
    no_long_words = NoLongWords(field="text", max_chars=9)
    print(no_long_words(text="A vegetarian nightingale"))
    print(no_long_words(text="cat dog"))
    ```
    """
    max_chars: int = 10

    def __post_init__(self):
        if not self.requirement:
            self.requirement = f"Contains no words with more than {self.max_chars} characters"

    def __call__(self, **inputs):
        text = inputs[self.field]
        too_long_words = []
        for word in text.split():
            if len(word) > self.max_chars:
                too_long_words.append(word)
        if too_long_words:
            return EvalResult(
                field=self.field,
                requirement=self.requirement,
                evaluation_result="FAIL",
                reason=f"The following words have more than {self.max_chars} characters: {', '.join(too_long_words)}"
            )

        return EvalResult(field=self.field, requirement=self.requirement, evaluation_result="PASS")
