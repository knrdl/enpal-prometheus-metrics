FROM python:3.12.4-alpine3.19

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

RUN adduser --home /home/app --disabled-password --shell /bin/false --uid 1000 app
ENV PATH "/home/app/.local/bin:$PATH"

CMD python3 main.py

EXPOSE 8080/tcp

WORKDIR /app

USER app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

