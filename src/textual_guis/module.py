import json
from dataclasses import dataclass, field, asdict
from typing import List, Union, Dict
from functools import partial

from textual_guis.llmchat import LlmChat
from textual_guis.evaluation import (
    Evaluation, EvalResult, MaxCharacters, NoSquareBrackets, NoSlashes, NoBlockedTerms,
    NotInBlockedList, NoLongWords
)
from textual_guis.utils import (
    Template, parse_text_for_one_tag, parse_text_for_tag
)


@dataclass
class Field:
    """Defines an LLM module input or output"""
    name: str
    description: str
    evaluations: List[Evaluation] = field(default_factory=lambda: [])
    inputs: List['Field'] = field(default_factory=lambda: [])

    def __post_init__(self):
        if self.inputs:
            self.inputs = [Field(**x) for x in self.inputs]

        if self.evaluations:
            self.evaluations = [
                self.evaluation_factory(field=self.name, **x)
                for x in self.evaluations
            ]

    @property
    def markdown(self) -> str:
        """Apply markdown formatting to the input name"""
        return f"`{self.name}`"

    @property
    def xml(self) -> str:
        """Apply xml formatting to the input name"""
        return f"<{self.name}>"

    @property
    def xml_close(self) -> str:
        """Apply xml formatting to the input name"""
        return f"</{self.name}>"

    @property
    def definition(self) -> str:
        """Return a formatted definition string"""
        return f"{self.name}: {self.description}"

    @property
    def input_template(self) -> str:
        """Returns an input template using xml tags and double curly braces"""
        return self.xml + "\n{{" + self.name + "}}\n" + self.xml_close

    def evaluation_factory(
            self,
            field: str,
            type: str,
            value: Union[int, float, str] = None,
            label: str = None,
            use_cot: bool = False,
            **kwargs
    ):
        if type == "max_chars":
            return MaxCharacters(field=field, max_chars=value)
        if type == "no_square_brackets":
            return NoSlashes(field=field)
        if type == "no_slashes":
            return NoSquareBrackets(field=field)
        if type == "not_contains":
            return NoBlockedTerms(field=field, blocked_terms=value, requirement=label)
        if type == "not_in_blocked_list":
            return NotInBlockedList(field=field, blocked_list=value, requirement=label)
        if type == "not_contains_field":
            return NoBlockedTerms(field=field, blocked_terms_field=value, requirement=label)
        if type == "not_in_blocked_list_field":
            return NotInBlockedList(field=field, blocked_list_field=value, requirement=label)
        if type == "no_long_words":
            return NoLongWords(field=field, max_chars=value, requirement=label)
        if type == "llm":
            requirement = Field("requirement", f"A requirement for `{field}`")
            cot = Field("thinking", "Begin by thinking step by step")
            evaluation_result = Field(
                "evaluation_result",
                f'PASS if `{field}` meets the requirement described in `requirement`, FAIL otherwise'
            )
            reason = Field("reason", "A reason for the evaluation result. Leave blank when the evaluation passes.")
            evaluator = LlmModule(
                inputs_header="You will be provided a set of inputs, along with an evaluation criteria that one of the inputs is expected to satisfy.",
                task="Your task is to determine if the input meets the requirement.",
                inputs=self.inputs + [Field(self.name, self.description)] + [requirement],
                outputs=(
                    [cot, evaluation_result, reason]
                    if use_cot else
                    [evaluation_result, reason]
                ),
                **kwargs
            )
            return LlmEvaluation(generator=evaluator, field=field, requirement=label or value)
        raise NotImplementedError


@dataclass
class LlmEvaluation(Evaluation):
    generator: 'LlmModule' = None
    type: str = "llm"

    def __call__(self, **sample):
        result = self.generator(**sample, requirement=self.requirement)
        return EvalResult(
            field=self.field, requirement=self.requirement,
            evaluation_result=result["evaluation_result"],
            reason=result["reason"]
        )


@dataclass
class LlmModule(LlmChat):
    inputs: List[Field] = field(default_factory=lambda: [])
    outputs: List[Field] = field(default_factory=lambda: [])
    inputs_header: str = "You are provided the following inputs:"
    task: str = ""
    details: str = ""
    footer: str = None

    def __post_init__(self):
        super().__post_init__()
        if self.footer is None:
            if len(self.outputs) > 2:
                inline = ", ".join([f"{x.xml}...{x.xml_close}" for x in self.outputs])
            elif len(self.outputs) == 2:
                inline = " and ".join([f"{x.xml}...{x.xml_close}" for x in self.outputs])
            else:
                inline = self.outputs[0].xml
            self.footer = f"Generate the required output{'s' if len(self.outputs) > 1 else ''} within XML tags: {inline}"

    @property
    def prompt(self) -> str:
        """Returns a prompt for generating the output"""
        prompt = ["# Task Description"]
        if self.inputs:
            prompt.append(self.inputs_header)
            prompt.append("\n".join([f"- {x.definition}" for x in self.inputs]))
        if self.task:
            prompt.append(self.task)
        prompt.append("Generate the following outputs within XML tags:")
        for idx, x in enumerate(self.outputs):
            prompt.append(f"{x.xml}\n{x.description}\n{x.xml_close}")
        for x in self.outputs:
            if x.evaluations:
                prompt.append(f"Requirements for {x.markdown}:")
                prompt.append("\n".join([f"- {evl.requirement}" for evl in x.evaluations]))
        if self.details:
            prompt.append(self.details)
        if self.inputs:
            prompt.append("# Inputs")
            for x in self.inputs:
                prompt.append(x.input_template)
        if self.footer:
            prompt.append(self.footer)
        return "\n\n".join(prompt)

    def verify_outputs(self, outputs):
        assert set([x.name for x in self.outputs]) <= set(outputs.keys())

    def __call__(self, **inputs) -> Dict:
        self.clear_history()
        try:
            response_text = self._call(prompt=Template(self.prompt).format(**inputs))
        except Exception as e:
            print(e)
            response_text = ""

        outputs = {}
        for field in self.outputs:
            outputs[field.name] = parse_text_for_one_tag(response_text, field.name).strip()

        self.verify_outputs(outputs)
        return outputs


@dataclass
class Revisor:
    revisor: 'LlmModule' = None
    max_revisions: int = 20

    def __call__(self, **inputs):
        field = self.revisor.outputs[-1]
        # Initialize outputs
        outputs = {
            field.name: inputs[field.name],
            f"{field.name}_evaluation_results": ""
        }

        # Initialize separate deterministic and llm-based evaluations
        deterministic_evaluations = []
        llm_evaluations = []
        for evl in field.evaluations or []:
            if evl.type == "llm":
                llm_evaluations.append(evl)
            else:
                deterministic_evaluations.append(evl)

        # Iterate max_revision times or until all evaluations pass
        for revision_idx in range(self.max_revisions + 1):
            evaluation_results = []
            for evl in deterministic_evaluations + llm_evaluations:
                eval_result = evl(**(inputs | outputs))
                if eval_result.evaluation_result != "PASS":
                    evaluation_results.append(eval_result)
                    break

            if evaluation_results:
                outputs[f"{field.name}_evaluation_results"] = (
                    json.dumps(asdict(evaluation_results[0])) if evaluation_results else ""
                )

            if revision_idx < self.max_revisions and evaluation_results:
                eval_results_str = json.dumps(asdict(evaluation_results[0]), indent=2)
                print(f"revision {revision_idx}: {evaluation_results[0].reason}")
                revised = self.revisor(**(inputs | outputs), evaluation_result=eval_results_str)
                if revised[field.name].strip():
                    outputs[field.name] = revised[field.name].strip()
            elif not evaluation_results:  # Break out of revision loop if all evals pass
                outputs[f"{field.name}_evaluation_results"] = ""
                break
        return outputs


def run_single_output_chain(sample, generate: LlmModule, evaluate_and_revise: Revisor = None):
    output = generate.outputs[-1]

    # Generate an initial response
    sample = generate(**sample)

    # Evaluate and revise
    if evaluate_and_revise is not None:
        sample = sample | evaluate_and_revise(**sample)

    return sample


def initialize_single_output_gen(task: str, output: Dict, details: str = "", **kwargs):
    output = Field(**output)
    chain_of_thought = Field("thinking", "Begin by thinking step by step")
    generate = LlmModule(
        task=task,
        inputs=output.inputs,
        details=details,
        outputs=[chain_of_thought, output],
        **kwargs
    )
    return (
        partial(run_single_output_chain, generate=generate), 
        generate
    )


def initialize_single_output_genrevise(
        task: str, 
        output: Dict, 
        details: str = "", 
        max_revisions: int = 6, 
        **kwargs
):
    output = Field(**output)
    chain_of_thought = Field("thinking", "Begin by thinking step by step")
    generate = LlmModule(
        task=task,
        inputs=output.inputs,
        details=details,
        outputs=[chain_of_thought, output],
        **kwargs
    )
    revise = LlmModule(
        inputs_header="You will be provided a set of inputs, along with a non-passing evaluation result.",
        task="Your task is to generate an updated version of the field indicated in the evaluation result so that it meets all evaluation criteria and requirements.",
        details=details,
        inputs=output.inputs + [output, Field("evaluation_result", "An evaluation result")],
        outputs=[chain_of_thought, output],
        footer=f"Generate the required <thinking> and updated {output.xml} outputs within XML tags.",
        **kwargs
    )
    evaluate_and_revise = Revisor(revisor=revise, max_revisions=max_revisions)
    return (
        partial(
            run_single_output_chain, 
            generate=generate, 
            evaluate_and_revise=evaluate_and_revise
        ), 
        generate, 
        evaluate_and_revise
    )
