import unittest
import adaptive as a

class EProcessTests(unittest.TestCase):
    def test_initial_and_domains(self):
        self.assertEqual(a.e_confirm(0,0),1.0)
        self.assertEqual(a.e_futility(0,0),1.0)
        for n in range(1,15):
            for k in range(n+1):
                self.assertGreaterEqual(a.e_confirm(n,k),0)
                self.assertGreaterEqual(a.e_futility(n,k),0)

    def test_e_process_boundaries(self):
        self.assertGreaterEqual(a.e_confirm(13,13),960)
        self.assertLess(a.e_confirm(12,12),960)
        self.assertGreaterEqual(a.e_futility(4,0),960)
        self.assertLess(a.e_futility(3,0),960)

    def test_mixture_formulas_against_numeric_integration(self):
        # Midpoint quadrature independently checks the closed-form beta/binomial identities.
        for n, k in ((1, 0), (1, 1), (3, 1), (5, 4)):
            steps = 20000
            h = 0.5 / steps
            direct_hi = sum(2 * ((q / 0.5) ** k) * (((1-q) / 0.5) ** (n-k))
                            for q in (0.5 + (i + 0.5) * h for i in range(steps))) * h
            u = a.FUTILITY_TARGET
            h2 = u / steps
            direct_lo = sum((1/u) * ((q/u) ** k) * (((1-q)/(1-u)) ** (n-k))
                            for q in ((i + 0.5) * h2 for i in range(steps))) * h2
            self.assertAlmostEqual(a.e_confirm(n, k), direct_hi, places=5)
            self.assertAlmostEqual(a.e_futility(n, k), direct_lo, places=5)

    def test_statuses(self):
        self.assertEqual(a.classify([1.2]*13,24)['status'],'confirmed_median_ratio_above_threshold')
        self.assertEqual(a.classify([1.0]*4,24)['status'],'futility_evidence_below_90pct_reproducibility')
        self.assertEqual(a.classify([1.0]*20,24)['status'],'futility_evidence_below_90pct_reproducibility')

    def test_finite_horizon_error_bounds(self):
        _, alpha = a.thresholds(24)
        self.assertLessEqual(a.exact_crossing_probability(.5,'confirm',24),alpha)
        self.assertLessEqual(a.exact_crossing_probability(.9,'futility',24),alpha)

if __name__ == '__main__': unittest.main()
