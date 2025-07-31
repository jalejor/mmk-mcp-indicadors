FROM python:3.10-slim as base

RUN apt-get update \
  && apt-get install gcc -y \
  && apt-get clean

FROM base as dependencies
WORKDIR /dependencies
COPY ["requirements.txt", "./"]
RUN pip install --no-cache-dir --upgrade -r requirements.txt

FROM base as final
WORKDIR /app

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

COPY --from=dependencies /dependencies/requirements.txt ./
COPY --from=dependencies /root/.cache /root/.cache

# Install dependencies from cache
RUN pip install -r requirements.txt

COPY ["src", "./"]

CMD [ "python" ,"main.py" ]

FROM final as debugger

# Working dir
WORKDIR /app

RUN pip install ptvsd

CMD ["python", "-m", "ptvsd", "--host", "0.0.0.0", "--port", "5678", "--wait", "--multiprocess", "main.py"]