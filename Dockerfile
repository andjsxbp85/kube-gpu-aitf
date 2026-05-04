FROM huggingface/transformers-pytorch-gpu

RUN pip install --no-cache-dir jupyterlab ipykernel

ENV SHELL=/bin/bash

WORKDIR /workspace

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--no-browser", "--allow-root"]