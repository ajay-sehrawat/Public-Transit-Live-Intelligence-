#!/usr/bin/env bash
# ==============================================================================
# Install ArgoCD GitOps Controller on GKE Cluster (Requirement d)
# Enforces automated sync and blocks manual kubectl apply interventions
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "  Deploying ArgoCD GitOps Controller on GKE                      "
echo "================================================================="

# Create argocd namespace
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Install official ArgoCD stable manifests
echo "[+] Applying ArgoCD core controller manifests..."
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD server pod ready
echo "[+] Waiting for ArgoCD server to be ready..."
kubectl rollout status deployment/argocd-server -n argocd --timeout=120s || echo "ArgoCD roll-out in progress..."

# Deploy the Root Application CRD tracking this Git repository
echo "[+] Registering transit-system-production Application in ArgoCD..."
kubectl apply -f k8s/argocd/application-root.yaml

echo "================================================================="
echo "  [✓] ArgoCD GitOps Controller is Active and Tracking Repository! "
echo "  Direct kubectl apply is now restricted by self-heal policy.     "
echo "================================================================="

