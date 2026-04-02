"""Tests for Skills system.

Verifies T10.3: Skill loading, frontmatter parsing.
"""

from pathlib import Path

from cc.skills.loader import Skill, get_skill_by_name, load_skills


class TestLoadSkills:
    def test_load_skill_file(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "commit.md").write_text(
            "---\nname: commit\ndescription: Create a git commit\n---\n"
            "Analyze changes and create a commit with a descriptive message."
        )
        skills = load_skills(str(tmp_path))
        assert len(skills) == 1
        assert skills[0].name == "commit"
        assert "descriptive message" in skills[0].prompt

    def test_load_without_frontmatter(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "review.md").write_text("Review the code for bugs and issues.")
        skills = load_skills(str(tmp_path))
        assert len(skills) == 1
        assert skills[0].name == "review"
        assert "bugs" in skills[0].prompt

    def test_empty_skill_ignored(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "empty.md").write_text("")
        skills = load_skills(str(tmp_path))
        assert len(skills) == 0

    def test_no_skills_dir(self, tmp_path: Path) -> None:
        skills = load_skills(str(tmp_path))
        assert skills == []

    def test_get_skill_by_name(self) -> None:
        skills = [
            Skill(name="commit", description="", prompt="..."),
            Skill(name="review", description="", prompt="..."),
        ]
        found = get_skill_by_name(skills, "commit")
        assert found is not None
        assert found.name == "commit"

    def test_get_skill_case_insensitive(self) -> None:
        skills = [Skill(name="Commit", description="", prompt="...")]
        found = get_skill_by_name(skills, "commit")
        assert found is not None

    def test_get_skill_not_found(self) -> None:
        skills = [Skill(name="commit", description="", prompt="...")]
        found = get_skill_by_name(skills, "nonexistent")
        assert found is None
