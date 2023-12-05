FROM ubuntu:22.04
FROM python:3.11.6

LABEL author="ruslan.borodin"
LABEL version="1.0.0"
LABEL type="prod."

# ���������� ��� ����� � ���������
COPY . .

# ��������� ������������
RUN pip3 install --no-cache-dir -r requirements.txt

# ��������� ������� tzdata ��� �������������� �������� �����
RUN apt-get update && apt-get -y install tzdata && rm -rf /var/lib/apt/lists/* 
RUN apt-get update && apt-get -y install sqlite3 && apt-get -y install nano

# ��������� �������� ����� ������
RUN ln -fs /usr/share/zoneinfo/Europe/Moscow /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

# ����� ���� ������ ���������� ���������
EXPOSE 5000
EXPOSE 8181

# ������ �������
CMD [ "uwsgi", "--ini", "uwsgi.ini"]