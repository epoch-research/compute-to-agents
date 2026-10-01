import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import pandas as pd
from compute_tokens.clock import measured_clock
from compute_tokens.intervals import merge_intervals, subtract_intervals
from compute_tokens.weka import Event, compressed_span, span_dropping_long_gaps
from compute_tokens.prefix import cache_reads
from compute_tokens.frontier import pareto_frontier, estimate_at_cutoff
from compute_tokens.prepare import derive_gpu_count
from compute_tokens.sources import acquire, verify


class ClockTests(unittest.TestCase):
    def test_union(self):
        self.assertEqual(merge_intervals([(0,10),(5,15),(20,25)]),[(0,15),(20,25)])
        self.assertEqual(subtract_intervals([(0,10)],[(3,7)]),[(0,3),(7,10)])
    def test_human_removal_protected_work_wins(self):
        active,human,gap=measured_clock([(0,100)],[(0,20),(70,90)],[(10,80)],10)
        self.assertEqual((active,human,gap),(50,50,10))
    def test_long_tool_not_capped(self):
        self.assertEqual(measured_clock([(0,1000)],[(0,900)],[],30)[0],930)
    def test_weka_parent_child_union(self):
        events=[Event('root','main',0,10,'m',64,5,[1]),Event('child','subagent',5,10,'m',64,5,[1])]
        self.assertEqual(compressed_span(events,300),15)
    def test_weka_gap_cap_and_drop_differ(self):
        events=[Event('root','main',0,10,'m',64,5,[1]),Event('root','main',410,10,'m',64,5,[1])]
        self.assertEqual(compressed_span(events,300),320)
        self.assertEqual(span_dropping_long_gaps(events),20)


class CacheTests(unittest.TestCase):
    def event(self,t,d,model='m',stream='r',hashes=None):
        return Event(stream,'main',t,d,model,128,5,hashes or [1,2])
    def test_no_future_cache(self):
        events=[self.event(0,10),self.event(5,1),self.event(10,1)]
        result=list(cache_reads(events,64))
        self.assertEqual([r[1] for r in result],[0,0,128])
    def test_cache_model_isolation(self):
        result=list(cache_reads([self.event(0,1),self.event(2,1,'n')],64))
        self.assertEqual(result[1][1:],(0,0,0))
    def test_expiry_and_retention(self):
        result=list(cache_reads([self.event(0,1),self.event(302,1)],64))
        self.assertEqual(result[1][1:],(128,0,128))
    def test_child_prefix_sharing(self):
        result=list(cache_reads([self.event(0,1),self.event(2,1,stream='child',hashes=[1,3])],64))
        self.assertEqual(result[1][1:],(64,64,64))


class BenchmarkTests(unittest.TestCase):
    def test_frontier_interpolation(self):
        df=pd.DataFrame({'id':[1,2,3],'speed':[20,100,50],'concurrency_per_gpu':[10,2,4]})
        f=pareto_frontier(df,'speed')
        # Middle point is not dominated; frontier interpolation is segment-local.
        estimate=estimate_at_cutoff(df,f,'speed',75)
        self.assertAlmostEqual(estimate.estimate,3)
    def test_no_extrapolation(self):
        df=pd.DataFrame({'id':[1],'speed':[100],'concurrency_per_gpu':[2]})
        f=pareto_frontier(df,'speed')
        self.assertEqual(estimate_at_cutoff(df,f,'speed',50).estimate,2)
        self.assertIsNone(estimate_at_cutoff(df,f,'speed',200).estimate)
    def test_disagg_counts_both_pools(self):
        row={'id':'x','disagg':'true','num_prefill_gpu':'8','num_decode_gpu':'16',
             'metrics.total_tput_tps':'2400','metrics.tput_per_gpu':'100'}
        self.assertEqual(derive_gpu_count(row,'error')[0],24)
    def test_unknown_gpu_mismatch_fails(self):
        row={'id':'x','disagg':'true','num_prefill_gpu':'8','num_decode_gpu':'16',
             'metrics.total_tput_tps':'1000','metrics.tput_per_gpu':'100'}
        with self.assertRaises(ValueError): derive_gpu_count(row,'error')


class DownloadTests(unittest.TestCase):
    def test_missing_never_implicitly_downloads(self):
        with tempfile.TemporaryDirectory() as d, patch('urllib.request.urlopen') as request:
            with self.assertRaises(FileNotFoundError): acquire(Path(d))
            request.assert_not_called()
    def test_bad_hash_preserves_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample';p.write_bytes(b'abc')
            with self.assertRaises(ValueError):verify(p,{'bytes':3,'sha256':'bad'})
            self.assertEqual(p.read_bytes(),b'abc')

if __name__=='__main__':unittest.main()
