"""Editorial/layout regression checks on the alternative, unchanged-data figures."""
import json
import unittest

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from compute_tokens import polish as p, distributions as d
from compute_tokens.paths import DATA, REFERENCE


class Capture:
    def __init__(self):
        self.figures = {}

    def save(self, fig, number, *args):
        fig.canvas.draw()
        self.figures[number] = fig


class PolishedFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p.theme()
        token = json.loads((DATA / "token_groups.json").read_text())
        costs = [dict(r, dataset="TraceLab", hours_primary=r["hours_uncapped"]) for r in json.loads((DATA / "cost_groups.json").read_text())]
        cls.records = d.build_records(costs + d.choose(token,"WEKA"), token)
        cls.df = pd.read_csv(REFERENCE / "inferencex_prepared.csv")
        cls.estimates = p.b.r.estimates(cls.df,"latest")

    def tearDown(self):
        plt.close("all")

    def test_all_nine_figures_have_short_captions(self):
        self.assertEqual(set(p.FILES), set(p.SHORT_CAPTIONS))
        self.assertEqual(len(p.FILES), 9)
        for caption in p.SHORT_CAPTIONS.values():
            self.assertLessEqual(len(caption.split()), 65)

    def test_cost_values_and_separate_summary_axes(self):
        capture = Capture()
        rows = p.costs(capture, self.records)
        expected = json.loads((REFERENCE / "sample_summary.json").read_text())["rows"]
        for row, ref in zip(rows, expected):
            self.assertAlmostEqual(row["pooled"],ref["pooled_usd_per_adjusted_hour"],places=9)
        fig = capture.figures["3"]
        self.assertEqual(len(fig.axes), 3)
        self.assertLess(fig.axes[0].get_position().x1, fig.axes[1].get_position().x0)
        self.assertLess(fig.axes[1].get_position().x1, fig.axes[2].get_position().x0)

    def test_matrix_columns_and_scales_match(self):
        capture = Capture()
        p.matrix(capture,self.estimates,[50,100])
        p.matrix(capture,self.estimates,[200])
        axes = capture.figures["2"].axes[:2] + capture.figures["A2"].axes[:1]
        labels = [[t.get_text() for t in ax.get_xticklabels()] for ax in axes]
        self.assertTrue(all(x == labels[0] for x in labels))
        self.assertTrue(all(ax.images[0].norm.vmin == .05 and ax.images[0].norm.vmax == 40 for ax in axes))

    def test_frontier_legend_does_not_cover_note(self):
        capture = Capture()
        p.frontiers(capture,self.df,"p90")
        fig = capture.figures["1"]
        ax = fig.axes[-1]
        renderer = fig.canvas.get_renderer()
        self.assertFalse(ax.get_legend().get_window_extent(renderer).overlaps(ax.texts[0].get_window_extent(renderer)))

    def test_capacity_calculations_and_display_unit(self):
        capture = Capture()
        closed, sensitivity, opened = p.projections(capture,self.estimates)
        self.assertEqual(len(sensitivity), 362)
        self.assertAlmostEqual(closed[0]["central_low_millions"],p.b.capacity(2026),places=12)
        for row in opened:
            self.assertAlmostEqual(row["central_millions"],p.b.capacity(row["year"],u=2,c=row["c"]),places=12)
        # First line in Figure 7 is the original million-session capacity / 1,000.
        line = capture.figures["7"].axes[0].lines[0]
        np.testing.assert_allclose(line.get_xdata(),[opened[0]["low_millions"]/1000,opened[0]["high_millions"]/1000])


if __name__ == "__main__":
    unittest.main()
