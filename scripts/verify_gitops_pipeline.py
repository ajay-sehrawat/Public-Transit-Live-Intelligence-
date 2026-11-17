# -*- coding: utf-8 -*-
"""Verification Script for GitOps & Kubernetes Manifests (Requirements c & d)
Verifies:
  1. Declarative K8s manifests exist for all services
  2. ArgoCD Application CRD configuration (self-heal, automated prune)
  3. HPA configurations for critical services
"""

import unittest
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class TestGitOpsPipeline(unittest.TestCase):

    def test_k8s_production_kustomization_exists(self):
        kust_path = os.path.join(REPO_ROOT, "k8s/production/kustomization.yaml")
        self.assertTrue(os.path.exists(kust_path), "kustomization.yaml must exist")
        with open(kust_path, "r") as f:
            content = f.read()
        self.assertIn("gps-ingestion/deployment.yaml", content)
        self.assertIn("event-adapter/deployment.yaml", content)
        self.assertIn("vehicle-registry/deployment.yaml", content)
        self.assertIn("hpa-critical-services.yaml", content)

    def test_argocd_application_root_specification(self):
        argo_path = os.path.join(REPO_ROOT, "k8s/argocd/application-root.yaml")
        self.assertTrue(os.path.exists(argo_path), "ArgoCD application-root.yaml must exist")
        with open(argo_path, "r") as f:
            content = f.read()
        self.assertIn("kind: Application", content)
        self.assertIn("selfHeal: true", content, "GitOps selfHeal must be enabled to forbid direct kubectl edits")
        self.assertIn("prune: true", content, "GitOps prune must be enabled")
        self.assertIn("path: k8s/production", content)

    def test_hpa_critical_services_spec(self):
        hpa_path = os.path.join(REPO_ROOT, "k8s/hpa/hpa-critical-services.yaml")
        self.assertTrue(os.path.exists(hpa_path), "HPA manifests must exist")
        with open(hpa_path, "r") as f:
            content = f.read()
        self.assertIn("name: gps-ingestion-hpa", content)
        self.assertIn("name: event-adapter-hpa", content)
        self.assertIn("averageUtilization: 50", content)
        self.assertIn("maxReplicas: 8", content)

if __name__ == "__main__":
    unittest.main()

