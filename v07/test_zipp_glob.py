import unittest
import zipfile
import io
import zipp
from zipp_glob_benchmark import build_archive, glob_filelist, run_glob, structural_work

class ZippGlobRegressionTests(unittest.TestCase):
    def test_file_glob_matches_for_explicit_files(self):
        for depth in (1, 2, 8, 32):
            blob = build_archive(depth)
            self.assertEqual(run_glob(blob, 'namelist', '*.txt'), run_glob(blob, 'filelist', '*.txt'))

    def test_filelist_variant_drops_implied_directory(self):
        blob = build_archive(4)
        self.assertEqual(run_glob(blob, 'namelist', 'd'), ('d/',))
        self.assertEqual(run_glob(blob, 'filelist', 'd'), ())

    def test_parent_visit_count_is_quadratic(self):
        self.assertEqual(structural_work(8)['implied_parent_visits'], 28)
        self.assertEqual(structural_work(16)['implied_parent_visits'], 120)
        self.assertEqual(structural_work(16)['explicit_file_entries'], 16)

    def test_baseline_is_namelist_implementation(self):
        import inspect
        self.assertIn('self.root.namelist()', inspect.getsource(zipp.Path.glob))

if __name__ == '__main__': unittest.main()
