"""
Unit tests for Nonveg jokes utility and Zipper staging.
"""

import tempfile
from pathlib import Path
import pytest
from bot.utils.jokes import get_random_joke, format_joke_card, NONVEG_JOKES
from bot.services.zipper import (
    add_file_to_staging,
    get_staging_stats,
    get_staging_files_info,
    clear_staging,
    create_zip_package,
)
from bot.utils.progress import ProgressReporter


def test_jokes_generation():
    assert len(NONVEG_JOKES) >= 10
    joke = get_random_joke()
    assert isinstance(joke, str)
    assert len(joke) > 10

    card = format_joke_card(joke)
    assert "😂" in card
    assert joke in card


@pytest.mark.asyncio
async def test_zipper_workflow():
    test_user_id = 999888777
    clear_staging(test_user_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create 2 test files
        file1 = tmp_path / "doc1.txt"
        file1.write_text("Hello file 1")
        file2 = tmp_path / "pic1.jpg"
        file2.write_text("Fake picture content")

        # Add to staging
        count, size, latest = await add_file_to_staging(test_user_id, file1, "doc1.txt")
        assert count == 1
        assert latest == "doc1.txt"

        count, size, latest = await add_file_to_staging(test_user_id, file2, "pic1.jpg")
        assert count == 2
        assert latest == "pic1.jpg"

        # Staging stats and file info
        c, s, l = get_staging_stats(test_user_id)
        assert c == 2

        count_info, total_size, file_info = get_staging_files_info(test_user_id)
        assert count_info == 2
        assert len(file_info) == 2
        assert file_info[0][0] == "doc1.txt"
        assert file_info[1][0] == "pic1.jpg"

        # Test staging card generation with file list
        from bot.templates.cards import zipper_staging_card
        card = zipper_staging_card(count_info, total_size, file_info)
        assert "ZIP BATCH IN PROGRESS" in card
        assert "doc1.txt" in card
        assert "pic1.jpg" in card
        assert "create zip" in card

        # Create package
        out_dir = tmp_path / "out"
        archives = await create_zip_package(
            user_id=test_user_id,
            task_id="test_task",
            output_dir=out_dir,
            reporter=ProgressReporter(None, "Archive.zip", "test_task"),
        )

        assert len(archives) == 1
        assert archives[0].exists()
        assert archives[0].name == "archive.zip"

        # Clean staging
        clear_staging(test_user_id)
        c_after, _, _ = get_staging_stats(test_user_id)
        assert c_after == 0
