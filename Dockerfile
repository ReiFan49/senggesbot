#FROM python:3.6-alpine
FROM gorialis/discord.py:3.6-alpine-minimal
WORKDIR /app
#RUN apk add --no-cache gcc musl-dev linux-headers libffi-dev ffmpeg
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "app.py"]
