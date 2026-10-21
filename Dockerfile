FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY price_monitor ./price_monitor
COPY sources.toml .
ENTRYPOINT ["python", "-m", "price_monitor"]
CMD ["run", "--report", "reports/prices.xlsx"]
