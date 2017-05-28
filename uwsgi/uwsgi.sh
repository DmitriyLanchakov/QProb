#!/bin/bash


PROJECT=qprob

source /usr/local/anaconda/bin/activate $PROJECT && /usr/local/anaconda/envs/$PROJECT/bin/uwsgi --ini /home/$PROJECT/emperor.ini

source /usr/local/anaconda/bin/deactivate
