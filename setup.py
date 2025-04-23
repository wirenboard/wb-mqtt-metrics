#!/usr/bin/env python3

from setuptools import setup


def get_version():
    with open("debian/changelog", "r", encoding="utf-8") as f:
        return f.readline().split()[1][1:-1].split("~")[0]


setup(
    name="wb-mqtt-metrics",
    version=get_version(),
    description="metrics sender",
    license="MIT",
    author="Sokolov Semen",
    author_email="s.sokolov@wirenboard.ru",
    maintainer="Wiren Board Team",
    maintainer_email="info@wirenboard.com",
    url="https://github.com/wirenboard/wb-mqtt-metrics",
    packages=["wb.mqtt_metrics"],
)
