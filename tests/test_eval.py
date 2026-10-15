import json
import unittest
from collections import Counter
from pathlib import Path

from memory_merge import evaluation

DATASET = Path(__file__).resolve().parents[1] / 'datasets' / 'memory-eval-v1'


class MetricTests(unittest.TestCase):
    def test_metrics_on_hand_computed_cases(self):
        m = evaluation._metrics(['x', 'a', 'b'], {'a': 2, 'b': 1, 'c': 1}, k=3)
        self.assertAlmostEqual(m['recall'], 2 / 3); self.assertEqual(m['success'], 1.0); self.assertAlmostEqual(m['mrr'], 0.5)
        dcg = 3 / 1.584962500721156 + 1 / 2.0
        ideal = 3 / 1.0 + 1 / 1.584962500721156 + 1 / 2.0
        self.assertAlmostEqual(m['ndcg'], dcg / ideal)
        self.assertEqual(evaluation._metrics([], {'a': 2}, k=10)['zero'], 1.0)
        self.assertEqual(evaluation._metrics(['b'], {'a': 2, 'b': 1}, k=10)['success'], 0.0)  # only grade 2 counts


class DatasetTests(unittest.TestCase):
    def test_dataset_is_well_formed(self):
        corpus = [json.loads(l) for l in (DATASET / 'corpus.jsonl').read_text(encoding='utf-8').splitlines()]
        queries = [json.loads(l) for l in (DATASET / 'queries.jsonl').read_text(encoding='utf-8').splitlines()]
        by_id = {c['id']: c for c in corpus}
        self.assertEqual(len(by_id), len(corpus)); self.assertEqual(len({q['id'] for q in queries}), len(queries))
        for q in queries:
            self.assertIn(2, q['relevant'].values(), q['id'])
            for mid in q['relevant']:
                self.assertIn(by_id[mid]['project'], (q['project'], '@user'), q['id'])
        self.assertEqual(Counter(q['split'] for q in queries), {'test': 96, 'dev': 64})


class RetrievalRegressionTests(unittest.TestCase):
    """Guards the lexical retrieval quality measured in docs/EVALUATION.md (dev split, ~2 s).
    Thresholds sit a little below the measured values so harmless changes pass and regressions fail."""

    def test_lexical_dev_split_does_not_regress(self):
        r = evaluation.run(DATASET, ['lexical'], split='dev')
        o = r['modes']['lexical']['overall']
        self.assertEqual(r['dataset']['skipped'], [])  # screening must not reject legitimate memories
        self.assertGreaterEqual(o['ndcg'], 0.64)
        self.assertGreaterEqual(o['recall'], 0.72)
        self.assertLessEqual(o['zero_result_rate'], 0.03)


if __name__ == '__main__':
    unittest.main()
