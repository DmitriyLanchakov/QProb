#!/bin/bash



source activate <project_name> && /usr/local/anaconda/envs/<project_name>/bin/uwsgi --ini /home/<project_name>/emperor.ini

source deactivate
