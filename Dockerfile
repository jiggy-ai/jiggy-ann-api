FROM bitnami/python:3.9-prod   

# expose
EXPOSE 8000

# set working directory
WORKDIR /app

# install pip
RUN apt-get update && apt-get install -y python3-pip

# update pip
RUN pip3 install --upgrade pip

# add requirements
COPY ./requirements.txt /app/requirements.txt

# install requirements
RUN pip3 install -r requirements.txt

COPY app/s3_bucket ./s3_bucket
COPY app/*.py .
COPY app/results.json .

#CMD gunicorn  -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000 --access-logfile -

CMD  uvicorn main:app --host 0.0.0.0

# use WEB_CONCURRENCY from yaml env to control number of workers
# see https://docs.gunicorn.org/en/latest/design.html for additional gunicorn worker considerations



