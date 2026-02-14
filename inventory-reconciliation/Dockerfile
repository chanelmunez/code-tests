FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "reconcile.py", "--snapshot1", "data/snapshot_1.csv", "--snapshot2", "data/snapshot_2.csv", "--output-dir", "output"]
