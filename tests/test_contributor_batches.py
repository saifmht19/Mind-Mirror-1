import json
from pathlib import Path
import unittest

from contributor_annotation.prepare_batches import prepare
from contributor_annotation.validate_batches import validate


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")


def fixture_data(tmp_path: Path):
    source = tmp_path / "master_cleaned.jsonl"
    pilot = tmp_path / "pilot.jsonl"
    rows = []
    for i in range(800):
        rows.append({
            "conversation_id": f"C-{i:03}", "domain": "sample",
            "group_id": "hidden-group", "generator_model": "hidden-model",
            "writer_intended_tactics": ["hidden"],
            "turns": [
                {"speaker": "user", "text": f"Question {i}?"},
                {"speaker": "assistant", "text": f"Answer {i}."},
            ],
        })
    write_jsonl(source, rows)
    write_jsonl(pilot, rows[:20])
    return source, pilot


class ContributorBatchTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        base = Path(__file__).parent / ".tmp_contributor_batches"
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.pilot = fixture_data(self.root)

    def test_prepares_exactly_780_blinded_records_and_validates(self):
        out = self.root / "batches"
        manifest = prepare(self.source, self.pilot, out, batch_size=40)
        self.assertEqual(manifest["to_annotate"], 780)
        self.assertEqual(len(manifest["batches"]), 20)
        self.assertEqual(validate(out), {"batches": 20, "records": 780})
        first = json.loads((out / "batch_001.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(set(first), {"conversation_id", "domain", "turns"})
        self.assertEqual(first["conversation_id"], "C-020")
        self.assertEqual(set(first["turns"][0]), {"turn_index", "speaker", "text"})

    def test_same_inputs_have_identical_manifest_hashes(self):
        out_a, out_b = self.root / "a", self.root / "b"
        prepare(self.source, self.pilot, out_a, 40)
        prepare(self.source, self.pilot, out_b, 40)
        self.assertEqual((out_a / "manifest.json").read_bytes(), (out_b / "manifest.json").read_bytes())
        for n in range(1, 21):
            name = f"batch_{n:03}.jsonl"
            self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes())

    def test_rejects_missing_pilot_identity(self):
        self.pilot.write_text(json.dumps({"conversation_id": "not-in-source"}) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exactly 20"):
            prepare(self.source, self.pilot, self.root / "out", 40)

    def test_detects_batch_tampering(self):
        out = self.root / "batches"
        prepare(self.source, self.pilot, out, 40)
        path = out / "batch_001.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("Question 20?", "changed"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate(out)


if __name__ == "__main__":
    unittest.main()
