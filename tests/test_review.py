"""Tests for author-oriented document review."""

from click.testing import CliRunner

from ambisense.cli import main
from ambisense.review import extract_prose_blocks, review_text


class TestExtractProseBlocks:
    def test_skips_fenced_code_blocks(self):
        text = """# Tutorial

```bash
start a container on worker 2
```

Start a container on worker 2.
"""

        blocks = extract_prose_blocks(text, markdown=True)
        joined = "\n".join(block.text for block in blocks)

        assert "start a container on worker 2\n```" not in joined
        assert "Start a container on worker 2." in joined


class TestReviewText:
    def test_reports_line_column_and_highlighted_sentence_for_markdown(self):
        text = """# Tutorial

```bash
start a container on worker 2
```

Start a container on worker 2.
"""

        review = review_text(text, filename="tutorial.md", markdown=True)

        assert len(review.findings) == 1
        finding = review.findings[0]
        assert finding.filename == "tutorial.md"
        assert finding.line == 7
        assert finding.column == 19
        assert finding.pp_text == "on worker 2"
        assert finding.highlighted_sentence == "Start a container [[on worker 2]]."
        assert finding.rewrite_high == "While on worker 2, start a container"
        assert finding.rewrite_low == "Start a container that is on worker 2"

    def test_preserves_link_text_but_ignores_link_destination(self):
        text = "I saw [the man](https://example.com) with the telescope.\n"

        review = review_text(text, markdown=True)

        assert len(review.findings) == 1
        assert review.findings[0].highlighted_sentence == "I saw the man [[with the telescope]]."


class TestReviewCli:
    def test_review_command_outputs_author_facing_rewrites(self, tmp_path):
        path = tmp_path / "tutorial.md"
        path.write_text("Start a container on worker 2.\n")

        runner = CliRunner()
        result = runner.invoke(main, ["review", str(path), "--no-color"])

        assert result.exit_code == 0
        assert f"{path}:1:19" in result.output
        assert "If you mean the phrase attaches to verb \"start\":" in result.output
        assert "While on worker 2, start a container" in result.output
        assert "If you mean the phrase modifies noun \"container\":" in result.output
