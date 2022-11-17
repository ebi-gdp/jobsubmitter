FROM --platform=linux/amd64 python:3.10

# dockerhub.ebi.ac.uk/gdp-public/jobsubmitter/transfer:0.1.0

ENV GLOBUS_CLI_INTERACTIVE=0

RUN pip install globus-cli

RUN useradd -ms /bin/bash globus-client

USER globus-client

WORKDIR /home/globus-client

RUN wget https://downloads.globus.org/globus-connect-personal/linux/stable/globusconnectpersonal-latest.tgz

# version number will change, so strip out version number in globus folder
RUN mkdir globus && tar -xf globusconnectpersonal-latest.tgz -C globus --strip-components=1 && rm  globusconnectpersonal-latest.tgz

COPY transfer.sh .

USER root

RUN mkdir /data && chown globus-client:globus-client /data && chmod 755 transfer.sh

USER globus-client

ENV PATH="${PATH}:/home/globus-client/globus/"

ENV PATH="${PATH}:/home/globus-client/.local/bin/"

CMD ["./transfer.sh"]
