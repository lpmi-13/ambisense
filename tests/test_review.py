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
        assert finding.reading_high == "While on worker 2, start a container"
        assert finding.reading_low == "Start a container that is on worker 2"
        assert finding.rewrite_high == "While connected to worker 2, start a container"
        assert finding.rewrite_low == "Start a container running on worker 2"
        assert finding.high_rule_id == "runtime_on_host_or_cluster"
        assert finding.low_rule_id == "runtime_on_host_or_cluster"

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
        assert 'Ambiguous phrase: "on worker 2"' in result.output
        assert 'Sentence: "Start a container on worker 2."' in result.output
        assert "Possible readings:" in result.output
        assert "A. While on worker 2, start a container." in result.output
        assert "B. Start a container that is on worker 2." in result.output
        assert "Suggested rewrites:" in result.output
        assert '- If you mean A: "While connected to worker 2, start a container."' in result.output
        assert '- If you mean B: "Start a container running on worker 2."' in result.output

    def test_review_command_interactive_mode_prompts_and_echoes_choice(self, tmp_path):
        path = tmp_path / "tutorial.md"
        path.write_text("Start a container on worker 2.\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["review", str(path), "--interactive", "--no-color"],
            input="A\n",
        )

        assert result.exit_code == 0
        assert f"{path}:1:19" in result.output
        assert "Possible readings:" in result.output
        assert "Intended meaning?" in result.output
        assert "Suggested rewrite:" in result.output
        assert '"While connected to worker 2, start a container."' in result.output

    def test_review_command_apply_writes_selected_rewrite_to_file(self, tmp_path):
        path = tmp_path / "tutorial.md"
        path.write_text("Start a container on worker 2.\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["review", str(path), "--interactive", "--apply", "--no-color"],
            input="B\n",
        )

        assert result.exit_code == 0
        assert 'Applied 1 rewrite(s) to "' in result.output
        assert path.read_text(encoding="utf-8") == "Start a container running on worker 2.\n"

    def test_review_command_apply_requires_interactive(self, tmp_path):
        path = tmp_path / "tutorial.md"
        path.write_text("Start a container on worker 2.\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["review", str(path), "--apply"])

        assert result.exit_code != 0
        assert "--apply requires --interactive." in result.output

    def test_review_command_apply_rejects_stdin(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["review", "--interactive", "--apply"],
            input="Start a container on worker 2.\n",
        )

        assert result.exit_code != 0
        assert "--apply only works with file inputs, not stdin." in result.output
