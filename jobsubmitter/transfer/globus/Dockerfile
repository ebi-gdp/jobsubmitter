FROM --platform=linux/amd64 debian:stable-slim

# dockerhub.ebi.ac.uk/gdp-public/jobsubmitter/transfer:0.2.0

RUN mkdir /data

RUN apt-get update \
    && apt-get install -y curl jq \
    && rm -rf /var/lib/apt/lists/*

COPY transfer.sh /opt/transfer.sh

RUN chmod +x /opt/transfer.sh

WORKDIR /data

ENV PATH="/opt/:${PATH}"

CMD ["./transfer.sh"]
