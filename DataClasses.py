# Creating a dataclass version of subject
from dataclasses import dataclass


@dataclass
class Subject:
    """A class to represent a legal subject."""

    name: str

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Subject):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        else:
            return False

    def __repr__(self) -> str:
        return f"Subject(name={self.name})"


@dataclass
class Label:
    """A class to represent a citable label for a case."""

    text: str

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Label):
            return self.text == other.text
        elif isinstance(other, str):
            return self.text == other
        else:
            return False

    def __repr__(self) -> str:
        return f"Label(label={self.text})"


@dataclass
class Opinion:
    """A class to represent a court opinion."""

    author: str
    text: str

    def __str__(self) -> str:
        return f"{self.author}: {self.text}\n"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Opinion):
            return self.author == other.author and self.text == other.text
        elif isinstance(other, str):
            return str(self) == other
        else:
            return False

    def __repr__(self) -> str:
        return f"Opinion(author={self.author}, text={self.text})"


type CaseBriefDataTypes = str | list[Subject] | list[Opinion] | Label


@dataclass
class CaseBriefData:
    plaintiff: str
    defendant: str
    citation: str
    course: str
    facts: str
    procedure: str
    issue: str
    holding: str
    principle: str
    reasoning: str
    label: Label
    notes: str
    subjects: list[Subject]
    opinions: list[Opinion]

    @property
    def title(self) -> str:
        return f"{self.plaintiff} v. {self.defendant}"

    @property
    def filename(self) -> str:
        return f"{self.plaintiff}_V_{self.defendant}".replace(" ", "_")

    def asdict(self) -> dict[str, CaseBriefDataTypes]:
        return {
            "plaintiff": self.plaintiff,
            "defendant": self.defendant,
            "citation": self.citation,
            "course": self.course,
            "facts": self.facts,
            "procedure": self.procedure,
            "issue": self.issue,
            "holding": self.holding,
            "principle": self.principle,
            "reasoning": self.reasoning,
            "label": self.label,
            "notes": self.notes,
            "subjects": self.subjects,
            "opinions": self.opinions,
        }
