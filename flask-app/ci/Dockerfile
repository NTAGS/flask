FROM jenkins/jenkins:lts-jdk21

ARG HELM_VERSION=v3.21.4
ARG KUBECTL_VERSION=v1.35.9

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl docker.io python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" -o /tmp/helm.tgz \
    && tar -xzf /tmp/helm.tgz -C /tmp \
    && install /tmp/linux-amd64/helm /usr/local/bin/helm \
    && rm -rf /tmp/helm.tgz /tmp/linux-amd64 \
    && curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && helm version --short \
    && kubectl version --client=true --output=yaml
USER jenkins
