#!/bin/bash

# get abspath for current dir

absolute_path=$(cd "$(dirname "$0")" && pwd)
KIVY_METRICS_DENSITY=2 python3 $absolute_path/flashcard_app.py
