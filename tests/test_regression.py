import json
import unittest
from dataclasses import replace
from compute_tokens.paths import DATA, REFERENCE
from compute_tokens import distributions as d
from compute_tokens.tracelab import RoundUsage
from compute_tokens.cache import price_with_split
from compute_tokens.release import scan


class FrozenRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token=json.loads((DATA/'token_groups.json').read_text())
        cls.cost=[dict(r,dataset='TraceLab',hours_primary=r['hours_uncapped']) for r in json.loads((DATA/'cost_groups.json').read_text())]
        cls.records=d.build_records(cls.cost+d.choose(cls.token,'WEKA'),cls.token)
    def test_all_saved_distributions(self):
        d.validate(self.cost+d.choose(self.token,'WEKA'),self.token,self.records)
    def test_main_costs_counts_and_sample(self):
        expected=json.loads((REFERENCE/'sample_summary.json').read_text())['rows']
        for got,ref in zip(d.figure6_records(self.records,'retained'),expected):
            self.assertEqual(got['groups'],ref['included_session_model_groups'])
            self.assertEqual(got['eligible_groups'],ref['figure3_distribution_groups'])
            self.assertAlmostEqual(got['pooled'],ref['pooled_usd_per_adjusted_hour'],places=9)
            self.assertAlmostEqual(got['hours'],ref['adjusted_session_hours'],places=9)
    def test_weka_source_totals(self):
        rows=d.choose(self.token,'WEKA')
        self.assertEqual(len(rows),393)
        self.assertEqual(sum(r['calls'] for r in rows),98827)
        self.assertEqual(sum(r['child_calls'] for r in rows),42029)
        self.assertEqual(sum(r['tokens']['ideal']['input'] for r in rows),21635381376)
        self.assertEqual(sum(r['tokens']['ideal']['output'] for r in rows),106474498)
    def test_source_gap_sensitivity(self):
        rows=d.choose(self.token,'WEKA')
        ratio=sum(r['hours_cap300'] for r in rows)/sum(r['hours_cap60'] for r in rows)
        self.assertAlmostEqual(ratio,1.5542,places=4)
    def test_release_input_privacy(self):
        self.assertGreater(scan(),50)


class PricingTests(unittest.TestCase):
    def usage(self,**changes):
        row=RoundUsage(1,'codex','u','s',None,'gpt-5.6-sol',100000,80000,20000,0,0,0,1000,0,1)
        return replace(row,**changes)
    def test_codex_write_sensitivity(self):
        r=self.usage()
        self.assertAlmostEqual(price_with_split(r,append=20000,assume_codex_writes=True).total,.152)
        self.assertAlmostEqual(price_with_split(r,append=20000,assume_codex_writes=False).total,.132)
    def test_long_context_multipliers(self):
        r=self.usage(input_total=300000,newly_append=300000,prefix=0)
        self.assertAlmostEqual(price_with_split(r,append=300000,assume_codex_writes=True).total,3.03)
    def test_unpriced_call_zero(self):
        self.assertEqual(price_with_split(self.usage(model='unpriced'),append=20000,assume_codex_writes=True).total,0)
    def test_claude_cache_shift_and_ordinary_input(self):
        r=self.usage(provider='claude',model='claude-opus-4-8',claude_cache_read=80000,claude_cache_write=15000,claude_uncached=5000)
        got=price_with_split(r,append=10000,assume_codex_writes=True)
        self.assertAlmostEqual(got.cache_write,5000*6.25/1e6)
        self.assertAlmostEqual(got.uncached_input,5000*5/1e6)
        self.assertAlmostEqual(got.cache_read,90000*.5/1e6)

if __name__=='__main__':unittest.main()
