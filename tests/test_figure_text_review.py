"""Text-only revision regression tests, including tick formatter persistence."""
import unittest
import matplotlib.pyplot as plt
import pandas as pd
from compute_tokens import polish as p, figure_text_review as review
from compute_tokens.paths import REFERENCE


class Capture:
    def __init__(self):
        self.figures={}

    def save(self,fig,number,*args):
        self.figures[number]=fig


class TextReview(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_capacity_labels_survive_redraw_and_data_unchanged(self):
        p.theme()
        estimates=p.b.r.estimates(pd.read_csv(REFERENCE/'inferencex_prepared.csv'),'latest')
        capture=Capture()
        p.projections(capture,estimates)
        for old,new in [('5','6'),('6','7'),('7','8')]:
            fig=capture.figures[old]
            fig.canvas.draw()
            before=review.plot_signature(fig)
            review.revise(fig,new)
            fig.canvas.draw()
            self.assertEqual(before,review.plot_signature(fig))
        self.assertEqual([t.get_text() for t in capture.figures['5'].axes[0].get_yticklabels()],
                         ['2025–26 HBM shipments','2025–27 HBM shipments'])
        self.assertEqual([t.get_text() for t in capture.figures['7'].axes[0].get_yticklabels()],
                         ['P90: 50 tokens/s/user','P90: 100 tokens/s/user'])

    def test_a2_no_asterisk_note(self):
        p.theme()
        estimates=p.b.r.estimates(pd.read_csv(REFERENCE/'inferencex_prepared.csv'),'latest')
        capture=Capture()
        p.matrix(capture,estimates,[200])
        fig=capture.figures['A2']
        review.revise(fig,'A2')
        foot=next(t.get_text() for t in fig.texts if t.get_gid()=='figure-footnote')
        self.assertEqual(foot,'— No benchmark result meeting the target.')


if __name__=='__main__':
    unittest.main()
