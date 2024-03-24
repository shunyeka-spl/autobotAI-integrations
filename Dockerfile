FROM python:3.10
# steampipe

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
