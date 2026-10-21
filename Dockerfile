FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY secu_lense ./secu_lense
COPY app.py README.md ./
RUN pip install --no-cache-dir .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
