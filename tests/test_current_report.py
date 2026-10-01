import json
import unittest
import numpy as np
import pandas as pd
from compute_tokens.paths import DATA, ROOT, REFERENCE
from compute_tokens import benchmark_figures as b, distributions as d
from compute_tokens.current_report import model_measurements
from compute_tokens.opening_capacity import measurements
from compute_tokens.design_handoff_revision import GROUPS, STYLE


class CurrentReportTests(unittest.TestCase):
    def test_current_figure_coverage(self):
        manifest = json.loads((ROOT/'current_report_manifest.json').read_text())
        self.assertEqual([f['id'] for f in manifest['figures']],
                         [str(n) for n in range(1, 10)]+['A1', 'A2'])
        self.assertEqual(sum(len(f.get('parts', [])) for f in manifest['figures']), 4)

    def test_hardware_mapping_complete(self):
        self.assertEqual(set(STYLE), set(b.HARDWARE))
        self.assertEqual([name for name, _ in GROUPS], ['Nvidia Blackwell', 'Nvidia Hopper', 'AMD'])
        self.assertEqual(len(set(marker for _, marker in STYLE.values())), 9)

    def test_capacity_and_a2_regression(self):
        token = json.loads((DATA/'token_groups.json').read_text())
        cost = [dict(r, dataset='TraceLab', hours_primary=r['hours_uncapped'])
                for r in json.loads((DATA/'cost_groups.json').read_text())]
        records = d.build_records(cost+d.choose(token, 'WEKA'), token)
        est = b.r.estimates(pd.read_csv(REFERENCE/'inferencex_prepared.csv'), 'latest')
        rows = measurements(model_measurements(records, est))
        expected = [(1896.794715550109,1896.794715550109),
                    (570.8976396548203,570.8976396548203),
                    (239.73797809964069,239.73797809964069),
                    (97.34665490029153,194.69330980058305),
                    (30.086196222887267,60.17239244577453)]
        np.testing.assert_allclose([[r['low_agents']/1e6,r['high_agents']/1e6] for r in rows], expected, rtol=1e-12)
        cell = est[(est.model=='glm5.2') & (est.hardware=='b200') &
                   (est.metric=='p90') & (est.cutoff==200)].iloc[0]
        self.assertEqual(f'{cell.estimate:.3g}', '0.975')

    def test_hbm_cumulative_inputs_rederive(self):
        a = b.ASSUMPTIONS
        yearly = [a['hbm_2026_billion_gb']/a['growth_2026'],
                  a['hbm_2026_billion_gb'], a['hbm_2026_billion_gb']*a['growth_2027']]
        for n, year in [(2,2026),(3,2027)]:
            self.assertAlmostEqual(sum(v*s for v,s in zip(yearly[:n], a['share_hbm3e'][:n])), b.H3[year])
            self.assertAlmostEqual(sum(v*s for v,s in zip(yearly[:n], a['share_hbm4'][:n])), b.H4[year])
