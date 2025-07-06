from flask import Flask, request, jsonify
from dotenv import load_dotenv
import cv2, os, re, requests
from werkzeug.utils import secure_filename
