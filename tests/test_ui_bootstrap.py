import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    def test_static_shell_does_not_claim_backend_is_online(self):
        self.assertIn("BACKEND CONNECTING", self.html)
        self.assertNotIn(">AURIS ONLINE<", self.html)

    def test_optional_renderer_cannot_block_control_registration(self):
        self.assertFalse(self.app.lstrip().startswith("import "))
        listener = self.app.index('ui.commandForm.addEventListener("submit"')
        renderer = self.app.index('import("/neural-core.js?v=')
        self.assertLess(listener, renderer)
        self.assertIn("createInertCore", self.app)

    def test_backend_startup_is_resilient_and_provable(self):
        self.assertIn("Promise.allSettled", self.app)
        self.assertIn('fetchJson("/api/client/ready"', self.app)
        self.assertIn('document.body.dataset.backend = "online"', self.app)
        self.assertIn("authenticated commands remain operational", self.app)

    def test_decision_lab_is_connected_to_real_api(self):
        self.assertIn('data-view-panel="decisions"', self.html)
        self.assertIn('id="decisionForm"', self.html)
        self.assertIn('fetchJson("/api/decisions/analyse"', self.app)
        self.assertIn("renderDecisionLearning", self.app)
        self.assertIn('id="decisionRootCause"', self.html)
        self.assertIn('id="decisionLesson"', self.html)
        self.assertIn("recordDecisionOutcome", self.app)
        self.assertIn("INSUFFICIENT DATA", self.app)

    def test_world_model_is_connected_and_never_claims_execution(self):
        self.assertIn('id="worldActionForm"', self.html)
        self.assertIn('id="worldAlternativeSelect"', self.html)
        self.assertIn('id="worldSimulation"', self.html)
        self.assertIn('fetchJson(`/api/world-model?', self.app)
        self.assertIn('fetchJson("/api/world-model/simulate"', self.app)
        self.assertIn("ADVISORY ONLY // EXECUTED FALSE", self.app)
        self.assertIn("CONFOUNDERS //", self.app)

    def test_predictive_intelligence_exposes_uncertainty_and_sample_gate(self):
        self.assertIn('id="predictiveMetrics"', self.html)
        self.assertIn('id="predictiveSignals"', self.html)
        self.assertIn('fetchJson(`/api/predictions?', self.app)
        self.assertIn("FAILURE RATE WITHHELD", self.app)
        self.assertIn("ADVISORY ONLY", self.app)

    def test_proactive_watch_surface_is_connected(self):
        for element_id in (
            "watchForm", "watchMetric", "watchThreshold", "watchesView", "watchAlertsView"
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('fetchJson("/api/watches"', self.app)
        self.assertIn("NO AUTO ACTION", self.html)

    def test_browser_operations_surface_is_connected(self):
        self.assertIn('data-view-panel="browser"', self.html)
        for element_id in (
            "browserNavigateForm", "browserFillForm", "browserClickForm", "browserMissionForm",
            "browserMissionUrl", "browserMissionField", "browserMissionValue",
            "browserMissionControl", "browserPageView", "browserStateView",
            "browserStateShow", "browserStateContinue"
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('fetchJson("/api/browser/status")', self.app)
        self.assertIn("UNTRUSTED WEB CONTENT", self.app)
        self.assertIn("MISSION CHECKPOINTS", self.app)
        self.assertIn('fetchJson(`/api/application-state?', self.app)
        self.assertIn("FINAL CONTROL WILL NOT REPLAY", self.app)


if __name__ == "__main__":
    unittest.main()
