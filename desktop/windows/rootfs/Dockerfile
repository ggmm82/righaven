# WSL 2 distribution of the Windows portable app: Alpine with the Docker engine.
# RigHaven itself runs in the same verified containers as the server release.
ARG BASE=alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f
FROM ${BASE}
RUN apk add --no-cache docker docker-cli-compose iptables ip6tables ca-certificates e2fsprogs socat \
 && mkdir -p /opt/righaven /var/log
COPY wsl.conf /etc/wsl.conf
COPY bin/ /usr/local/bin/
RUN chmod 0755 /usr/local/bin/righaven-* && righaven-selftest --static
