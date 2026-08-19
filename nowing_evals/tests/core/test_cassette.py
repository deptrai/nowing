"""Unit tests for Cassette loading and replay mechanics in nowing_evals."""


import pytest


class TestCassetteLoadingAndReplay:
    """Test loading and replaying recorded cassettes in nowing_evals."""

    def test_load_rest_cassette_from_sse_jsonl(self, tmp_path):
        """Loads a valid REST cassette from JSONL format."""
        from nowing_evals.core.cassette import Cassette

        cassette_file = tmp_path / "lead-001.sse.jsonl"
        cassette_file.write_text(
            '{"type":"rest","status":200,"headers":{},"body":{"phones":["0908123456"],"tax_ids":["0100109106"],"tax_ids_valid":[true],"company_name":"ABC"}}\n'
        )

        cassette = Cassette.load(cassette_file)
        assert cassette.status == 200
        assert cassette.body["phones"] == ["0908123456"]
        assert cassette.body["tax_ids"] == ["0100109106"]
        assert cassette.body["tax_ids_valid"] == [True]

    def test_missing_cassette_raises_file_not_found(self, tmp_path):
        """Requesting non-existent cassette fails closed with FileNotFoundError."""
        from nowing_evals.core.cassette import Cassette

        missing_file = tmp_path / "non-existent.sse.jsonl"
        with pytest.raises(FileNotFoundError):
            Cassette.load(missing_file)

    def test_malformed_cassette_raises_error(self, tmp_path):
        """Corrupted cassette file fails closed."""
        from nowing_evals.core.cassette import Cassette

        corrupt_file = tmp_path / "corrupt.sse.jsonl"
        corrupt_file.write_text("{invalid json payload")

        with pytest.raises(ValueError):
            Cassette.load(corrupt_file)

    def test_cassette_non_object_json_raises(self, tmp_path):
        """Cassette must contain a JSON object."""
        from nowing_evals.core.cassette import Cassette

        bad_file = tmp_path / "bad.sse.jsonl"
        bad_file.write_text('["not", "an", "object"]\n')

        with pytest.raises(ValueError, match="must contain a JSON object"):
            Cassette.load(bad_file)

    def test_cassette_body_not_dict_raises(self, tmp_path):
        """Cassette body must be a JSON object."""
        from nowing_evals.core.cassette import Cassette

        bad_file = tmp_path / "bad-body.sse.jsonl"
        bad_file.write_text('{"type":"rest","status":200,"headers":{},"body":"not-a-dict"}\n')

        with pytest.raises(ValueError, match="'body' must be a JSON object"):
            Cassette.load(bad_file)

    def test_cassette_save_and_load_round_trip(self, tmp_path):
        """Saving and loading a cassette is idempotent."""
        from nowing_evals.core.cassette import Cassette

        cassette = Cassette(
            type="rest",
            status=200,
            headers={"content-type": "application/json"},
            body={"phones": ["0908123456"], "tax_ids": [], "tax_ids_valid": []},
        )
        out = tmp_path / "roundtrip.sse.jsonl"
        cassette.save(out)

        loaded = Cassette.load(out)
        assert loaded.status == 200
        assert loaded.body == cassette.body
        assert loaded.headers == cassette.headers
