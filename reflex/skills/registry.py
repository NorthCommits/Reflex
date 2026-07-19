import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger("reflex.skills")

LIBRARY_DIR = Path(__file__).parent / "library"
_REQUIRED_FRONTMATTER_FIELDS = ("name", "description", "triggers")


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    body: str


def _parse_skill_file(path: Path) -> Skill:
    text = path.read_text()

    if not text.startswith("---"):
        raise ValueError(f"Skill file {path.name} is missing YAML frontmatter.")

    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Skill file {path.name} has malformed frontmatter delimiters.")

    _, frontmatter_text, body = parts
    frontmatter = yaml.safe_load(frontmatter_text) or {}

    missing = [f for f in _REQUIRED_FRONTMATTER_FIELDS if not frontmatter.get(f)]
    if missing:
        raise ValueError(f"Skill file {path.name} is missing required field(s): {missing}")

    return Skill(
        name=frontmatter["name"],
        description=frontmatter["description"],
        triggers=[str(t).lower() for t in frontmatter["triggers"]],
        body=body.strip(),
    )


def _load_skills() -> list[Skill]:
    skills = []
    for path in sorted(LIBRARY_DIR.glob("*.md")):
        skill = _parse_skill_file(path)
        skills.append(skill)

    names = [s.name for s in skills]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"Duplicate skill name(s): {duplicates}")

    logger.info("loaded %d skills: %s", len(skills), names)
    return skills


# Skills are loaded once at import time.
SKILLS: list[Skill] = _load_skills()


def get_skills() -> list[Skill]:
    return SKILLS


def select_skills(question: str) -> list[Skill]:
    """Pick the skills whose triggers appear in the question.

    Falls back to every skill if nothing matches, since an unrecognised
    question is exactly the case where the model needs the most guidance,
    not the least.
    """
    lowered = question.lower()
    selected = [s for s in SKILLS if any(trigger in lowered for trigger in s.triggers)]

    if not selected:
        logger.info("no skill triggers matched, falling back to all skills")
        return SKILLS

    return selected


def format_skills_for_prompt(skills: list[Skill]) -> str:
    blocks = [f"## Skill: {s.name}\n{s.description}\n\n{s.body}" for s in skills]
    return "\n\n".join(blocks)
