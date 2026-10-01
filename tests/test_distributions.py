"""Estimator tests, independent of the saved-data regression checks in the build."""
import unittest
import numpy as np
from compute_tokens.distributions import cost, distribution, choose, figure6_records, COHORTS


class FiguresTest(unittest.TestCase):
    def test_figure6_only_tracelab_main_scenario_in_cohort_order(self):
        records = [dict(kind='cost',dataset=ds,model=model,high_context=high,
                        scenario='retained',clock='cap300',codex_write_markup=markup)
                   for model, high, _ in reversed(COHORTS)
                   for ds in ('TraceLab','WEKA') for markup in (False, True)]
        selected = figure6_records(records, 'retained')
        self.assertEqual(len(selected),6)
        self.assertTrue(all(r['dataset']=='TraceLab' and r['codex_write_markup'] for r in selected))
        self.assertEqual([(r['model'],r['high_context']) for r in selected],[(m,h) for m,h,_ in COHORTS])

    def test_pool_is_not_session_mean(self):
        rows=[dict(hours_primary=1,hours_cap300=1,n=10),
              dict(hours_primary=9,hours_cap300=9,n=270)]
        d=distribution(rows,lambda r:r['n'])
        self.assertEqual(d['p50'],20)
        self.assertEqual(d['pooled'],28)

    def test_short_rows_only_in_pooled(self):
        rows=[dict(hours_primary=1/12,hours_cap300=.01,n=1),
              dict(hours_primary=.01,hours_cap300=.01,n=3)]
        d=distribution(rows,lambda r:r['n'])
        self.assertEqual(d['eligible_groups'],1)
        self.assertEqual(d['p50'],100)
        self.assertEqual(d['pooled'],200)

    def test_strict_peak_threshold_and_whole_group(self):
        rows=[dict(dataset='WEKA',model='m',max_input=v,n=17) for v in (499999,500000,500001)]
        chosen=choose(rows,'WEKA','m',True)
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]['n'],17)

    def test_tariff_sensitivity_explicit(self):
        tl=dict(dataset='TraceLab',no_write_cost=1,observed_cost=2,
                no_write_retained_cost=.5,retained_cost=1.5)
        self.assertEqual(cost(tl,'baseline'),1)
        self.assertEqual(cost(tl,'baseline',True),2)
        self.assertEqual(cost(tl,'retained'),.5)
        self.assertEqual(cost(dict(dataset='WEKA',reconstructed_costs={'ideal':3}), 'retained'),3)

    def test_sparse_and_empty(self):
        d=distribution([dict(hours_primary=1,hours_cap300=1,n=7)],lambda r:r['n'])
        self.assertEqual(d['p10'],d['p90'])
        self.assertEqual(distribution([],lambda r:0)['pooled'],None)

    def test_cost_quantiles_preserve_token_covariance(self):
        rows=[dict(hours_primary=1,hours_cap300=1,a=a,b=b) for a,b in ((0,10),(10,0),(10,10))]
        total=distribution(rows,lambda r:r['a']+r['b'])['p50']
        wrong=sum(distribution(rows,lambda r:r[k])['p50'] for k in ('a','b'))
        self.assertEqual(total,10)
        self.assertEqual(wrong,20)


if __name__=='__main__':unittest.main()
